import io
import urllib.request
import wave

import numpy as np
import sounddevice as sd

from speaker import Speaker, SpeakerInfo

_LOCAL_SPEAKER = SpeakerInfo(id="local", name="Local Beeper")


def _wav_bytes_to_array(data: bytes) -> tuple[np.ndarray, int]:
    with wave.open(io.BytesIO(data)) as w:
        frames = w.readframes(w.getnframes())
        sample_rate = w.getframerate()
        n_channels = w.getnchannels()
        sample_width = w.getsampwidth()
    dtype = {1: np.int8, 2: np.int16, 4: np.int32}[sample_width]
    audio = np.frombuffer(frames, dtype=dtype)
    if n_channels > 1:
        audio = audio.reshape(-1, n_channels)
    return audio, sample_rate


class LocalBeeper(Speaker):
    preferred_format = "wav"

    def discover(self) -> list[SpeakerInfo]:
        return [_LOCAL_SPEAKER]

    def play_url(self, speaker: SpeakerInfo, url: str) -> None:
        with urllib.request.urlopen(url) as response:
            data = response.read()
        audio, sample_rate = _wav_bytes_to_array(data)
        sd.play(audio, samplerate=sample_rate)

    def stop(self, speaker: SpeakerInfo) -> None:
        sd.stop()
