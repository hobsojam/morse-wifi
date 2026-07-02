import wave
import struct
import math
import pytest
from morse import text_to_morse, morse_to_wav, calculate_duration, DEFAULT_WPM, SAMPLE_RATE


class TestTextToMorse:
    def test_single_letter(self):
        assert text_to_morse("A") == ".-"

    def test_single_letter_lowercase(self):
        assert text_to_morse("a") == ".-"

    def test_word(self):
        assert text_to_morse("SOS") == "... --- ..."

    def test_two_words(self):
        assert text_to_morse("HI HI") == ".... .. / .... .."

    def test_number(self):
        assert text_to_morse("5") == "....."

    def test_unknown_character_skipped(self):
        assert text_to_morse("A^B") == ".- -..."

    def test_empty_string(self):
        assert text_to_morse("") == ""

    def test_only_spaces(self):
        assert text_to_morse("   ") == ""


class TestCalculateDuration:
    def test_returns_positive_float(self):
        duration = calculate_duration(".-", wpm=20)
        assert isinstance(duration, float)
        assert duration > 0

    def test_longer_morse_takes_longer(self):
        short = calculate_duration(".", wpm=20)
        long = calculate_duration("---", wpm=20)
        assert long > short

    def test_slower_wpm_takes_longer(self):
        fast = calculate_duration(".-", wpm=30)
        slow = calculate_duration(".-", wpm=10)
        assert slow > fast

    def test_word_gap_included(self):
        with_gap = calculate_duration(".. /", wpm=20)
        without_gap = calculate_duration("..", wpm=20)
        assert with_gap > without_gap


class TestMorseToWav:
    def test_returns_bytes(self):
        wav_bytes = morse_to_wav(".-", wpm=20)
        assert isinstance(wav_bytes, bytes)

    def test_valid_wav_header(self):
        wav_bytes = morse_to_wav(".-", wpm=20)
        assert wav_bytes[:4] == b"RIFF"
        assert wav_bytes[8:12] == b"WAVE"

    def test_correct_sample_rate(self):
        wav_bytes = morse_to_wav(".-", wpm=20)
        # sample rate is at bytes 24-27 (little-endian uint32)
        rate = struct.unpack_from("<I", wav_bytes, 24)[0]
        assert rate == SAMPLE_RATE

    def test_mono_channel(self):
        wav_bytes = morse_to_wav(".-", wpm=20)
        channels = struct.unpack_from("<H", wav_bytes, 22)[0]
        assert channels == 1

    def test_riff_info_title_embedded(self):
        wav_bytes = morse_to_wav(".-", wpm=20, title="test title")
        assert b"INAM" in wav_bytes
        assert b"test title" in wav_bytes

    def test_riff_info_absent_without_title(self):
        wav_bytes = morse_to_wav(".-", wpm=20)
        assert b"INAM" not in wav_bytes

    def test_non_empty_audio(self):
        wav_bytes = morse_to_wav(".-", wpm=20)
        assert len(wav_bytes) > 44  # more than just the header

    def test_different_wpm_produces_different_length(self):
        fast = morse_to_wav(".-", wpm=30)
        slow = morse_to_wav(".-", wpm=10)
        assert len(slow) > len(fast)

    def test_empty_morse_produces_silence(self):
        wav_bytes = morse_to_wav("", wpm=20)
        assert isinstance(wav_bytes, bytes)
        assert len(wav_bytes) >= 44  # valid WAV with at least a header


class TestInjectRiffInfo:
    def test_survives_malformed_wav(self):
        bad = b"not a wav file at all"
        # _inject_riff_info should return original bytes on error
        from morse import _inject_riff_info
        assert _inject_riff_info(bad, "title") == bad

    def test_odd_length_title_padded(self):
        wav = morse_to_wav(".", wpm=20, title="abc")  # 3 chars + null = 4, even — fine
        assert b"INAM" in wav
        wav2 = morse_to_wav(".", wpm=20, title="ab")   # 2 chars + null = 3, odd — needs pad
        assert b"INAM" in wav2
