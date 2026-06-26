import time
import pytest
from unittest.mock import MagicMock, patch
from speaker import SpeakerInfo
from main import (
    select_speaker,
    prompt_wpm,
    handle_command,
    process_input,
    BACKENDS,
)


SPEAKERS = [
    SpeakerInfo(id="1", name="Living Room"),
    SpeakerInfo(id="2", name="Kitchen"),
]


class TestSelectSpeaker:
    def test_single_speaker_auto_selected(self):
        result = select_speaker([SPEAKERS[0]])
        assert result == SPEAKERS[0]

    def test_returns_chosen_speaker(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "1")
        result = select_speaker(SPEAKERS)
        assert result == SPEAKERS[0]

    def test_second_choice(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "2")
        result = select_speaker(SPEAKERS)
        assert result == SPEAKERS[1]

    def test_invalid_then_valid(self, monkeypatch):
        responses = iter(["0", "99", "abc", "2"])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        result = select_speaker(SPEAKERS)
        assert result == SPEAKERS[1]


class TestPromptWpm:
    def test_valid_wpm(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "15")
        assert prompt_wpm() == 15

    def test_empty_returns_default(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "")
        assert prompt_wpm() == 20

    def test_invalid_then_valid(self, monkeypatch):
        responses = iter(["abc", "0", "-5", "25"])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        assert prompt_wpm() == 25


class TestHandleCommand:
    def test_wpm_command(self):
        state = {"wpm": 20, "backend_name": "heos"}
        assert handle_command("/wpm 15", state)
        assert state["wpm"] == 15

    def test_wpm_invalid_ignored(self):
        state = {"wpm": 20, "backend_name": "heos"}
        assert not handle_command("/wpm abc", state)
        assert state["wpm"] == 20

    def test_backend_switch_updates_speaker_and_backend(self):
        mock_backend = MagicMock()
        mock_backend.discover.return_value = [SPEAKERS[0]]
        state = {"wpm": 20, "backend_name": "dlna", "speaker": SPEAKERS[1]}

        with patch.dict("main.BACKENDS", {"heos": lambda: mock_backend}), \
             patch("main.select_speaker", return_value=SPEAKERS[0]):
            assert handle_command("/backend heos", state)

        assert state["backend_name"] == "heos"
        assert state["backend"] is mock_backend
        assert state["speaker"] == SPEAKERS[0]

    def test_backend_switch_fails_silently_when_no_speakers(self):
        mock_backend = MagicMock()
        mock_backend.discover.return_value = []
        state = {"wpm": 20, "backend_name": "heos", "speaker": SPEAKERS[0]}

        with patch.dict("main.BACKENDS", {"dlna": lambda: mock_backend}):
            assert not handle_command("/backend dlna", state)

        assert state["backend_name"] == "heos"
        assert state["speaker"] == SPEAKERS[0]

    def test_backend_switch_unknown_ignored(self):
        state = {"wpm": 20, "backend_name": "heos", "speaker": SPEAKERS[0]}
        assert not handle_command("/backend foo", state)
        assert state["backend_name"] == "heos"

    def test_unknown_command_returns_false(self):
        state = {"wpm": 20, "backend_name": "heos"}
        assert not handle_command("/foo", state)


class TestProcessInput:
    def test_always_uses_wav(self):
        mock_backend = MagicMock()
        mock_server = MagicMock()
        mock_server.url.return_value = "http://127.0.0.1:8080/audio.wav"
        state = {"busy_until": 0.0, "debug": False}
        process_input("SOS", SPEAKERS[0], mock_backend, mock_server, wpm=20, state=state)
        _, content_type = mock_server.set_audio.call_args.args
        assert content_type == "audio/wav"

    def test_schedules_play(self):
        mock_backend = MagicMock()
        mock_server = MagicMock()
        mock_server.url.return_value = "http://127.0.0.1:8080/audio.wav"
        speaker = SPEAKERS[0]

        state = {"busy_until": 0.0, "debug": False}
        process_input("SOS", speaker, mock_backend, mock_server, wpm=20, state=state)

        mock_server.set_audio.assert_called_once()
        mock_backend.play_url.assert_called_once_with(speaker, "http://127.0.0.1:8080/audio.wav")
        assert state["busy_until"] > time.monotonic()

    def test_empty_input_ignored(self):
        mock_backend = MagicMock()
        mock_server = MagicMock()
        state = {"busy_until": 0.0, "debug": False}
        process_input("   ", SPEAKERS[0], mock_backend, mock_server, wpm=20, state=state)
        mock_backend.play_url.assert_not_called()

    def test_queues_when_busy(self):
        mock_backend = MagicMock()
        mock_server = MagicMock()
        mock_server.url.return_value = "http://127.0.0.1:8080/audio.wav"

        state = {"busy_until": time.monotonic() + 10.0, "debug": False}

        with patch("time.sleep") as mock_sleep:
            process_input("HI", SPEAKERS[0], mock_backend, mock_server, wpm=20, state=state)
            mock_sleep.assert_called()

    def test_title_is_original_text(self):
        mock_backend = MagicMock()
        mock_server = MagicMock()
        mock_server.url.return_value = "http://127.0.0.1:8080/audio.wav"
        state = {"busy_until": 0.0, "debug": False}
        process_input("Hello", SPEAKERS[0], mock_backend, mock_server, wpm=20, state=state)
        audio, _ = mock_server.set_audio.call_args.args
        assert b"Hello" in audio  # RIFF INAM chunk contains original text


class TestBackends:
    def test_heos_in_backends(self):
        assert "heos" in BACKENDS

    def test_dlna_in_backends(self):
        assert "dlna" in BACKENDS

    def test_local_in_backends(self):
        assert "local" in BACKENDS
