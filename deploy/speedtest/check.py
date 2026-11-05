#!/usr/bin/env python3
"""Checks the deployed speed test through its real public path. Standard library only; run it with no project set up.

    SPEEDTEST_BASE=https://<host>/speedtest/<secret> python3 deploy/speedtest/check.py \
        --also https://<host>/mcp/ --container ai4ra-speedtest

The base comes from the environment so the secret stays off the command line, and the output never prints it, so the
output can be pasted anywhere. --also names another service on the VM, polled during a transfer. --container reads
`docker stats` for memory, CPU and network, so it works only on the VM itself; a run from elsewhere skips those.
Exits nonzero when a check fails. Needs curl. Uses about 250 MB of transfer.
"""

import argparse
import http.client
import os
import shutil
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from urllib.parse import urlsplit

USER_AGENT = "satbox-dashboard/1"
TEN_MB = 10_000_000
MIB = 1024 * 1024
failures = []


def report(ok, name, detail=""):
    if not ok:
        failures.append(name)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}{': ' + detail if detail else ''}", flush=True)


class Target:
    def __init__(self, base):
        parts = urlsplit(base.rstrip("/"))
        self.https, self.netloc, self.path = parts.scheme == "https", parts.netloc, parts.path

    def connect(self, timeout=30):
        if self.https:  # certificates verified, as the client does
            return http.client.HTTPSConnection(self.netloc, timeout=timeout, context=ssl.create_default_context())
        return http.client.HTTPConnection(self.netloc, timeout=timeout)

    def fetch(self, route, read=True, path=None):
        conn = self.connect()
        try:
            conn.request("GET", path or f"{self.path}/{route}", headers={"User-Agent": USER_AGENT})
            r = conn.getresponse()
            size = len(r.read()) if read else None
            return r, size
        finally:
            conn.close()

    def start_upload(self, size, path=None):
        conn = self.connect()
        conn.putrequest("POST", path or f"{self.path}/up", skip_accept_encoding=True)
        conn.putheader("User-Agent", USER_AGENT)
        conn.putheader("Content-Type", "application/octet-stream")
        conn.putheader("Content-Length", str(size))
        conn.endheaders()
        return conn


def download(target, size=TEN_MB):
    started = time.monotonic()
    r, got = target.fetch(f"down?bytes={size}")
    seconds = time.monotonic() - started
    ok = r.status == 200 and got == size and r.headers["Content-Length"] == str(size) and not r.headers.get("Content-Encoding")
    report(ok, "download", f"{r.status}, {got} bytes, {seconds:.2f} s, {got / seconds / 1e6:.1f} MB/s, server {r.headers.get('X-Speedtest-Server')}")
    report(bool(r.headers.get("X-Speedtest-Server")), "identifying header present")


def upload(target, size=TEN_MB):
    started = time.monotonic()
    conn = target.start_upload(size)
    block = os.urandom(MIB)
    left = size
    while left:
        piece = block[:min(left, MIB)]
        conn.send(piece)
        left -= len(piece)
    r = conn.getresponse()
    body = r.read().decode(errors="replace").strip()
    conn.close()
    seconds = time.monotonic() - started
    report(r.status == 200 and body.startswith(f"received {size} bytes"), "upload", f"{r.status}, {seconds:.2f} s, {size / seconds / 1e6:.1f} MB/s, says: {body}")


def abandon_download(target, size=TEN_MB, read=64 * 1024):
    conn = target.connect()
    conn.request("GET", f"{target.path}/down?bytes={size}", headers={"User-Agent": USER_AGENT})
    r = conn.getresponse()
    status = r.status
    if status == 200:
        r.read(read)
    conn.sock.close() if conn.sock else None
    conn.close()
    return status


def abandon_upload(target, size=TEN_MB, send=256 * 1024):
    conn = target.start_upload(size)
    conn.send(b"x" * send)
    conn.sock.close()
    conn.close()


