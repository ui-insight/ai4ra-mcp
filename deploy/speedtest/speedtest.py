"""A private speed test for one remote field device. Standard library only; not an MCP server, and it shares
the host with the rest of this repository and nothing else.

    GET  /speedtest/<secret>/down?bytes=N   N random bytes, 0 to 32 MiB, 10,000,000 when bytes is absent
    POST /speedtest/<secret>/up             reads and discards the body, up to 32 MiB

Anything else, a wrong secret included, is an empty 404. Nothing is stored. One line per transfer goes to stdout,
with no path, address or secret. A client hanging up part way is the normal case, not an error.
"""

import hmac
import os
import re
import signal
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

SERVER_NAME = "ai4ra-mcp"  # the X-Speedtest-Server header, so the client can log which server it used
MAX_BYTES = 32 * 1024 * 1024
DEFAULT_BYTES = 10_000_000
CHUNK = 64 * 1024
MIN_SECRET = 32

SECRET = os.environ.get("SPEEDTEST_SECRET", "")
MAX_TRANSFERS = int(os.environ.get("SPEEDTEST_MAX_TRANSFERS", "3"))
# A stalled connection closes after this long. Above the client's own 15 seconds of silence on a download, and short
# enough that a link that died without a FIN frees its slot quickly.
IDLE_S = float(os.environ.get("SPEEDTEST_IDLE_S", "20"))
MAX_TRANSFER_S = float(os.environ.get("SPEEDTEST_MAX_TRANSFER_S", "120"))  # frees a slot held by a trickle
STALLED_S = float(os.environ.get("SPEEDTEST_STALLED_S", "2"))  # no bytes for this long and a new transfer may take the slot
RETRY_AFTER_S = 5  # a pause loses field data, and a slot frees within IDLE_S
MAX_CONNECTIONS = 16  # threads, unauthenticated ones included
LINGER_S = 1.0  # how long an early reply waits for the proxy to read it before the socket closes
LINGER_BYTES = 1024 * 1024

BLOCK = os.urandom(1024 * 1024)  # incompressible, and reused so memory stays fixed
BYTES_VALUE = re.compile(r"[0-9]{1,9}", re.ASCII)
active: dict[socket.socket, float] = {}  # each transfer's connection and when it last moved a byte
active_lock = threading.Lock()


def log(line: str) -> None:
    print(line, flush=True)


def claim_slot(connection: socket.socket) -> bool:
    """A slot for this transfer. When all are taken, the one stalled longest gives up its slot: the device reconnects
    at any time and abandons earlier connections, and over a dead link the proxy may not learn of that until IDLE_S.
    False, a 429, only when every transfer is really moving."""
    with active_lock:
        now = time.monotonic()
        if len(active) >= MAX_TRANSFERS:
            stalled = min(active, key=active.__getitem__)
            if now - active[stalled] < STALLED_S:
                return False
            del active[stalled]
            try:
                stalled.shutdown(socket.SHUT_RDWR)  # wakes its thread, which ends as if the client had left
            except OSError:
                pass
            log("replaced a stalled transfer")
        active[connection] = now
        return True


