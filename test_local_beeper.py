import io
import struct
import wave

import numpy as np
import pytest
from unittest.mock import patch, MagicMock

from speaker import SpeakerInfo
from local_beeper import LocalBeeper, _wav_bytes_to_array


def make_wav(num_frames: int = 100, sample_rate: int = 44100) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(struct.pack(f'<{num_frames}h', *([0] * num_frames)))
    return buf.getvalue()


DUMMY_WAV = make_wav()


class TestWavBytesToArray:
    def test_returns_numpy_array(self):
        audio, _ = _wav_bytes_to_array(DUMMY_WAV)
        assert isinstance(audio, np.ndarray)

    def test_returns_correct_sample_rate(self):
        _, sample_rate = _wav_bytes_to_array(DUMMY_WAV)
        assert sample_rate == 44100

    def test_correct_dtype_for_16bit(self):
        audio, _ = _wav_bytes_to_array(DUMMY_WAV)
        assert audio.dtype == np.int16

    def test_correct_frame_count(self):
        audio, _ = _wav_bytes_to_array(make_wav(num_frames=200))
        assert len(audio) == 200


class TestLocalBeeperFormat:
    def test_preferred_format_is_wav(self):
        assert LocalBeeper().preferred_format == "wav"


class TestLocalBeeperDiscover:
    def test_returns_one_speaker(self):
        assert len(LocalBeeper().discover()) == 1

    def test_speaker_name_is_descriptive(self):
        speaker = LocalBeeper().discover()[0]
        assert "local" in speaker.name.lower() or "beeper" in speaker.name.lower()

    def test_speaker_id_is_local(self):
        assert LocalBeeper().discover()[0].id == "local"


class TestLocalBeeperPlayUrl:
    def _mock_response(self):
        mock = MagicMock()
        mock.read.return_value = DUMMY_WAV
        mock.__enter__ = lambda s: s
        mock.__exit__ = MagicMock(return_value=False)
        return mock

    def test_fetches_url_and_plays(self):
        speaker = SpeakerInfo(id="local", name="Local Beeper")
        with patch("urllib.request.urlopen", return_value=self._mock_response()) as mock_open, \
             patch("sounddevice.play") as mock_play:
            LocalBeeper().play_url(speaker, "http://127.0.0.1:8080/audio.wav")

        mock_open.assert_called_once_with("http://127.0.0.1:8080/audio.wav")
        mock_play.assert_called_once()

    def test_passes_correct_sample_rate(self):
        speaker = SpeakerInfo(id="local", name="Local Beeper")
        with patch("urllib.request.urlopen", return_value=self._mock_response()), \
             patch("sounddevice.play") as mock_play:
            LocalBeeper().play_url(speaker, "http://127.0.0.1:8080/audio.wav")

        assert mock_play.call_args.kwargs["samplerate"] == 44100

    def test_passes_numpy_array(self):
        speaker = SpeakerInfo(id="local", name="Local Beeper")
        with patch("urllib.request.urlopen", return_value=self._mock_response()), \
             patch("sounddevice.play") as mock_play:
            LocalBeeper().play_url(speaker, "http://127.0.0.1:8080/audio.wav")

        audio_arg = mock_play.call_args.args[0]
        assert isinstance(audio_arg, np.ndarray)


class TestLocalBeeperStop:
    def test_stop_calls_sd_stop(self):
        speaker = SpeakerInfo(id="local", name="Local Beeper")
        with patch("sounddevice.stop") as mock_stop:
            LocalBeeper().stop(speaker)
        mock_stop.assert_called_once()
