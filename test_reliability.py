#!/usr/bin/env python3
"""Check actual output framing, failure handling, and cancellation offline."""
from pathlib import Path
import signal
import os
import subprocess
import sys
import time
import hashlib
import json

root = Path(__file__).resolve().parent
fixtures = Path(sys.argv[1]) if len(sys.argv) > 1 else root / "fixtures"
binary = Path(os.environ.get("DCPJ315W_FILTER", root / "rastertodcpj315w"))
golden = json.loads((root / "fixtures/reliability-golden.json").read_text())
prologue = (root / "prologue_a4_300.bin").read_bytes()


def verify_stream(data):
    """Walk the protocol independently; require complete passes and final reset."""
    assert data[:4096] == bytes(4096)
    p = 4096
    pages = 0
    while True:
        header = prologue if pages == 0 else prologue[7:]
        assert data[p:p + len(header)] == header
        p += len(header)
        assert data[p:p + 2] == b"I1"
        p += 2
        while data[p:p + 1] == b"F":
            assert data[p:p + 3] == b"F\x10\x1d"
            p += 3
            if data[p:p + 5] == b"ivT2\x01":
                p += 5
                for _ in range(93 * 5):
                    command = data[p]
                    p += 1
                    if command == ord("Z"):
                        continue
                    assert command == ord("G")
                    size = int.from_bytes(data[p:p + 2], "little")
                    p += 2
                    payload = data[p:p + size]
                    assert len(payload) == size
                    p += size
                    q = decoded = 0
                    while q < size:
                        control = payload[q]
                        q += 1
                        literal = control >> 5
                        decoded += (control & 31) + literal
                        q += literal
                        assert q <= size
                    assert decoded == 1204
        assert data[p:p + 1] == b"\x0c"
        p += 1
        pages += 1
        if data[p:p + 2] == b"\x1b@":
            assert data[p + 2:] == bytes(4096)
            return pages


two = fixtures / "two-pages.ras"
dense = fixtures / "dense.ras"
if len(sys.argv) > 2:
    assert verify_stream(Path(sys.argv[2]).read_bytes()) == 4
    print("PASS: macOS pipeline produces four valid pages for two collated copies")
result = subprocess.run([binary, two], capture_output=True, check=True)
assert verify_stream(result.stdout) == 2
assert result.stderr.count(b"PAGE:") == 2
assert hashlib.sha256(result.stdout).hexdigest() == golden["two-pages.ras"]
print("PASS: two pages retain the independently checked baseline output")

for name in ("legacy150.ras", "colour-cube-600.ras"):
    output = subprocess.run([binary, root / "fixtures" / name], capture_output=True, check=True)
    assert hashlib.sha256(output.stdout).hexdigest() == golden[name]
    print(f"PASS: {name} matches the baseline exactly")

bad = subprocess.run([binary], input=dense.read_bytes()[:2000], capture_output=True)
assert bad.returncode == 1 and b"ERROR:" in bad.stderr and not bad.stdout
print("PASS: truncated first page fails clearly without printer output")

data = two.read_bytes()
second_header = data.find(data[4:1800], 1800)
assert second_header > 1800
for header_bytes in (1, 8, 32, 1795):
    bad = subprocess.run([binary], input=data[:second_header + header_bytes], capture_output=True)
    assert bad.returncode == 1 and b"ERROR:" in bad.stderr
    assert verify_stream(bad.stdout) == 1 and bad.stderr.count(b"PAGE:") == 1
print("PASS: partial later-page headers fail instead of silently losing pages")
bad = subprocess.run([binary], input=data[:-30], capture_output=True)
assert bad.returncode == 1 and b"Incomplete raster data on page 2" in bad.stderr
assert verify_stream(bad.stdout) == 1 and bad.stderr.count(b"PAGE:") == 1
print("PASS: later-page data failure resets the completed job without an extra eject")

process = subprocess.Popen([binary, dense], stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, bufsize=0)
prefix = bytearray()
while len(prefix) < 16000:
    block = process.stdout.read(16000 - len(prefix))
    assert block
    prefix.extend(block)
process.send_signal(signal.SIGTERM)
remaining, error = process.communicate(timeout=10)
assert process.returncode == 0 and b"cancelled" in error
assert verify_stream(prefix + remaining) == 1
assert b"PAGE:" not in error
print("PASS: cancellation finishes one complete pass and closes the partial page")

process = subprocess.Popen([binary], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE)
process.stdin.write(dense.read_bytes()[:32])
process.stdin.flush()
time.sleep(0.1)
process.send_signal(signal.SIGTERM)
try:
    process.wait(timeout=5)
except subprocess.TimeoutExpired:
    process.kill()
    process.wait()
    raise AssertionError("cancellation stayed blocked waiting for input")
process.stdin.close()
assert process.returncode == 0 and not process.stdout.read()
print("PASS: cancellation interrupts a blocked raster read")

process = subprocess.Popen([binary, dense], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
process.stdout.close()
process.wait(timeout=10)
assert process.returncode == 1 and b"ERROR:" in process.stderr.read()
print("PASS: a closed output pipe reports an error instead of a SIGPIPE crash")
