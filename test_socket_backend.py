#!/usr/bin/env python3
"""Exercise the system raw-network backend against a local simulated printer.

Usage: python3 test_socket_backend.py controlled.prn output-directory
No physical printer is contacted and no CUPS queues are modified.
"""
from pathlib import Path
import os
import socket
import struct
import subprocess
import sys
import threading
import time

source = Path(sys.argv[1]).resolve()
output = Path(sys.argv[2]).resolve()
output.mkdir(parents=True, exist_ok=True)
backend_root = subprocess.check_output(["cups-config", "--serverbin"], text=True).strip()
backend = Path(backend_root) / "backend/socket"
expected = source.read_bytes()
assert len(expected) > 1024 * 1024, "use a sizeable controlled job for disconnect testing"


def run(name, initially_offline=False, disconnect=False):
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    listener.settimeout(45)
    received = bytearray()
    errors = []
    stop = threading.Event()
    first_refusal = threading.Event()
    listening = threading.Event()

    def serve():
        try:
            if initially_offline:
                deadline = time.monotonic() + 45
                while not first_refusal.wait(0.1):
                    if stop.is_set(): return
                    if time.monotonic() > deadline:
                        raise AssertionError("backend did not report an initial refused connection")
            listener.listen(1)
            listening.set()
            connection, _ = listener.accept()
            with connection:
                connection.settimeout(20)
                if disconnect:
                    received.extend(connection.recv(1024))
                    connection.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
                    return
                while True:
                    block = connection.recv(65536)
                    if not block:
                        break
                    received.extend(block)
        except Exception as error:
            errors.append(str(error))
        finally:
            listener.close()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    if not initially_offline:
        assert listening.wait(2)
    env = dict(os.environ, DEVICE_URI=f"socket://127.0.0.1:{port}/?contimeout=60&snmp=false",
               PRINTER="DCPJ315W_LocalTest", LC_ALL="C")
    process = subprocess.Popen([str(backend), "1", "tester", name, "1", "", str(source)],
                               env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    stderr = bytearray()

    def read_log():
        for line in iter(process.stderr.readline, b""):
            stderr.extend(line)
            if b"Connection error:" in line:
                first_refusal.set()

    logger = threading.Thread(target=read_log, daemon=True)
    logger.start()
    try:
        process.wait(timeout=55)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        logger.join(timeout=2)
        (output / f"{name}.log").write_bytes(stderr)
        raise AssertionError(f"{name}: backend did not finish")
    finally:
        stop.set()
        thread.join(timeout=2)
        logger.join(timeout=2)
        process.stderr.close()
        listener.close()
    (output / f"{name}.log").write_bytes(stderr)
    assert not errors, errors
    if disconnect:
        assert process.returncode != 0, "connection reset was reported as successful printing"
        assert 0 < len(received) < len(expected)
        print("PASS: mid-job connection reset reports failure, not success", flush=True)
    else:
        assert process.returncode == 0, (process.returncode, stderr.decode(errors="replace"))
        assert received == expected, "network delivery altered or truncated the job"
        if initially_offline:
            assert first_refusal.is_set(), "no initial connection failure was observed"
        print(f"PASS: {name}: exact job delivery", flush=True)


run("online")
run("initially-offline", initially_offline=True)
run("connection-reset", disconnect=True)
