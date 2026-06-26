import socket
import pytest
from unittest.mock import patch, MagicMock
from speaker import SpeakerInfo
from dlna import DlnaBackend, _extract_location, _parse_device_description

SAMPLE_SSDP_RESPONSE = (
    "HTTP/1.1 200 OK\r\n"
    "LOCATION: http://192.168.1.100:8060/desc.xml\r\n"
    "ST: urn:schemas-upnp-org:device:MediaRenderer:1\r\n"
    "\r\n"
)

SAMPLE_DESCRIPTION_XML = """<?xml version="1.0"?>
<root xmlns="urn:schemas-upnp-org:device-1-0">
  <device>
    <friendlyName>Living Room Speaker</friendlyName>
    <serviceList>
      <service>
        <serviceType>urn:schemas-upnp-org:service:AVTransport:1</serviceType>
        <controlURL>/upnp/control/AVTransport1</controlURL>
      </service>
    </serviceList>
  </device>
</root>"""

CONTROL_URL = "http://192.168.1.100:8060/upnp/control/AVTransport1"


def _url_mock(content: bytes | str) -> MagicMock:
    if isinstance(content, str):
        content = content.encode()
    ctx = MagicMock()
    ctx.__enter__ = lambda s: s
    ctx.__exit__ = MagicMock(return_value=False)
    ctx.read.return_value = content
    return ctx


def _soap_mock() -> MagicMock:
    return _url_mock(b"")


class TestExtractLocation:
    def test_parses_location_header(self):
        assert _extract_location(SAMPLE_SSDP_RESPONSE) == "http://192.168.1.100:8060/desc.xml"

    def test_returns_none_when_absent(self):
        assert _extract_location("HTTP/1.1 200 OK\r\n\r\n") is None

    def test_case_insensitive(self):
        assert _extract_location("location: http://x/d.xml\r\n") == "http://x/d.xml"


class TestParseDeviceDescription:
    def test_extracts_name_and_control_url(self):
        result = _parse_device_description(SAMPLE_DESCRIPTION_XML, "http://192.168.1.100:8060/desc.xml")
        assert result == ("Living Room Speaker", CONTROL_URL)

    def test_relative_control_url_made_absolute(self):
        result = _parse_device_description(SAMPLE_DESCRIPTION_XML, "http://192.168.1.100:8060/desc.xml")
        assert result is not None
        _, url = result
        assert url.startswith("http://192.168.1.100:8060")

    def test_absolute_control_url_unchanged(self):
        xml = SAMPLE_DESCRIPTION_XML.replace(
            "/upnp/control/AVTransport1", "http://10.0.0.1:9000/avt"
        )
        result = _parse_device_description(xml, "http://192.168.1.100:8060/desc.xml")
        assert result is not None
        assert result[1] == "http://10.0.0.1:9000/avt"

    def test_returns_none_without_avtransport(self):
        xml = """<root xmlns="urn:schemas-upnp-org:device-1-0">
          <device><friendlyName>TV</friendlyName><serviceList/></device>
        </root>"""
        assert _parse_device_description(xml, "http://x/") is None

    def test_returns_none_on_invalid_xml(self):
        assert _parse_device_description("not xml at all", "http://x/") is None


