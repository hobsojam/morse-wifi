import argparse
import threading
import time
from typing import Callable, TypedDict

from dlna import DlnaBackend
from heos import HeosBackend
from local_beeper import LocalBeeper
from morse import text_to_morse, morse_to_wav, calculate_duration, DEFAULT_WPM
from server import AudioServer
from speaker import Speaker, SpeakerInfo

BACKENDS: dict[str, Callable[[], Speaker]] = {
    "heos": HeosBackend,
    "dlna": DlnaBackend,
    "local": LocalBeeper,
}


class AppState(TypedDict):
    wpm: int
    backend_name: str
    backend: Speaker
    speaker: SpeakerInfo
    busy_until: float
    debug: bool


def select_speaker(speakers: list[SpeakerInfo]) -> SpeakerInfo:
    if len(speakers) == 1:
        print(f"\nUsing speaker: {speakers[0].name}")
        return speakers[0]
    print("\nAvailable speakers:")
    for i, s in enumerate(speakers, 1):
        print(f"  {i}. {s.name}")
    while True:
        raw = input("Select speaker number: ").strip()
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(speakers):
                return speakers[idx]
        print(f"  Please enter a number between 1 and {len(speakers)}.")


def prompt_wpm() -> int:
    while True:
        raw = input(f"WPM (default {DEFAULT_WPM}): ").strip()
        if raw == "":
            return DEFAULT_WPM
        if raw.isdigit() and int(raw) > 0:
            return int(raw)
        print("  Please enter a positive integer.")


def handle_command(line: str, state: AppState) -> bool:
    parts = line.strip().split()
    cmd = parts[0].lower()

    if cmd == "/wpm":
        if len(parts) == 2 and parts[1].isdigit() and int(parts[1]) > 0:
            state["wpm"] = int(parts[1])
            print(f"  WPM set to {state['wpm']}")
            return True
        print("  Usage: /wpm <positive integer>")
        return False

    if cmd == "/backend":
        if len(parts) == 2 and parts[1].lower() in BACKENDS:
            name = parts[1].lower()
            new_backend = BACKENDS[name]()
            print(f"  Discovering speakers via {name.upper()}...")
            speakers = new_backend.discover()
            if not speakers:
                print(f"  No speakers found via {name.upper()}.")
                return False
            speaker = select_speaker(speakers)
            state["backend_name"] = name
            state["backend"] = new_backend
            state["speaker"] = speaker
            print(f"  Now sending to: {speaker.name}")
            return True
        print(f"  Unknown backend. Available: {', '.join(BACKENDS)}")
        return False

    print(f"  Unknown command: {cmd}")
    return False


def _debug_poll_play_state(backend: Speaker, speaker: SpeakerInfo, timeout: float) -> None:
    def _poll():
        for key, val in backend.get_debug_info(speaker).items():
            print(f"  [debug] {key}: {val}")
        deadline = time.monotonic() + timeout + 5.0
        elapsed = 0
        while time.monotonic() < deadline:
            time.sleep(1.0)
            elapsed += 1
            try:
                state = backend.get_transport_state(speaker)
            except Exception as exc:
                print(f"  [debug] play state at {elapsed}s: error ({exc})")
                return
            print(f"  [debug] play state at {elapsed}s: {state}")
            if state in ("stopped", "error"):
                return
    threading.Thread(target=_poll, daemon=True).start()


def process_input(
    text: str,
    speaker: SpeakerInfo,
    backend: Speaker,
    server: AudioServer,
    wpm: int,
    state: AppState,
) -> None:
    text = text.strip()
    if not text:
        return

    morse = text_to_morse(text)
    duration = calculate_duration(morse, wpm=wpm)
    audio = morse_to_wav(morse, wpm=wpm, title=text)

    now = time.monotonic()
    wait = state["busy_until"] - now
    if wait > 0:
        time.sleep(wait)

    url = server.url(extension="wav")
    if state.get("debug"):
        print(f"  [debug] morse:        {morse}")
        print(f"  [debug] url:          {url}")
        print("  [debug] content-type: audio/wav")
    server.set_audio(audio, "audio/wav")
    backend.play_url(speaker, url)
    state["busy_until"] = time.monotonic() + duration
    if state.get("debug"):
        _debug_poll_play_state(backend, speaker, timeout=duration)


def main() -> None:
    parser = argparse.ArgumentParser(description="Morse code over HEOS/DLNA")
    parser.add_argument("--backend", choices=BACKENDS.keys(), default="heos")
    parser.add_argument("--debug", action="store_true", help="Print URL and morse for each transmission")
    args = parser.parse_args()

    backend_name = args.backend
    backend = BACKENDS[backend_name]()

    server = AudioServer(debug=args.debug)
    server.start()

    print(f"Discovering speakers via {backend_name.upper()}...")
    speakers = backend.discover()

    if not speakers:
        print("No speakers found. Check your network and try again.")
        server.stop()
        return

    speaker = select_speaker(speakers)
    wpm = prompt_wpm()

    state: AppState = {
        "wpm": wpm,
        "backend_name": backend_name,
        "backend": backend,
        "speaker": speaker,
        "busy_until": 0.0,
        "debug": args.debug,
    }

    print(f"\nReady. Sending to: {speaker.name} at {wpm} WPM")
    print("Commands: /wpm <n>  /backend heos|dlna|local  Ctrl+C to quit\n")

    try:
        while True:
            line = input("> ").strip()
            if not line:
                continue
            if line.startswith("/"):
                handle_command(line, state)
            else:
                process_input(
                    line,
                    state["speaker"],
                    state["backend"],
                    server,
                    state["wpm"],
                    state,
                )
    except KeyboardInterrupt:
        print("\nBye.")
    finally:
        server.stop()


if __name__ == "__main__":
    main()
