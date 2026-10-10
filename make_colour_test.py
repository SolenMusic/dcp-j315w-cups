#!/usr/bin/env python3
"""Create a small colour swatch PNG for end-to-end printer checks."""

import struct
import sys
import zlib


def chunk(tag, payload):
    return struct.pack(">I", len(payload)) + tag + payload + struct.pack(
        ">I", zlib.crc32(tag + payload)
    )


width, height = 1200, 800
colours = (
    (0, 0, 0), (255, 0, 0), (0, 255, 0), (0, 0, 255),
    (128, 128, 128), (0, 255, 255), (255, 0, 255), (255, 255, 0),
)
rows = bytearray()
for y in range(height):
    rows.append(0)  # PNG's no-filter row type
    for x in range(width):
        column = x // 300
        line = y // 400
        inside = 60 <= x % 300 < 240 and 75 <= y % 400 < 255
        rows.extend(colours[line * 4 + column] if inside else (255, 255, 255))

png = bytearray(b"\x89PNG\r\n\x1a\n")
png.extend(chunk(b"IHDR", struct.pack(">2I5B", width, height, 8, 2, 0, 0, 0)))
png.extend(chunk(b"IDAT", zlib.compress(rows, 9)))
png.extend(chunk(b"IEND", b""))
with open(sys.argv[1] if len(sys.argv) > 1 else "colour-test.png", "wb") as out:
    out.write(png)