def release_slot(connection: socket.socket) -> None:
    with active_lock:
        active.pop(connection, None)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"  # exact Content-Length and a clean close; every response closes its connection
    timeout = IDLE_S  # socket timeout on every read and write
    disable_nagle_algorithm = True

    def handle(self):
        try:
            super().handle()
        except OSError:  # the peer went away before or between responses
            self.close_connection = True

    def log_message(self, format, *args):  # http.server logs the request line, which holds the secret
        pass

    def send_error(self, code, message=None, explain=None):  # also an unknown method and an unparsable request
        self._reply(404, identify=False)

    def _reply(self, status, body=b"", headers=(), identify=True):
        self.send_response_only(status)
        if identify:
            self.send_header("X-Speedtest-Server", SERVER_NAME)
        for name, value in headers:
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _route(self, method_route):
        """The route when the path and method are right and the secret matches; otherwise a 404 and None."""
        path, _, self.query = self.path.partition("?")
        parts = path.split("/")
        if (SECRET and len(parts) == 4 and parts[1] == "speedtest" and parts[3] == method_route
                and hmac.compare_digest(parts[2].encode(), SECRET.encode())):
            return parts[3]
        self._reply(404, identify=False)
        return None

    def _refuse_body(self, status, body=b"", headers=()):
        """Answer without reading the body. Closing a socket with unread data resets it, which can destroy the reply
        before the proxy reads it, so half-close first and drain briefly: never the whole body."""
        self._reply(status, body, headers)
        self._linger()

    def _linger(self):
        try:
            self.connection.shutdown(socket.SHUT_WR)
            self.connection.settimeout(LINGER_S)
            deadline, drained = time.monotonic() + LINGER_S, 0
            while drained < LINGER_BYTES and time.monotonic() < deadline:
                got = self.rfile.read1(CHUNK)
                if not got:
                    break
                drained += len(got)
        except OSError:
            pass

    def _no_slot(self):
        log("busy: no free transfer slot")
        return [("Retry-After", str(RETRY_AFTER_S))]

    def do_GET(self):
        if not self._route("down"):
            return
        values = parse_qs(self.query, keep_blank_values=True).get("bytes", [str(DEFAULT_BYTES)])
        if len(values) != 1 or not BYTES_VALUE.fullmatch(values[0]) or int(values[0]) > MAX_BYTES:
            return self._reply(400)
        size = int(values[0])
        if not claim_slot(self.connection):
            return self._reply(429, headers=self._no_slot())
        start, sent, end = time.monotonic(), 0, "complete"
        try:
            self.send_response_only(200)
            self.send_header("X-Speedtest-Server", SERVER_NAME)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(size))
            self.send_header("Cache-Control", "no-store, no-transform")
            self.send_header("Connection", "close")
            self.end_headers()
            view = memoryview(BLOCK)
            while sent < size:
                if time.monotonic() - start > MAX_TRANSFER_S:
                    end = "too long"
                    break
                offset = sent % len(BLOCK)
                piece = view[offset:offset + min(CHUNK, size - sent, len(BLOCK) - offset)]
                self.connection.sendall(piece)
                sent += len(piece)
                active[self.connection] = time.monotonic()
        except TimeoutError:
            end = "idle"
        except OSError:
            end = "client left"
        finally:
            release_slot(self.connection)
            self.close_connection = True
        log(f"down {sent}/{size} bytes {time.monotonic() - start:.2f}s {end}")

    def do_POST(self):
        if not self._route("up"):
            return self._linger()
        declared = self.headers.get("Content-Length", "")
        if not BYTES_VALUE.fullmatch(declared):
            if declared.isdigit():  # too many digits to be under the cap
                return self._refuse_body(413)
            return self._refuse_body(411)
        size = int(declared)
        if size > MAX_BYTES:
            return self._refuse_body(413)
        if not claim_slot(self.connection):
            return self._refuse_body(429, headers=self._no_slot())
        start, received, end = time.monotonic(), 0, "complete"
        buffer = memoryview(bytearray(CHUNK))
        try:
            while received < size:
                if time.monotonic() - start > MAX_TRANSFER_S:
                    end = "too long"
                    break
                got = self.rfile.readinto1(buffer[:min(CHUNK, size - received)])
                if not got:
                    end = "client left"
                    break
                received += got
                active[self.connection] = time.monotonic()
        except TimeoutError:
            end = "idle"
        except OSError:
            end = "client left"
        finally:
            release_slot(self.connection)
            self.close_connection = True
        seconds = time.monotonic() - start
        log(f"up {received}/{size} bytes {seconds:.2f}s {end}")
        if end == "complete":
            self._reply(200, f"received {received} bytes in {seconds:.3f} s\n".encode(), [("Content-Type", "text/plain")])

    def _not_found(self):
        self._reply(404, identify=False)
        if self.headers.get("Content-Length", "0") != "0":
            self._linger()

    do_HEAD = do_PUT = do_DELETE = do_OPTIONS = do_PATCH = _not_found


class Server(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False
    request_queue_size = 16

    def verify_request(self, request, client_address):
        return threading.active_count() <= MAX_CONNECTIONS

    def handle_error(self, request, client_address):  # no stack traces: a hangup is normal and handled above
        log(f"connection ended: {type(sys.exc_info()[1]).__name__}")


def main():
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    os.nice(10)
    global SECRET
    if len(SECRET) < MIN_SECRET:
        log(f"SPEEDTEST_SECRET is missing or under {MIN_SECRET} characters: every request gets a 404")
        SECRET = ""
    server = Server((os.environ.get("SPEEDTEST_HOST", "0.0.0.0"), int(os.environ.get("SPEEDTEST_PORT", "8080"))), Handler)
    log(f"speedtest listening on port {server.server_address[1]}, {MAX_TRANSFERS} transfers at a time")
    server.serve_forever()


if __name__ == "__main__":
    main()
