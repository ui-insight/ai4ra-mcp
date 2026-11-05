"""The speed test server (deploy/speedtest/speedtest.py), run as its own process and spoken to over real sockets, since
what matters is how it behaves when a client hangs up. deploy/speedtest/check.py runs the same promises through the
deployed proxy."""

import http.client
import os
import socket
import subprocess
import sys
import time
import zlib
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "deploy" / "speedtest" / "speedtest.py"
SECRET = "s3cret-" + "x" * 40
MIB = 1024 * 1024


class Running:
    def __init__(self, tmp_path, **env):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            self.port = probe.getsockname()[1]
        self.log_path = tmp_path / f"out-{self.port}.log"
        self.log_file = open(self.log_path, "w")
        self.process = subprocess.Popen(
            [sys.executable, "-u", str(SCRIPT)], stdout=self.log_file, stderr=subprocess.STDOUT,
            env={**os.environ, "SPEEDTEST_HOST": "127.0.0.1", "SPEEDTEST_PORT": str(self.port), "SPEEDTEST_SECRET": SECRET, **env})
        deadline = time.monotonic() + 10
        while True:
            try:
                socket.create_connection(("127.0.0.1", self.port), timeout=1).close()
                break
            except OSError:
                assert time.monotonic() < deadline, "server did not start"
                time.sleep(0.05)

    def stop(self):
        self.process.terminate()
        self.process.wait(10)
        self.log_file.close()

    def log(self):
        self.log_file.flush()
        return self.log_path.read_text()

    def request(self, method, path, body=None, headers=None):
        """Status, headers and the size and first bytes of the body."""
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        try:
            conn.request(method, path, body=body, headers=headers or {})
            r = conn.getresponse()
            data = r.read()
            return r.status, r.headers, data
        finally:
            conn.close()

    def open_upload(self, size, path=f"/speedtest/{SECRET}/up"):
        s = socket.create_connection(("127.0.0.1", self.port), timeout=30)
        s.sendall(f"POST {path} HTTP/1.1\r\nHost: x\r\nContent-Type: application/octet-stream\r\nContent-Length: {size}\r\n\r\n".encode())
        return s

    def open_download(self, size=10_000_000):
        s = socket.create_connection(("127.0.0.1", self.port), timeout=30)
        s.sendall(f"GET /speedtest/{SECRET}/down?bytes={size} HTTP/1.1\r\nHost: x\r\n\r\n".encode())
        return s

    def rss_kb(self):
        return int(subprocess.check_output(["ps", "-o", "rss=", "-p", str(self.process.pid)]).strip())


@pytest.fixture
def server(tmp_path):
    running = Running(tmp_path)
    yield running
    running.stop()


def wait_for_log(server, text, seconds=5):
    deadline = time.monotonic() + seconds
    while text not in server.log():
        assert time.monotonic() < deadline, f"{text!r} not logged in:\n{server.log()}"
        time.sleep(0.02)


# ---- download ----

@pytest.mark.parametrize("query,size", [("?bytes=0", 0), ("?bytes=1", 1), ("?bytes=1000000", 1_000_000), ("", 10_000_000),
                                        (f"?bytes={32 * MIB}", 32 * MIB), (f"?other=1&bytes=5", 5)])
def test_download_returns_exactly_what_was_asked(server, query, size):
    status, headers, data = server.request("GET", f"/speedtest/{SECRET}/down{query}")
    assert status == 200 and len(data) == size
    assert headers["Content-Length"] == str(size)
    assert headers["Content-Type"] == "application/octet-stream"
    assert headers["X-Speedtest-Server"] == "ai4ra-mcp"


def test_download_data_is_incompressible(server):
    _, _, data = server.request("GET", f"/speedtest/{SECRET}/down?bytes=3000000")
    assert len(zlib.compress(data[:500_000])) > 0.99 * 500_000


@pytest.mark.parametrize("value", ["", "abc", "-1", "%2B5", "1.5", "1_000", "%D9%A1%D9%A2", "0x10", str(32 * MIB + 1), "9" * 5000, "5&bytes=6"])
def test_download_refuses_a_bad_size(server, value):
    status, headers, data = server.request("GET", f"/speedtest/{SECRET}/down?bytes={value}")
    assert status == 400 and data == b""
    assert headers["X-Speedtest-Server"] == "ai4ra-mcp"


# ---- upload ----

def test_upload_reads_a_whole_body(server):
    status, headers, data = server.request("POST", f"/speedtest/{SECRET}/up", body=b"x" * 10_000_000,
                                           headers={"Content-Type": "application/octet-stream"})
    assert status == 200 and data.startswith(b"received 10000000 bytes")
    assert headers["X-Speedtest-Server"] == "ai4ra-mcp"
    assert len(data) < 100


