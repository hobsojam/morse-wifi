import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


def _local_ip() -> str:
    # Determine the LAN IP of this machine by asking the OS which local
    # interface it would route through to reach a public address (Google DNS,
    # 8.8.8.8). connect() on a UDP socket sends no packets — any routable
    # public IP would work here; 8.8.8.8 is just a stable, well-known choice.
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]


class AudioServer:
    def __init__(self, port: int = 0, debug: bool = False):
        self._audio: bytes | None = None
        self._content_type: str = "audio/wav"
        self._lock = threading.Lock()
        self._httpd: HTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._port = port
        self._debug = debug

    @property
    def port(self) -> int:
        if self._httpd is None:
            return self._port
        return self._httpd.server_address[1]

    def url(self, extension: str = "mp3") -> str:
        return f"http://{_local_ip()}:{self.port}/audio.{extension}"

    def set_audio(self, data: bytes, content_type: str = "audio/wav") -> None:
        with self._lock:
            self._audio = data
            self._content_type = content_type

    def _get_audio(self) -> tuple[bytes | None, str]:
        with self._lock:
            return self._audio, self._content_type

    def is_running(self) -> bool:
        return self._httpd is not None

    def start(self) -> None:
        server = self

        class Handler(BaseHTTPRequestHandler):
            def _send_audio_headers(self, data: bytes, content_type: str) -> None:
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Accept-Ranges", "bytes")
                self.end_headers()

            def do_HEAD(self):
                data, content_type = server._get_audio()
                if data is None:
                    self.send_response(204)
                    self.end_headers()
                    return
                self._send_audio_headers(data, content_type)

            def do_GET(self):
                data, content_type = server._get_audio()
                if data is None:
                    self.send_response(204)
                    self.end_headers()
                    return
                self._send_audio_headers(data, content_type)
                self.wfile.write(data)

            def log_message(self, format, *args):
                if server._debug:
                    print(f"  [debug] http: {self.client_address[0]} {format % args}")

        # Bind to all interfaces (0.0.0.0): the speaker is a separate device
        # on the LAN and must be able to fetch audio from this server, so
        # binding to loopback would break playback. While running, any host
        # on the local network can fetch the currently loaded audio.
        self._httpd = HTTPServer(("0.0.0.0", self._port), Handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd = None
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
