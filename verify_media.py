#!/usr/bin/env python3
"""Compare new media streams and colour row registration with reference data."""
from pathlib import Path
import sys


def parse(path, dpi, line_bytes):
    data = path.read_bytes()
    assert data[:4096] == bytes(4096) and data[-4096:] == bytes(4096)
    p = 4916
    assert data[p:p + 2] == b"I1"
    p += 2
    region = -1
    result = {}
    while data[p:p + 1] == b"F":
        assert data[p:p + 3] == (b"F\x10\x1d" if dpi == 300 else b"F\x88\x0e")
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
            line = bytearray()
            while q < size:
                control = encoded[q]
                q += 1
                count = control >> 5
                line.extend(bytes(control & 31))
                line.extend(encoded[q:q + count])
                q += count
                assert q <= size
            assert len(line) == line_bytes
            result[region, record // 5, record % 5] = line
    assert data[p:] == b"\x0c\x1b@" + bytes(4096)
    return region + 1, result


def support(line, dpi):
    bits = 4 if dpi == 300 else 2
    per_byte = 8 // bits
    return {byte * per_byte + pixel for byte, value in enumerate(line) if value
            for pixel in range(per_byte) if (value >> (8 - bits * (pixel + 1))) & ((1 << bits) - 1)}


def source_y(key, dpi):
    region, row, channel = key
    if dpi == 600:
        phase = region % 4
        y = (region // 4 * 93 + row - (3 - phase) * 23) * 4 + phase
    elif region % 2:
        y = (region // 2 * 93 + row) * 2 + 1
    elif region == 0:
        y = (row - 46) * 2
    else:
        y = (47 + (region - 2) // 2 * 93 + row) * 2
    return y - (dpi // 300 if channel != 4 else 0)


folder = Path(sys.argv[1])
cases = (("A5", 300, 1675, 2404, 840, 27), ("A5", 600, 3350, 4808, 838, 55),
         ("Letter", 300, 2475, 3225, 1240, 36), ("Letter", 600, 4950, 6450, 1238, 73),
         ("A4", 300, 2404, 3433, 1204, 38), ("A6", 300, 1163, 1675, 584, 20))
for size, dpi, width, height, length, feeds in cases:
    prefix = folder / f"{size}-{dpi}"
    if size in ("A5", "Letter"):
        assert Path(f"{prefix}-blank-native.prn").read_bytes() == Path(f"{prefix}-blank-reference.prn").read_bytes()
        print(f"PASS: {size}/{dpi} blank stream matches reference exactly")
    probes = (("rows", 4), ("yellow", 2)) if size in ("A5", "Letter") else (("yellow", 2),)
    for probe, channel in probes:
        rf, reference = parse(Path(f"{prefix}-{probe}-reference.prn"), dpi, length)
        nf, native = parse(Path(f"{prefix}-{probe}-native.prn"), dpi, length)
        assert rf == nf == feeds
        reference = {key: line for key, line in reference.items() if key[2] == channel}
        native = {key: line for key, line in native.items() if key[2] == channel}
        assert reference.keys() == native.keys() and len(native) == height
        ys = set()
        period = 512 if width < 1600 else 1024
        for key in reference:
            y = source_y(key, dpi)
            assert 0 <= y < height
            ys.add(y)
            left = 16 + y % period
            marker = (700 if width < 1600 else 1400) + y // period * 32
            expected = set(range(left, left + 16)) | set(range(marker, marker + 16))
            assert support(reference[key], dpi) <= expected
            assert support(native[key], dpi) <= expected
        assert ys == set(range(height))
        print(f"PASS: {size}/{dpi} {probe}: all {height} rows, slots, and horizontal support match")
    if size in ("A5", "Letter"):
        rf, reference = parse(Path(f"{prefix}-edges-reference.prn"), dpi, length)
        nf, native = parse(Path(f"{prefix}-edges-native.prn"), dpi, length)
        assert rf == nf == feeds and reference.keys() == native.keys()
        assert len(native) == height and all(key[2] == 4 for key in native)
        # Older captures use a two-pixel frame at both resolutions.
        # Derive thickness from an interior source row so either fixture works.
        interior = next(line for key, line in native.items() if source_y(key, dpi) == height // 2)
        thickness = len(support(interior, dpi)) // 2
        assert 0 < thickness <= dpi // 150
        ys = set()
        for key in native:
            y = source_y(key, dpi)
            assert 0 <= y < height
            ys.add(y)
            expected = (set(range(width)) if y < thickness or y >= height - thickness
                        else set(range(thickness)) | set(range(width - thickness, width)))
            assert support(reference[key], dpi) == support(native[key], dpi) == expected
        assert ys == set(range(height))
        print(f"PASS: {size}/{dpi} complete border: every printed pixel location matches reference")