def test_upload_at_the_cap_is_accepted(server):
    status, _, _ = server.request("POST", f"/speedtest/{SECRET}/up", body=b"x" * (32 * MIB))
    assert status == 200


def test_upload_timing_tracks_the_sender(server):
    """The body is read as it arrives: the server's own clock runs as long as the sender takes."""
    s = server.open_upload(300_000)
    for _ in range(3):
        s.sendall(b"x" * 100_000)
        time.sleep(0.4)
    answer = s.recv(4096)
    s.close()
    seconds = float(answer.split(b" in ")[1].split()[0])
    assert 0.7 < seconds < 2


def test_upload_over_the_cap_is_refused_without_reading_it(server):
    s = server.open_upload(32 * MIB + 1)
    started = time.monotonic()
    answer = s.recv(4096)
    assert answer.startswith(b"HTTP/1.1 413") and time.monotonic() - started < 1
    s.close()


def test_an_over_cap_reply_survives_a_sender_still_sending(server):
    """Closing with unread data can reset the connection and destroy the reply; the sender must still read it."""
    s = server.open_upload(40 * MIB)
    s.sendall(b"x" * 500_000)
    assert s.recv(4096).startswith(b"HTTP/1.1 413")
    s.close()


def test_upload_with_no_length_is_refused(server):
    status, _, _ = server.request("POST", f"/speedtest/{SECRET}/up", body=iter([b"abc"]), headers={"Transfer-Encoding": "chunked"})
    assert status == 411


def test_upload_never_stores_the_body(server):
    before = server.rss_kb()
    server.request("POST", f"/speedtest/{SECRET}/up", body=b"x" * (32 * MIB))
    assert server.rss_kb() - before < 5 * 1024


# ---- access control ----

@pytest.mark.parametrize("method,path", [
    ("GET", f"/speedtest/{SECRET}x/down"), ("POST", f"/speedtest/{SECRET}x/up"), ("GET", "/speedtest//down"),
    ("GET", f"/speedtest/{SECRET}/up"), ("POST", f"/speedtest/{SECRET}/down"), ("GET", f"/speedtest/{SECRET}"),
    ("GET", f"/speedtest/{SECRET}/down/"), ("GET", "/"), ("HEAD", f"/speedtest/{SECRET}/down"),
    ("PUT", f"/speedtest/{SECRET}/up"), ("OPTIONS", f"/speedtest/{SECRET}/up"), ("BREW", f"/speedtest/{SECRET}/up"),
])
def test_everything_else_is_a_plain_404(server, method, path):
    status, headers, data = server.request(method, path)
    assert status == 404 and data == b""
    assert "X-Speedtest-Server" not in headers and "Server" not in headers


def test_a_wrong_secret_with_a_large_body_still_gets_its_404(server):
    s = server.open_upload(10_000_000, path="/speedtest/wrong/up")
    s.sendall(b"x" * 500_000)
    assert s.recv(4096).startswith(b"HTTP/1.1 404")
    s.close()


@pytest.mark.parametrize("secret", ["", "short"])
def test_with_no_usable_secret_everything_is_a_404(tmp_path, secret):
    running = Running(tmp_path, SPEEDTEST_SECRET=secret)
    try:
        assert running.request("GET", f"/speedtest/{secret}/down?bytes=1")[0] == 404
        assert running.request("GET", "/speedtest//down?bytes=1")[0] == 404
    finally:
        running.stop()


# ---- early disconnects, slots, memory ----

def assert_quiet(server):
    log = server.log()
    assert "Traceback" not in log and "Error" not in log, log


def test_abandoned_transfers_free_their_slots(server):
    """Far more abandoned transfers than slots, one after another: later tests are never blocked."""
    for _ in range(10):
        s = server.open_download()
        s.recv(1000)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, b"\x01\x00\x00\x00\x00\x00\x00\x00")  # a reset, the rude way
        s.close()
        u = server.open_upload(10_000_000)
        u.sendall(b"x" * 100_000)
        u.close()
    wait_for_log(server, "client left")
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and server.log().count("client left") < 20:
        time.sleep(0.02)
    assert server.log().count("client left") == 20
    assert server.request("GET", f"/speedtest/{SECRET}/down?bytes=1000")[0] == 200
    assert server.request("POST", f"/speedtest/{SECRET}/up", body=b"x" * 1000)[0] == 200
    assert_quiet(server)