class TestDlnaDiscover:
    def test_returns_speakers_from_ssdp(self):
        mock_sock = MagicMock()
        mock_sock.recvfrom.side_effect = [
            (SAMPLE_SSDP_RESPONSE.encode(), ("192.168.1.100", 1900)),
            socket.timeout(),
        ]
        with patch("dlna.socket.socket", return_value=mock_sock):
            with patch("dlna.urllib.request.urlopen", return_value=_url_mock(SAMPLE_DESCRIPTION_XML)):
                speakers = DlnaBackend().discover()
        assert len(speakers) == 1
        assert speakers[0].name == "Living Room Speaker"
        assert speakers[0].id == CONTROL_URL

    def test_returns_empty_on_timeout(self):
        mock_sock = MagicMock()
        mock_sock.recvfrom.side_effect = socket.timeout()
        with patch("dlna.socket.socket", return_value=mock_sock):
            assert DlnaBackend().discover() == []

    def test_skips_devices_without_avtransport(self):
        xml = """<root xmlns="urn:schemas-upnp-org:device-1-0">
          <device><friendlyName>TV</friendlyName><serviceList/></device>
        </root>"""
        mock_sock = MagicMock()
        mock_sock.recvfrom.side_effect = [
            (SAMPLE_SSDP_RESPONSE.encode(), ("192.168.1.100", 1900)),
            socket.timeout(),
        ]
        with patch("dlna.socket.socket", return_value=mock_sock):
            with patch("dlna.urllib.request.urlopen", return_value=_url_mock(xml)):
                assert DlnaBackend().discover() == []

    def test_deduplicates_locations(self):
        mock_sock = MagicMock()
        mock_sock.recvfrom.side_effect = [
            (SAMPLE_SSDP_RESPONSE.encode(), ("192.168.1.100", 1900)),
            (SAMPLE_SSDP_RESPONSE.encode(), ("192.168.1.100", 1900)),
            socket.timeout(),
        ]
        with patch("dlna.socket.socket", return_value=mock_sock):
            with patch("dlna.urllib.request.urlopen", return_value=_url_mock(SAMPLE_DESCRIPTION_XML)) as m:
                DlnaBackend().discover()
        assert m.call_count == 1  # fetched description only once


class TestDlnaPlayUrl:
    def test_sends_set_uri_then_play(self):
        speaker = SpeakerInfo(id=CONTROL_URL, name="Test")
        with patch("dlna.urllib.request.urlopen", return_value=_soap_mock()) as m:
            DlnaBackend().play_url(speaker, "http://192.168.1.50:1234/audio.wav")
        assert m.call_count == 2
        first = m.call_args_list[0][0][0]
        second = m.call_args_list[1][0][0]
        assert "SetAVTransportURI" in first.get_header("Soapaction")
        assert "Play" in second.get_header("Soapaction")

    def test_url_embedded_in_set_uri_body(self):
        speaker = SpeakerInfo(id=CONTROL_URL, name="Test")
        with patch("dlna.urllib.request.urlopen", return_value=_soap_mock()) as m:
            DlnaBackend().play_url(speaker, "http://192.168.1.50:1234/audio.wav")
        body = m.call_args_list[0][0][0].data.decode()
        assert "http://192.168.1.50:1234/audio.wav" in body

    def test_url_with_ampersand_is_escaped(self):
        speaker = SpeakerInfo(id=CONTROL_URL, name="Test")
        with patch("dlna.urllib.request.urlopen", return_value=_soap_mock()) as m:
            DlnaBackend().play_url(speaker, "http://example.com/audio?a=1&b=2")
        body = m.call_args_list[0][0][0].data.decode()
        assert "&amp;" in body
        assert "&b=2" not in body

    def test_soap_sent_to_control_url(self):
        speaker = SpeakerInfo(id=CONTROL_URL, name="Test")
        with patch("dlna.urllib.request.urlopen", return_value=_soap_mock()) as m:
            DlnaBackend().play_url(speaker, "http://x/audio.wav")
        assert m.call_args_list[0][0][0].full_url == CONTROL_URL


class TestDlnaStop:
    def test_sends_stop_action(self):
        speaker = SpeakerInfo(id=CONTROL_URL, name="Test")
        with patch("dlna.urllib.request.urlopen", return_value=_soap_mock()) as m:
            DlnaBackend().stop(speaker)
        assert m.call_count == 1
        req = m.call_args_list[0][0][0]
        assert "Stop" in req.get_header("Soapaction")
        assert CONTROL_URL == req.full_url


class TestDlnaPreferredFormat:
    def test_preferred_format_is_wav(self):
        assert DlnaBackend.preferred_format == "wav"
