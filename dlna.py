import html
import socket
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from speaker import Speaker, SpeakerInfo

SSDP_ADDR = "239.255.255.250"
SSDP_PORT = 1900
SSDP_MX = 3
SSDP_ST = "urn:schemas-upnp-org:device:MediaRenderer:1"
AVT_NS = "urn:schemas-upnp-org:service:AVTransport:1"

SSDP_SEARCH = (
    "M-SEARCH * HTTP/1.1\r\n"
    f"HOST: {SSDP_ADDR}:{SSDP_PORT}\r\n"
    'MAN: "ssdp:discover"\r\n'
    f"MX: {SSDP_MX}\r\n"
    f"ST: {SSDP_ST}\r\n"
    "\r\n"
)


def _extract_location(ssdp_response: str) -> str | None:
    for line in ssdp_response.splitlines():
        if line.upper().startswith("LOCATION:"):
            return line.split(":", 1)[1].strip()
    return None


def _parse_device_description(xml_text: str, location_url: str) -> tuple[str, str] | None:
    """Return (friendly_name, avt_control_url) or None if no AVTransport found."""
    try:
        root = ET.fromstring(xml_text)
        name_el = root.find(".//{*}friendlyName")
        name = (name_el.text or "Unknown DLNA") if name_el is not None else "Unknown DLNA"

        for service in root.findall(".//{*}service"):
            st = service.find("{*}serviceType")
            cu = service.find("{*}controlURL")
            if st is not None and "AVTransport" in (st.text or ""):
                if cu is not None and cu.text:
                    control_url = cu.text.strip()
                    if not control_url.startswith("http"):
                        parsed = urllib.parse.urlparse(location_url)
                        prefix = "/" if not control_url.startswith("/") else ""
                        control_url = f"{parsed.scheme}://{parsed.netloc}{prefix}{control_url}"
                    return name, control_url
    except Exception:
        pass
    return None


def _soap_action(control_url: str, action: str, body: str) -> None:
    envelope = (
        '<?xml version="1.0"?>'
        '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
        's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">'
        f"<s:Body>{body}</s:Body>"
        "</s:Envelope>"
    )
    req = urllib.request.Request(
        control_url,
        data=envelope.encode("utf-8"),
        headers={
            "Content-Type": 'text/xml; charset="utf-8"',
            "SOAPAction": f'"{AVT_NS}#{action}"',
        },
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        resp.read()


class DlnaBackend(Speaker):
    preferred_format = "wav"

    def discover(self) -> list[SpeakerInfo]:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(SSDP_MX + 1)
        sock.sendto(SSDP_SEARCH.encode(), (SSDP_ADDR, SSDP_PORT))

        locations: list[str] = []
        try:
            while True:
                data, _ = sock.recvfrom(4096)
                loc = _extract_location(data.decode(errors="ignore"))
                if loc and loc not in locations:
                    locations.append(loc)
        except socket.timeout:
            pass

        speakers: list[SpeakerInfo] = []
        for location in locations:
            try:
                with urllib.request.urlopen(location, timeout=3) as resp:
                    xml_text = resp.read().decode("utf-8", errors="replace")
                result = _parse_device_description(xml_text, location)
                if result:
                    name, control_url = result
                    speakers.append(SpeakerInfo(id=control_url, name=name))
            except Exception:
                pass
        return speakers

    def play_url(self, speaker: SpeakerInfo, url: str) -> None:
        safe_url = html.escape(url)
        _soap_action(
            speaker.id,
            "SetAVTransportURI",
            f'<u:SetAVTransportURI xmlns:u="{AVT_NS}">'
            "<InstanceID>0</InstanceID>"
            f"<CurrentURI>{safe_url}</CurrentURI>"
            "<CurrentURIMetaData></CurrentURIMetaData>"
            "</u:SetAVTransportURI>",
        )
        _soap_action(
            speaker.id,
            "Play",
            f'<u:Play xmlns:u="{AVT_NS}">'
            "<InstanceID>0</InstanceID>"
            "<Speed>1</Speed>"
            "</u:Play>",
        )

    def stop(self, speaker: SpeakerInfo) -> None:
        _soap_action(
            speaker.id,
            "Stop",
            f'<u:Stop xmlns:u="{AVT_NS}">'
            "<InstanceID>0</InstanceID>"
            "</u:Stop>",
        )

    def get_transport_state(self, speaker: SpeakerInfo) -> str:
        envelope = (
            '<?xml version="1.0"?>'
            '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
            's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">'
            f'<s:Body><u:GetTransportInfo xmlns:u="{AVT_NS}">'
            "<InstanceID>0</InstanceID>"
            "</u:GetTransportInfo></s:Body></s:Envelope>"
        )
        req = urllib.request.Request(
            speaker.id,
            data=envelope.encode("utf-8"),
            headers={
                "Content-Type": 'text/xml; charset="utf-8"',
                "SOAPAction": f'"{AVT_NS}#GetTransportInfo"',
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                xml_text = resp.read().decode("utf-8", errors="replace")
            root = ET.fromstring(xml_text)
            el = root.find(".//{*}CurrentTransportState")
            return el.text.lower() if el is not None and el.text else "unknown"
        except Exception:
            return "unknown"
