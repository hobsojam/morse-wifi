import json
import socket
import threading
import pytest
from unittest.mock import patch, MagicMock, call
from heos import HeosBackend, _parse_players, _build_command, HEOS_PORT


SAMPLE_SSDP_RESPONSE = (
    "HTTP/1.1 200 OK\r\n"
    "LOCATION: http://192.168.1.50:60006/upnp/desc/aios_device/aios_device.xml\r\n"
    "ST: urn:schemas-denon-com:device:ACT-Denon:1\r\n"
    "\r\n"
)

SAMPLE_PLAYERS_RESPONSE = json.dumps({
    "heos": {"command": "player/get_players", "result": "success", "message": ""},
    "payload": [
        {"name": "Living Room", "pid": 1, "model": "HEOS 1", "version": "1.0"},
        {"name": "Kitchen", "pid": 2, "model": "HEOS 3", "version": "1.0"},
    ]
})

SAMPLE_PLAY_RESPONSE = json.dumps({
    "heos": {"command": "player/play_stream", "result": "success", "message": ""},
})

SAMPLE_STOP_RESPONSE = json.dumps({
    "heos": {"command": "player/set_play_state", "result": "success", "message": ""},
})


class TestBuildCommand:
    def test_simple_command(self):
        cmd = _build_command("player/get_players")
        assert cmd == "heos://player/get_players\r\n"

    def test_command_with_params(self):
        cmd = _build_command("player/play_stream", pid=1, url="http://x/a.wav")
        assert "heos://player/play_stream?" in cmd
        assert "pid=1" in cmd
        assert "url=http://x/a.wav" in cmd
        assert cmd.endswith("\r\n")


class TestParsePlayers:
    def test_parses_player_list(self):
        players = _parse_players(SAMPLE_PLAYERS_RESPONSE)
        assert len(players) == 2
        assert players[0].name == "Living Room"
        assert players[0].id == "1"
        assert players[1].name == "Kitchen"
        assert players[1].id == "2"

    def test_empty_payload(self):
        response = json.dumps({
            "heos": {"command": "player/get_players", "result": "success", "message": ""},
            "payload": []
        })
        assert _parse_players(response) == []


class TestHeosDiscover:
    def test_discover_returns_speakers(self):
        mock_sock = MagicMock()
        mock_sock.recvfrom.side_effect = [
            (SAMPLE_SSDP_RESPONSE.encode(), ("192.168.1.50", 1900)),
            socket.timeout(),
        ]

        mock_tcp = MagicMock()
        mock_tcp.makefile.return_value.__enter__ = lambda s: s
        mock_tcp.makefile.return_value.__exit__ = MagicMock(return_value=False)
        mock_tcp.makefile.return_value.readline.return_value = SAMPLE_PLAYERS_RESPONSE + "\r\n"

        with patch("heos.socket.socket") as mock_socket_cls:
            mock_socket_cls.side_effect = [mock_sock, mock_tcp]
            backend = HeosBackend()
            speakers = backend.discover()

        assert len(speakers) == 2
        assert speakers[0].name == "Living Room"

    def test_discover_returns_empty_on_timeout(self):
        mock_sock = MagicMock()
        mock_sock.recvfrom.side_effect = socket.timeout()

        with patch("heos.socket.socket", return_value=mock_sock):
            backend = HeosBackend()
            speakers = backend.discover()

        assert speakers == []


class TestHeosPlayUrl:
    def _make_tcp_mock(self, response_line: str) -> MagicMock:
        mock_file = MagicMock()
        mock_file.readline.return_value = response_line + "\r\n"
        mock_tcp = MagicMock()
        mock_tcp.__enter__ = lambda s: s
        mock_tcp.__exit__ = MagicMock(return_value=False)
        mock_tcp.makefile.return_value.__enter__ = lambda s: s
        mock_tcp.makefile.return_value.__exit__ = MagicMock(return_value=False)
        mock_tcp.makefile.return_value.readline.return_value = response_line + "\r\n"
        return mock_tcp

    def test_play_url_sends_correct_command(self):
        from speaker import SpeakerInfo
        info = SpeakerInfo(id="1", name="Living Room")
        tcp = self._make_tcp_mock(SAMPLE_PLAY_RESPONSE)

        with patch("heos.socket.socket", return_value=tcp):
            backend = HeosBackend(device_ip="192.168.1.50")
            backend.play_url(info, "http://192.168.1.1:8080/audio.wav")

        sent = tcp.sendall.call_args[0][0].decode()
        assert "player/play_stream" in sent
        assert "pid=1" in sent
        assert "http://192.168.1.1:8080/audio.wav" in sent

    def test_play_url_raises_on_heos_error(self):
        from speaker import SpeakerInfo
        error_response = json.dumps({
            "heos": {"command": "player/play_stream", "result": "fail",
                     "message": "eid=9&text=Unknown error"}
        })
        info = SpeakerInfo(id="1", name="Living Room")
        tcp = self._make_tcp_mock(error_response)

        with patch("heos.socket.socket", return_value=tcp):
            backend = HeosBackend(device_ip="192.168.1.50")
            with pytest.raises(RuntimeError, match="HEOS error"):
                backend.play_url(info, "http://192.168.1.1:8080/audio.wav")

    def test_get_play_state_returns_state(self):
        from speaker import SpeakerInfo
        info = SpeakerInfo(id="1", name="Living Room")
        response = json.dumps({
            "heos": {"command": "player/get_play_state", "result": "success",
                     "message": "pid=1&state=play"}
        })
        tcp = self._make_tcp_mock(response)
        with patch("heos.socket.socket", return_value=tcp):
            state, raw = HeosBackend(device_ip="192.168.1.50").get_play_state(info)
        assert state == "play"
        assert "play" in raw

    def test_stop_sends_correct_command(self):
        from speaker import SpeakerInfo
        info = SpeakerInfo(id="2", name="Kitchen")
        tcp = self._make_tcp_mock(SAMPLE_STOP_RESPONSE)

        with patch("heos.socket.socket", return_value=tcp):
            backend = HeosBackend(device_ip="192.168.1.50")
            backend.stop(info)

        sent = tcp.sendall.call_args[0][0].decode()
        assert "set_play_state" in sent
        assert "pid=2" in sent
        assert "state=stop" in sent
