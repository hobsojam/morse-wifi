# morse-wifi

A cross-platform console app that converts text to Morse code audio and plays it on wireless speakers. Supports HEOS (Denon/Marantz), DLNA/UPnP, and local audio output.

Type a line of text, hit Enter, and the Morse code beeps play on your chosen speaker within a second or two. You can keep typing while it plays — lines queue automatically.

## Requirements

- Python 3.11+
- A speaker on the same local network (HEOS or any DLNA/UPnP MediaRenderer)
- `lameenc`, `sounddevice`, `numpy` (installed via requirements.txt)

```
pip install -r requirements-dev.txt
```

## Running

```
python main.py
```

On startup the app discovers speakers on your network, selects one automatically if only one is found, and asks for a playback speed. After that you get a prompt and can start typing.

```
Discovering speakers via HEOS...

Using speaker: Living Room

WPM (default 20):

Ready. Sending to: Living Room at 20 WPM
Commands: /wpm <n>  /backend heos|dlna|local  Ctrl+C to quit

> SOS
> Hello world
>
```

### Command-line options

| Flag | Effect |
|------|--------|
| `--backend heos` | Use HEOS protocol (default) |
| `--backend dlna` | Use DLNA/UPnP AV |
| `--backend local` | Play on this PC's audio output |
| `--debug` | Print Morse, URL, transport state for each transmission |

## Runtime commands

Type these at the `>` prompt:

| Command | Effect |
|---------|--------|
| `/wpm 15` | Change playback speed to 15 WPM |
| `/backend heos` | Switch to HEOS and rediscover speakers |
| `/backend dlna` | Switch to DLNA and rediscover speakers |
| `/backend local` | Switch to local audio output |

## What is WPM?

WPM (words per minute) controls how fast the Morse code plays — shorter dots and gaps mean faster playback. It has nothing to do with how fast you type. The calculation follows the PARIS standard, where one "word" is 50 dot-lengths. At 20 WPM each dot lasts 60ms, which is comfortable for a skilled operator. At 5 WPM it is slow enough for a beginner to follow.

## Queueing

If you submit a second line before the first has finished playing, the app waits for the right moment and then pushes the next sequence to the speaker with no gap. You do not need to wait.

## Architecture

The speaker backend is pluggable. `speaker.py` defines an abstract `Speaker` interface:

- `discover()` — find speakers on the network
- `play_url(speaker, url)` — tell a speaker to stream a URL
- `stop(speaker)` — stop playback

Three backends are implemented:

| Backend | File | Protocol |
|---------|------|----------|
| HEOS | `heos.py` | SSDP discovery + HEOS CLI over TCP 1255 |
| DLNA | `dlna.py` | SSDP discovery + UPnP AV SOAP (SetAVTransportURI / Play) |
| Local | `local_beeper.py` | Plays WAV directly on the PC via `sounddevice` |

Audio is generated in memory and served from a local HTTP server (`server.py`). The speaker fetches it by URL. WAV is used for HEOS and DLNA; the local backend also uses WAV.

### HEOS notes

The HEOS Bar (and similar soundbars) auto-switches audio to HDMI when a TV is on. The stream plays but the output is muted by the TV signal. Turn the TV off — or switch the Bar's input manually — to hear the Morse code.

## Running the tests

```
python -m pytest
```

108 tests covering Morse generation, WAV/MP3 encoding, the HTTP server, the speaker interface, HEOS protocol handling, DLNA SOAP/SSDP handling, and the main input loop. All network and audio I/O is mocked.
