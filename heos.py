import json
import socket
import urllib.parse

from speaker import Speaker, SpeakerInfo

HEOS_PORT = 1255
# Standard SSDP multicast address and port fixed by the UPnP specification;
# HEOS devices listen here for discovery. Local-scope multicast — never
# routed beyond the LAN.
SSDP_ADDR = "239.255.255.250"
SSDP_PORT = 1900
SSDP_MX = 3
SSDP_ST = "urn:schemas-denon-com:device:ACT-Denon:1"
HEOS_TIMEOUT = 5

SSDP_SEARCH = (
    f"M-SEARCH * HTTP/1.1\r\n"
    f"HOST: {SSDP_ADDR}:{SSDP_PORT}\r\n"
    f"MAN: \"ssdp:discover\"\r\n"
    f"MX: {SSDP_MX}\r\n"
    f"ST: {SSDP_ST}\r\n"
    f"\r\n"
)


def _build_command(command: str, **params) -> str:
    if params:
        param_str = "&".join(f"{k}={v}" for k, v in params.items())
        return f"heos://{command}?{param_str}\r\n"
    return f"heos://{command}\r\n"


def _parse_players(response: str) -> list[SpeakerInfo]:
    data = json.loads(response)
    return [
        SpeakerInfo(id=str(p["pid"]), name=p["name"])
        for p in data.get("payload", [])
    ]


def _extract_location_ip(response: str) -> str | None:
    for line in response.splitlines():
        if line.upper().startswith("LOCATION:"):
            url = line.split(":", 1)[1].strip()
            return urllib.parse.urlparse(url).hostname
    return None


def _heos_command(ip: str, command: str, **params) -> str:
    cmd = _build_command(command, **params).encode()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(HEOS_TIMEOUT)
    sock.connect((ip, HEOS_PORT))
    sock.sendall(cmd)
    with sock.makefile("r") as f:
        return f.readline().strip()


class HeosBackend(Speaker):
    preferred_format = "wav"

    def __init__(self, device_ip: str | None = None):
        self._device_ip = device_ip

    def discover(self) -> list[SpeakerInfo]:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(SSDP_MX + 1)
        sock.sendto(SSDP_SEARCH.encode(), (SSDP_ADDR, SSDP_PORT))

        device_ips: list[str] = []
        try:
            while True:
                data, _ = sock.recvfrom(4096)
                ip = _extract_location_ip(data.decode(errors="ignore"))
                if ip and ip not in device_ips:
                    device_ips.append(ip)
        except socket.timeout:
            pass

        if not device_ips:
            return []

        self._device_ip = device_ips[0]
        try:
            response = _heos_command(self._device_ip, "player/get_players")
            return _parse_players(response)
        except Exception:
            return []

    def play_url(self, speaker: SpeakerInfo, url: str) -> None:
        if self._device_ip is None:
            raise RuntimeError("No HEOS device discovered. Call discover() first.")
        response = _heos_command(
            self._device_ip,
            "player/play_stream",
            pid=speaker.id,
            url=url,
        )
        data = json.loads(response)
        if data["heos"].get("result") == "fail":
            raise RuntimeError(f"HEOS error: {data['heos'].get('message', 'unknown')}")

    def get_play_state(self, speaker: SpeakerInfo) -> tuple[str, str]:
        if self._device_ip is None:
            return "unknown", ""
        response = _heos_command(self._device_ip, "player/get_play_state", pid=speaker.id)
        try:
            data = json.loads(response)
            msg = data["heos"].get("message", "")
            for part in msg.split("&"):
                if part.startswith("state="):
                    return part[6:], response
        except Exception:
            pass
        return "unknown", response

    def get_transport_state(self, speaker: SpeakerInfo) -> str:
        state, _ = self.get_play_state(speaker)
        return {"play": "playing", "stop": "stopped"}.get(state, state)

    def get_volume(self, speaker: SpeakerInfo) -> str:
        if self._device_ip is None:
            return "?"
        try:
            response = _heos_command(self._device_ip, "player/get_volume", pid=speaker.id)
            data = json.loads(response)
            msg = data["heos"].get("message", "")
            for part in msg.split("&"):
                if part.startswith("level="):
                    return part[6:]
        except Exception:
            pass
        return "?"

    def get_mute(self, speaker: SpeakerInfo) -> str:
        if self._device_ip is None:
            return "?"
        try:
            response = _heos_command(self._device_ip, "player/get_mute", pid=speaker.id)
            data = json.loads(response)
            msg = data["heos"].get("message", "")
            for part in msg.split("&"):
                if part.startswith("state="):
                    return part[6:]
        except Exception:
            pass
        return "?"

    def get_now_playing_media(self, speaker: SpeakerInfo) -> dict:
        if self._device_ip is None:
            return {}
        try:
            response = _heos_command(self._device_ip, "player/get_now_playing_media", pid=speaker.id)
            data = json.loads(response)
            return data.get("payload", {})
        except Exception:
            return {}

    def get_debug_info(self, speaker: SpeakerInfo) -> dict:
        return {
            "volume": self.get_volume(speaker),
            "muted": self.get_mute(speaker),
            "now playing": self.get_now_playing_media(speaker),
        }

    def stop(self, speaker: SpeakerInfo) -> None:
        if self._device_ip is None:
            raise RuntimeError("No HEOS device discovered. Call discover() first.")
        _heos_command(
            self._device_ip,
            "player/set_play_state",
            pid=speaker.id,
            state="stop",
        )