def curl(base, route, *options):
    """curl with the URL passed on stdin, so the secret stays out of the process list. Its exit code and output, the
    secret removed in case an error message ever repeats the URL."""
    done = subprocess.run(["curl", "-sS", *options, "--config", "-"], input=f'url = "{base}/{route}"\n', capture_output=True, text=True)
    secret = base.rsplit("/", 1)[1]
    return done.returncode, (done.stdout + done.stderr).replace(secret, "<secret>").strip()


def curl_checks(base, body_file):
    """The curl commands as the brief gives them. curl exits 28 when --max-time cuts it off."""
    upload_headers = ("-H", "Content-Type: application/octet-stream", "-H", "Expect:", "--data-binary", f"@{body_file}")
    down_format = "%{http_code} %{size_download} bytes %{speed_download} B/s"
    up_format = "%{http_code} %{size_upload} bytes %{speed_upload} B/s"

    def full_pair():
        code, out = curl(base, "down?bytes=10000000", "-o", "/dev/null", "-w", down_format)
        report(code == 0 and out.startswith("200 10000000 bytes"), "curl download", out)
        code, out = curl(base, "up", "-o", "/dev/null", "-w", up_format, *upload_headers)
        report(code == 0 and out.startswith("200 10000000 bytes"), "curl upload", out)

    full_pair()
    code_down, _ = curl(base, "down?bytes=10000000", "-o", "/dev/null", "--max-time", "1", "--limit-rate", "100k")
    code_up, _ = curl(base, "up", "-o", "/dev/null", "--max-time", "1", "--limit-rate", "100k", *upload_headers)
    report(code_down == 28 and code_up == 28, "curl hung up after 1 s both ways", f"exit codes {code_down}, {code_up}")
    full_pair()


def slow_upload_tracks_the_rate(base, body_file):
    """10 MB limited to 2 MB/s takes about 5 seconds, and the server reports how long it spent reading. A proxy that
    buffered the upload would hand it over in an instant at the end, and the server's clock would read near zero."""
    code, out = curl(base, "up", "--limit-rate", "2M", "-w", "|%{time_total}", "-H", "Content-Type: application/octet-stream",
                     "-H", "Expect:", "--data-binary", f"@{body_file}")
    try:
        body, sender = out.rsplit("|", 1)
        sender, server = float(sender), float(body.split(" in ")[1].split()[0])
    except (IndexError, ValueError):
        return report(False, "slow upload is not buffered", out)
    report(code == 0 and sender > 3.5 and server > 0.7 * sender, "slow upload is not buffered",
           f"limited to 2 MB/s: curl took {sender:.2f} s, the server read for {server:.2f} s")


