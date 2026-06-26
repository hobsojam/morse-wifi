import time
import urllib.request
import pytest
from server import AudioServer


@pytest.fixture
def server():
    s = AudioServer()
    s.start()
    yield s
    s.stop()


class TestAudioServer:
    def test_starts_and_stops(self):
        s = AudioServer()
        s.start()
        assert s.is_running()
        s.stop()
        assert not s.is_running()

    def test_url_is_reachable_ip(self, server):
        import re
        assert re.match(r"http://\d+\.\d+\.\d+\.\d+:\d+/audio\.\w+", server.url())

    def test_url_extension_matches_format(self, server):
        assert server.url(extension="mp3").endswith(".mp3")
        assert server.url(extension="wav").endswith(".wav")

    def test_serves_wav_bytes(self, server):
        data = b"RIFF" + b"\x00" * 40
        server.set_audio(data)
        response = urllib.request.urlopen(server.url())
        assert response.read() == data

    def test_content_type_defaults_to_wav(self, server):
        server.set_audio(b"RIFF" + b"\x00" * 40)
        response = urllib.request.urlopen(server.url(extension="wav"))
        assert response.headers.get("Content-Type") == "audio/wav"

    def test_wav_includes_content_length(self, server):
        data = b"RIFF" + b"\x00" * 40
        server.set_audio(data, content_type="audio/wav")
        response = urllib.request.urlopen(server.url(extension="wav"))
        assert response.headers.get("Content-Length") == str(len(data))

    def test_mp3_includes_content_length(self, server):
        data = b"\xff\xfb" + b"\x00" * 40
        server.set_audio(data, content_type="audio/mpeg")
        response = urllib.request.urlopen(server.url(extension="mp3"))
        assert response.headers.get("Content-Length") == str(len(data))

    def test_content_type_mp3(self, server):
        server.set_audio(b"\xff\xfb" + b"\x00" * 40, content_type="audio/mpeg")
        response = urllib.request.urlopen(server.url(extension="mp3"))
        assert response.headers.get("Content-Type") == "audio/mpeg"

    def test_head_request_supported(self, server):
        server.set_audio(b"RIFF" + b"\x00" * 40)
        req = urllib.request.Request(server.url(extension="wav"), method="HEAD")
        response = urllib.request.urlopen(req)
        assert response.status == 200

    def test_updated_audio_is_served(self, server):
        first = b"RIFF" + b"\x00" * 40
        second = b"RIFF" + b"\x01" * 40
        server.set_audio(first)
        server.set_audio(second)
        response = urllib.request.urlopen(server.url())
        assert response.read() == second

    def test_no_audio_returns_204(self, server):
        response = urllib.request.urlopen(server.url())
        assert response.status == 204

    def test_port_is_available_after_stop(self):
        s = AudioServer()
        s.start()
        port = s.port
        s.stop()
        # should be able to start a new server (reuses the port slot)
        s2 = AudioServer(port=port)
        s2.start()
        assert s2.is_running()
        s2.stop()
