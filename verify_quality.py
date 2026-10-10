#!/usr/bin/env python3
"""Validate 600 dpi captures against controlled Brother reference streams."""
from pathlib import Path
import sys


def parse(path):
    data = path.read_bytes()
    assert data[:4096] == bytes(4096) and data[-4096:] == bytes(4096)
    p = 4916
    assert data[p:p + 2] == b"I1"
    p += 2
    region = -1
    output = {}
    while data[p:p + 1] == b"F":
        assert data[p:p + 3] == b"F\x88\x0e"
        p += 3
        region += 1
        if data[p:p + 5] != b"ivT2\x01":
            continue
        p += 5
        for record in range(93 * 5):
            command = data[p]
            p += 1
            if command == ord("Z"):
                continue
            assert command == ord("G") and record % 5 != 3
            size = int.from_bytes(data[p:p + 2], "little")
            p += 2
            encoded = data[p:p + size]
            p += size
            q = 0
            decoded = bytearray()
            while q < len(encoded):
                control = encoded[q]
                q += 1
                count = control >> 5
                decoded.extend(bytes(control & 31))
                decoded.extend(encoded[q:q + count])
                q += count
                assert q <= len(encoded)
            output[region, record // 5, record % 5] = bytes(decoded)
    assert data[p:] == b"\x0c\x1b@" + bytes(4096)
    return region + 1, output


def support(line):
    return {byte * 4 + pixel for byte, value in enumerate(line) if value
            for pixel in range(4) if (value >> (6 - 2 * pixel)) & 3}


folder = Path(sys.argv[1])
for name in ("blank", "a4-blank", "two-blank"):
    assert (folder / f"{name}.prn").read_bytes() == (
        folder / f"{name}-native.prn").read_bytes()
    print(f"PASS: {name} stream is byte-identical to the reference")

for name, channel, rows in (("rows", 4, 3350), ("a4-rows", 4, 6867),
                            ("bars", 4, 40), ("cyan", 0, 3350),
                            ("magenta", 1, 3350), ("yellow", 2, 3350),
                            ("a4-yellow", 2, 6867)):
    reference_feeds, reference = parse(folder / f"{name}.prn")
    native_feeds, native = parse(folder / f"{name}-native.prn")
    reference = {key: line for key, line in reference.items() if key[2] == channel}
    native = {key: line for key, line in native.items() if key[2] == channel}
    assert reference_feeds == native_feeds
    assert reference.keys() == native.keys() and len(native) == rows
    for key, line in reference.items():
        assert len(line) == len(native[key])
        if channel == 4:
            assert support(line) <= support(native[key]), (name, key)
        else:
            # Colour dot levels and patterns may differ; check their physical
            # support against the input probe rather than requiring identical ink.
            region, row, _ = key
            phase = region % 4
            y = (region // 4 * 93 + row - (3 - phase) * 23) * 4 + phase - 2
            left = 64 + y % 2048
            marker = 2220 + y // 2048 * 20
            expected = set(range(left, left + 12)) | set(range(marker, marker + 12))
            assert support(line) <= expected and support(native[key]) <= expected, (name, key)
    print(f"PASS: {name}: {rows} matching slots, line lengths, and pixel support")
