import pytest
from speaker import Speaker, SpeakerInfo
from dlna import DlnaBackend


class _StubSpeaker(Speaker):
    """Minimal concrete Speaker used to exercise base-class default behavior."""

    def discover(self) -> list[SpeakerInfo]:
        return []

    def play_url(self, speaker: SpeakerInfo, url: str) -> None:
        """Intentionally empty: these tests never play audio."""

    def stop(self, speaker: SpeakerInfo) -> None:
        """Intentionally empty: these tests never stop playback."""


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
                """Intentionally empty: defined only so discover() is the sole missing method."""

            def stop(self, speaker: SpeakerInfo) -> None:
                """Intentionally empty: defined only so discover() is the sole missing method."""

        with pytest.raises(TypeError):
            Incomplete()

    def test_concrete_must_implement_play_url(self):
        class Incomplete(Speaker):
            def discover(self) -> list[SpeakerInfo]:
                return []

            def stop(self, speaker: SpeakerInfo) -> None:
                """Intentionally empty: defined only so play_url() is the sole missing method."""

        with pytest.raises(TypeError):
            Incomplete()

    def test_concrete_must_implement_stop(self):
        class Incomplete(Speaker):
            def discover(self) -> list[SpeakerInfo]:
                return []

            def play_url(self, speaker: SpeakerInfo, url: str) -> None:
                """Intentionally empty: defined only so stop() is the sole missing method."""

        with pytest.raises(TypeError):
            Incomplete()


class TestSpeakerDefaults:
    def test_preferred_format_is_wav(self):
        assert _StubSpeaker().preferred_format == "wav"

    def test_get_transport_state_default_is_unknown(self):
        info = SpeakerInfo(id="x", name="X")
        assert _StubSpeaker().get_transport_state(info) == "unknown"

    def test_get_debug_info_default_is_empty(self):
        info = SpeakerInfo(id="x", name="X")
        assert _StubSpeaker().get_debug_info(info) == {}


class TestDlnaBackend:
    def test_is_a_speaker(self):
        assert isinstance(DlnaBackend(), Speaker)

    def test_preferred_format_is_wav(self):
        assert DlnaBackend.preferred_format == "wav"
