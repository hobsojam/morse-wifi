# morse-wifi

A Windows console app that converts text to Morse code audio and plays it on wireless speakers via the HEOS protocol (Denon/Marantz multi-room audio systems).

Type a line of text, hit Enter, and the Morse code beeps play on your chosen speaker within a second or two. You can keep typing while it plays — lines queue automatically.

## Requirements

- Python 3.11+
- A HEOS-compatible speaker (Denon or Marantz) on the same local network
- `sounddevice` and `numpy` (for local audio output)
- `pytest` (for running tests)

```
pip install -r requirements-dev.txt
```

No other third-party packages are required.

## Running

```
python main.py
```

On startup the app discovers HEOS speakers on your network, lists them, and asks you to pick one. It then asks for a playback speed (WPM). After that you get a prompt and can start typing.

```
Discovering speakers via HEOS...

Available speakers:
  1. Living Room
  2. Kitchen
Select speaker number: 1

WPM (default 20): 

Ready. Sending to: Living Room at 20 WPM
Commands: /wpm <n>  /backend heos|dlna  Ctrl+C to quit

> SOS
> Hello world
>
```

### Command-line options

```
python main.py --backend heos    # default
python main.py --backend local   # play on this PC's audio output (useful for testing)
python main.py --backend dlna    # DLNA stub, not yet implemented
```

## Runtime commands

Type these at the `>` prompt instead of text:

| Command | Effect |
|---------|--------|
| `/wpm 15` | Change playback speed to 15 WPM |
| `/backend heos` | Switch to HEOS backend and rediscover speakers |
| `/backend local` | Switch to local audio output |
| `/backend dlna` | Switch to DLNA backend (not yet implemented) |

## What is WPM?

WPM (words per minute) controls how fast the Morse code plays — shorter dots and gaps mean faster playback. It has nothing to do with how fast you type. The calculation follows the PARIS standard, where one "word" is 50 dot-lengths. At 20 WPM each dot lasts 60ms, which is comfortable for a skilled operator. At 5 WPM it is slow enough for a beginner to follow.

## Queueing

If you submit a second line before the first has finished playing, the app waits for the right moment and then pushes the next sequence to the speaker with no gap. You do not need to wait.

## Architecture

The speaker backend is pluggable. `speaker.py` defines an abstract `Speaker` interface with three methods:

- `discover()` — find speakers on the network
- `play_url(speaker, url)` — tell a speaker to stream a URL
- `stop(speaker)` — stop playback

`heos.py` implements this interface using SSDP discovery and the HEOS CLI protocol over TCP port 1255. `dlna.py` is a stub ready for a future DLNA/UPnP implementation. Switching backends at runtime with `/backend` re-runs discovery with the new backend.

Audio is generated in memory as a WAV file and served from a local HTTP server (`server.py`) so the speaker can fetch it by URL.

## Running the tests

```
python -m pytest
```

60 tests covering Morse generation, WAV encoding, the HTTP server, the speaker interface, HEOS protocol handling (with mocked network), and the main input loop.

## Future work

- DLNA/UPnP backend (implement `dlna.py`)
- `/speaker` runtime command to switch speaker without restarting
- Volume control