def stats(container):
    """Memory in MiB, with the CPU and network text, from docker stats; None when docker cannot see the container."""
    if not container:
        return None
    try:
        out = subprocess.run(["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}|{{.CPUPerc}}|{{.NetIO}}", container],
                             capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0 or "|" not in out.stdout:
        return None
    memory, cpu, net = out.stdout.strip().split("|")
    used = memory.split("/")[0].strip()
    factor = 1 / 1024 if used.endswith("KiB") else 1024 if used.endswith("GiB") else 1
    return float(used.rstrip("KMGiB")) * factor, cpu, net


def watch_other_service(url, stop, times, errors):
    while not stop.is_set():
        started = time.monotonic()
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=10) as r:
                r.read()
            times.append(time.monotonic() - started)
        except OSError as e:
            errors.append(type(e).__name__)
        stop.wait(0.25)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--also", help="another service's URL, polled during a transfer")
    parser.add_argument("--container", help="the container's name, for docker stats")
    args = parser.parse_args()
    base = os.environ.get("SPEEDTEST_BASE")
    if not base:
        sys.exit("Set SPEEDTEST_BASE to https://<host>/speedtest/<secret>")
    target = Target(base)

    print("== full transfers ==", flush=True)
    download(target)
    upload(target)

    print("== hanging up early does no harm ==", flush=True)
    status = abandon_download(target)
    abandon_upload(target)
    report(status == 200, "abandoned one each way")
    time.sleep(1)
    download(target)
    upload(target)

    if not shutil.which("curl"):
        sys.exit("curl is needed for the rest of these checks")
    with tempfile.NamedTemporaryFile(prefix="speedtest-up-", suffix=".bin") as body_file:
        body_file.write(os.urandom(TEN_MB))
        body_file.flush()
        print("== the curl commands ==", flush=True)
        curl_checks(base.rstrip("/"), body_file.name)
        print("== buffering ==", flush=True)
        slow_upload_tracks_the_rate(base.rstrip("/"), body_file.name)

    print("== refusals ==", flush=True)
    secret = target.path.rsplit("/", 1)[1]
    wrong = target.path[: -len(secret)] + ("x" * len(secret))
    for route in ("down", "up"):
        r, body = target.fetch(route, path=f"{wrong}/{route}")
        report(r.status == 404 and body == 0 and not r.headers.get("X-Speedtest-Server"), f"wrong secret on {route} gets a plain 404", str(r.status))
    conn = target.start_upload(TEN_MB, path=f"{wrong}/up")
    conn.send(b"x" * 256 * 1024)
    r = conn.getresponse()
    report(r.status == 404, "wrong secret with an upload body gets a 404", str(r.status))
    conn.close()
    for value in ("abc", "-1", "", str(32 * MIB + 1)):
        r, _ = target.fetch(f"down?bytes={value}")
        report(r.status == 400, f"bytes={value or '(empty)'} gets 400", str(r.status))
    r, got = target.fetch(f"down?bytes={32 * MIB}")
    report(r.status == 200 and got == 32 * MIB, "bytes at the 32 MiB cap is allowed", f"{got} bytes")
    started = time.monotonic()
    conn = target.start_upload(32 * MIB + 1)
    conn.send(b"x" * 256 * 1024)
    r = conn.getresponse()
    seconds = time.monotonic() - started
    report(r.status == 413 and seconds < 5, "upload over the cap gets 413 without being read in full", f"{r.status} in {seconds:.2f} s")
    conn.close()

    print("== 100 abandoned transfers ==", flush=True)
    before = stats(args.container)
    refused = 0
    for i in range(100):
        if i % 2:
            abandon_upload(target, send=64 * 1024)
        elif abandon_download(target, read=16 * 1024) == 429:
            refused += 1
        time.sleep(0.2)
    time.sleep(1)
    after = stats(args.container)
    report(refused == 0, "no abandoned transfer held a slot against a later one", f"{refused} of 50 downloads got 429")
    download(target)
    upload(target)
    if before and after:
        report(after[0] - before[0] < 10, "memory stays flat", f"{before[0]:.1f} MiB before, {after[0]:.1f} MiB after")
    else:
        print("[SKIP] memory: no docker stats here (run on the VM with --container)", flush=True)

    print("== other services during a transfer ==", flush=True)
    stop, times, errors = threading.Event(), [], []
    watcher = None
    if args.also:
        watcher = threading.Thread(target=watch_other_service, args=(args.also, stop, times, errors), daemon=True)
        watcher.start()
    transfer = threading.Thread(target=lambda: (target.fetch(f"down?bytes={32 * MIB}"), target.fetch(f"down?bytes={32 * MIB}")))
    transfer.start()
    sample = stats(args.container)
    transfer.join()
    stop.set()
    if watcher:
        watcher.join()
        slowest = max(times) if times else 0
        report(bool(times) and not errors, "the other service answered throughout", f"{len(times)} polls, slowest {slowest:.3f} s, {len(errors)} errors")
    else:
        print("[SKIP] other service: pass --also", flush=True)
    if sample:
        print(f"[INFO] during a transfer: CPU {sample[1]}, memory {sample[0]:.1f} MiB, network so far {sample[2]}", flush=True)

    print(f"== {'ALL PASSED' if not failures else f'{len(failures)} FAILED: ' + '; '.join(failures)} ==", flush=True)
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
