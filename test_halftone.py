#!/usr/bin/env python3
"""Check tone conservation and remove the previous four-pixel repetition."""
from collections import Counter
from pathlib import Path
import sys


def patch(path):
    data = path.read_bytes()
    p = 4918
    region = -1
    pixels = bytearray(200 * 200)
    while data[p:p + 1] == b"F":
        assert data[p:p + 3] == b"F\x88\x0e"
        p += 3
        region += 1
        if data[p:p + 5] != b"ivT2\x01":
            continue
        p += 5
        for record in range(93 * 5):
            slot = record % 5
            command = data[p]
            p += 1
            if command == ord("Z"):
                continue
            assert command == ord("G") and slot != 3
            size = int.from_bytes(data[p:p + 2], "little")
            p += 2
            encoded = data[p:p + size]
            p += size
            q = 0
            line = bytearray()
            while q < size:
                value = encoded[q]
                q += 1
                count = value >> 5
                line.extend(bytes(value & 31))
                line.extend(encoded[q:q + count])
                q += count
                assert q <= size
            assert len(line) == 582
            phase = region % 4
            channel = 3 if slot == 4 else slot
            y = (region // 4 * 93 + record // 5 - (3 - phase) * 23) * 4 + phase
            if channel != 3:
                y -= 2
            for byte, value in enumerate(line):
                if not value:
                    continue
                for part in range(4):
                    code = (value >> (6 - part * 2)) & 3
                    if not code:
                        continue
                    x = byte * 4 + part
                    assert 200 <= x < 400 and 200 <= y < 400, "ink escaped into white margin"
                    pixels[(y - 200) * 200 + x - 200] |= code << (6 - channel * 2)
    assert data[p:] == b"\x0c\x1b@" + bytes(4096)
    return pixels


def repetition(pixels, dx, dy):
    total = equal = 0
    for y in range(20, 180 - dy):
        for x in range(20, 180 - dx):
            equal += pixels[y * 200 + x] == pixels[(y + dy) * 200 + x + dx]
            total += 1
    return equal / total


folder = Path(sys.argv[1])
ordered = patch(folder / "ordered.prn")
diffused = patch(folder / "diffused.prn")
for dx, dy in ((4, 0), (0, 4)):
    before = repetition(ordered, dx, dy)
    after = repetition(diffused, dx, dy)
    assert before == 1 and after < 0.9
    print(f"PASS: four-pixel repeat ({dx},{dy}) falls from {before:.1%} to {after:.1%}")

# Measured probabilities at the exact RGB 192/192/192 calibration node.
interior = [diffused[y * 200 + x] for y in range(20, 180) for x in range(20, 180)]
for channel, target in zip(range(4), (40 / 255, 30 / 255, 35 / 255, 6 / 255)):
    hist = Counter((pixel >> (6 - channel * 2)) & 3 for pixel in interior)
    mean = sum(code * count for code, count in hist.items()) / len(interior)
    assert abs(mean - target) < 0.0005, (channel, mean, target)
    print(f"PASS: {'CMYK'[channel]} mean code {mean:.4f} matches target {target:.4f}")
assert (folder / "black-diffused.prn").read_bytes() == (folder / "black-ordered.prn").read_bytes()
print("PASS: exact black/white output is unchanged and white margins remain clean")
