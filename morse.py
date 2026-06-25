import io
import math
import struct
import wave

import lameenc

SAMPLE_RATE = 44100
TONE_FREQ = 700
DEFAULT_WPM = 20

MORSE_TABLE = {
    'A': '.-',    'B': '-...',  'C': '-.-.',  'D': '-..',
    'E': '.',     'F': '..-.',  'G': '--.',   'H': '....',
    'I': '..',    'J': '.---',  'K': '-.-',   'L': '.-..',
    'M': '--',    'N': '-.',    'O': '---',   'P': '.--.',
    'Q': '--.-',  'R': '.-.',   'S': '...',   'T': '-',
    'U': '..-',   'V': '...-',  'W': '.--',   'X': '-..-',
    'Y': '-.--',  'Z': '--..',
    '0': '-----', '1': '.----', '2': '..---', '3': '...--',
    '4': '....-', '5': '.....', '6': '-....', '7': '--...',
    '8': '---..',  '9': '----.',
    '.': '.-.-.-', ',': '--..--', '?': '..--..', "'": '.----.',
    '!': '-.-.--', '/': '-..-.', '(': '-.--.',  ')': '-.--.-',
    '&': '.-...',  ':': '---...', ';': '-.-.-.', '=': '-...-',
    '+': '.-.-.',  '-': '-....-', '_': '..--.-', '"': '.-..-.',
    '$': '...-..-','@': '.--.-.', ' ': '/',
}


def text_to_morse(text: str) -> str:
    text = text.upper().strip()
    if not text:
        return ""
    parts = []
    for ch in text:
        code = MORSE_TABLE.get(ch)
        if code == '/':
            if parts and parts[-1] != '/':
                parts.append('/')
        elif code is not None:
            parts.append(code)
    result = ' '.join(parts)
    # collapse duplicate word gaps that may arise from multiple spaces
    while ' / /' in result:
        result = result.replace(' / /', ' /')
    return result.strip('/ ').strip()


def _dot_duration(wpm: int) -> float:
    # PARIS standard: 1 WPM = 1.2 seconds per dot
    return 1.2 / wpm


def calculate_duration(morse: str, wpm: int = DEFAULT_WPM) -> float:
    dot = _dot_duration(wpm)
    dash = dot * 3
    symbol_gap = dot
    letter_gap = dot * 3
    word_gap = dot * 7

    total = 0.0
    tokens = morse.split(' ')
    for i, token in enumerate(tokens):
        if token == '/':
            total += word_gap
            continue
        for j, symbol in enumerate(token):
            if symbol == '.':
                total += dot
            elif symbol == '-':
                total += dash
            if j < len(token) - 1:
                total += symbol_gap
        if i < len(tokens) - 1 and tokens[i + 1] != '/':
            total += letter_gap
    return total


def _generate_samples(morse: str, wpm: int) -> list[int]:
    dot = _dot_duration(wpm)
    dash = dot * 3
    symbol_gap = dot
    letter_gap = dot * 3
    word_gap = dot * 7

    def tone(duration: float) -> list[int]:
        n = int(SAMPLE_RATE * duration)
        # apply a short linear fade (5ms) to avoid clicks
        fade = min(int(SAMPLE_RATE * 0.005), n // 4)
        samples = []
        for i in range(n):
            amplitude = 0.8
            if i < fade:
                amplitude *= i / fade
            elif i >= n - fade:
                amplitude *= (n - i) / fade
            val = amplitude * math.sin(2 * math.pi * TONE_FREQ * i / SAMPLE_RATE)
            samples.append(int(val * 32767))
        return samples

    def silence(duration: float) -> list[int]:
        return [0] * int(SAMPLE_RATE * duration)

    samples: list[int] = []
    tokens = morse.split(' ')
    for i, token in enumerate(tokens):
        if token == '/':
            samples += silence(word_gap)
            continue
        for j, symbol in enumerate(token):
            if symbol == '.':
                samples += tone(dot)
            elif symbol == '-':
                samples += tone(dash)
            if j < len(token) - 1:
                samples += silence(symbol_gap)
        if i < len(tokens) - 1 and tokens[i + 1] != '/':
            samples += silence(letter_gap)
    return samples


def _inject_riff_info(wav_bytes: bytes, title: str) -> bytes:
    title_bytes = title.encode("utf-8") + b"\x00"
    if len(title_bytes) % 2:
        title_bytes += b"\x00"
    inam = b"INAM" + struct.pack("<I", len(title_bytes)) + title_bytes
    info = b"LIST" + struct.pack("<I", 4 + len(inam)) + b"INFO" + inam
    pos = wav_bytes.index(b"data")
    merged = wav_bytes[:pos] + info + wav_bytes[pos:]
    return merged[:4] + struct.pack("<I", len(merged) - 8) + merged[8:]


def morse_to_wav(morse: str, wpm: int = DEFAULT_WPM, title: str = "") -> bytes:
    samples = _generate_samples(morse, wpm) if morse.strip() else [0] * SAMPLE_RATE

    buf = io.BytesIO()
    with wave.open(buf, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(struct.pack(f'<{len(samples)}h', *samples))
    wav_bytes = buf.getvalue()
    if title:
        wav_bytes = _inject_riff_info(wav_bytes, title)
    return wav_bytes


def morse_to_mp3(morse: str, wpm: int = DEFAULT_WPM) -> bytes:
    samples = _generate_samples(morse, wpm) if morse.strip() else [0] * SAMPLE_RATE
    # interleave as stereo (L, R, L, R) — many HEOS devices reject mono MP3
    stereo = [s for sample in samples for s in (sample, sample)]
    pcm = struct.pack(f'<{len(stereo)}h', *stereo)

    encoder = lameenc.Encoder()
    encoder.set_bit_rate(128)
    encoder.set_in_sample_rate(SAMPLE_RATE)
    encoder.set_channels(2)
    encoder.set_quality(2)
    return bytes(encoder.encode(pcm) + encoder.flush())