def test_a_fourth_transfer_gets_a_short_retry_after_then_a_slot_frees(server):
    held = [server.open_upload(10_000_000) for _ in range(3)]
    for s in held:
        s.sendall(b"x")
    time.sleep(0.2)
    status, headers, _ = server.request("GET", f"/speedtest/{SECRET}/down?bytes=1")
    assert status == 429 and int(headers["Retry-After"]) <= 10
    held.pop().close()
    deadline = time.monotonic() + 5
    while server.request("GET", f"/speedtest/{SECRET}/down?bytes=1")[0] != 200:
        assert time.monotonic() < deadline
        time.sleep(0.02)
    for s in held:
        s.close()


def test_a_reconnecting_device_is_not_locked_out_by_its_dead_connections(tmp_path):
    """Three connections left behind by a dead link, with no FIN and long before the idle timeout: the next test runs
    at once, with no 429, and the transfer it replaced ends quietly."""
    running = Running(tmp_path, SPEEDTEST_STALLED_S="0.3")
    try:
        dead = [running.open_upload(10_000_000), running.open_upload(10_000_000), running.open_download(32 * MIB)]
        time.sleep(0.6)
        started = time.monotonic()
        assert running.request("POST", f"/speedtest/{SECRET}/up", body=b"x" * 1000)[0] == 200
        assert running.request("GET", f"/speedtest/{SECRET}/down?bytes=1000")[0] == 200
        assert time.monotonic() - started < 1
        assert "replaced a stalled transfer" in running.log()
        assert "busy" not in running.log()
        for s in dead:
            s.close()
        assert_quiet(running)
    finally:
        running.stop()


def test_a_moving_transfer_keeps_its_slot(tmp_path):
    running = Running(tmp_path, SPEEDTEST_STALLED_S="0.5")
    try:
        moving = [running.open_upload(10_000_000) for _ in range(3)]
        finish = time.monotonic() + 1
        refused = False
        while time.monotonic() < finish:
            for s in moving:
                s.sendall(b"x" * 1000)
            time.sleep(0.05)
            if time.monotonic() > finish - 0.4:
                refused = running.request("GET", f"/speedtest/{SECRET}/down?bytes=1")[0] == 429
        assert refused and "replaced" not in running.log()
        for s in moving:
            s.close()
    finally:
        running.stop()


def test_a_wrong_secret_needs_no_slot(server):
    held = [server.open_upload(10_000_000) for _ in range(3)]
    time.sleep(0.2)
    assert server.request("GET", "/speedtest/wrong/down")[0] == 404
    for s in held:
        s.close()


def test_stalled_connections_close_and_free_their_slots(tmp_path):
    running = Running(tmp_path, SPEEDTEST_IDLE_S="0.5")
    try:
        up = running.open_upload(1000)  # never sends the body
        down = running.open_download(32 * MIB)  # never reads: the send fills the socket buffers and stalls
        silent = socket.create_connection(("127.0.0.1", running.port))  # never sends a request
        wait_for_log(running, "up 0/1000 bytes")
        deadline = time.monotonic() + 10
        while running.log().count(" idle") < 2:  # the upload's line comes first, the download's when its send times out
            assert time.monotonic() < deadline, running.log()
            time.sleep(0.02)
        assert running.request("POST", f"/speedtest/{SECRET}/up", body=b"x")[0] == 200
        for s in (up, down, silent):
            s.close()
        assert_quiet(running)
    finally:
        running.stop()


def test_a_trickle_cannot_hold_a_slot_past_the_limit(tmp_path):
    running = Running(tmp_path, SPEEDTEST_MAX_TRANSFER_S="0.3")
    try:
        s = running.open_upload(1000)
        try:
            for _ in range(10):
                s.sendall(b"x")
                time.sleep(0.1)
        except OSError:  # the server closing on the trickle is the point
            pass
        wait_for_log(running, "too long")
        s.close()
    finally:
        running.stop()


def test_memory_stays_flat_over_100_transfers(server):
    server.request("GET", f"/speedtest/{SECRET}/down?bytes=100000")
    baseline = server.rss_kb()
    for i in range(100):
        if i % 2:
            s = server.open_download(1_000_000)
            s.recv(1000)
            s.close()
        else:
            server.request("POST", f"/speedtest/{SECRET}/up", body=b"x" * 500_000)
    time.sleep(0.2)
    assert server.rss_kb() - baseline < 5 * 1024
    assert_quiet(server)


def test_the_secret_appears_in_no_output(server):
    server.request("GET", f"/speedtest/{SECRET}/down?bytes=10")
    server.request("GET", f"/speedtest/{SECRET}x/down")
    server.request("POST", f"/speedtest/{SECRET}/up", body=b"x")
    s = server.open_download(10_000_000)
    s.recv(100)
    s.close()
    wait_for_log(server, "client left")
    assert SECRET[:12] not in server.log()
    assert "up 1/1 bytes" in server.log()
