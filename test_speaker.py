import pytest
from speaker import Speaker, SpeakerInfo
from dlna import DlnaBackend


class TestSpeakerInfo:
    def test_has_id_and_name(self):
        info = SpeakerInfo(id="abc", name="Living Room")
        assert info.id == "abc"
        assert info.name == "Living Room"

    def test_str_includes_name(self):
        info = SpeakerInfo(id="abc", name="Living Room")
        assert "Living Room" in str(info)


class TestSpeakerInterface:
    def test_speaker_is_abstract(self):
        with pytest.raises(TypeError):
            Speaker()

    def test_concrete_must_implement_discover(self):
        class Incomplete(Speaker):
            def play_url(self, speaker: SpeakerInfo, url: str) -> None:
                pass
            def stop(self, speaker: SpeakerInfo) -> None:
                pass
        with pytest.raises(TypeError):
            Incomplete()

    def test_concrete_must_implement_play_url(self):
        class Incomplete(Speaker):
            def discover(self) -> list[SpeakerInfo]:
                return []
            def stop(self, speaker: SpeakerInfo) -> None:
                pass
        with pytest.raises(TypeError):
            Incomplete()

    def test_concrete_must_implement_stop(self):
        class Incomplete(Speaker):
            def discover(self) -> list[SpeakerInfo]:
                return []
            def play_url(self, speaker: SpeakerInfo, url: str) -> None:
                pass
        with pytest.raises(TypeError):
            Incomplete()


class TestSpeakerDefaults:
    def test_preferred_format_is_mp3(self):
        class Concrete(Speaker):
            def discover(self): return []
            def play_url(self, s, u): pass
            def stop(self, s): pass
        assert Concrete().preferred_format == "mp3"


class TestDlnaStub:
    def test_discover_raises_not_implemented(self):
        with pytest.raises(NotImplementedError):
            DlnaBackend().discover()

    def test_play_url_raises_not_implemented(self):
        info = SpeakerInfo(id="x", name="X")
        with pytest.raises(NotImplementedError):
            DlnaBackend().play_url(info, "http://example.com/audio.wav")

    def test_stop_raises_not_implemented(self):
        info = SpeakerInfo(id="x", name="X")
        with pytest.raises(NotImplementedError):
            DlnaBackend().stop(info)
