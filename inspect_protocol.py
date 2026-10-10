#!/usr/bin/env python3
"""Independently walk complete 300/600 dpi native jobs, without vendor software."""
import hashlib
import json
from pathlib import Path
import sys

PROFILES = {
    ("a4", 300): (2404, 3433, 1204, 38),
    ("a4", 600): (4808, 6867, 1202, 77),
    ("a5", 300): (1675, 2404, 840, 27),
    ("a5", 600): (3350, 4808, 838, 55),
    ("a6", 300): (1163, 1675, 584, 20),
    ("a6", 600): (2325, 3350, 582, 40),
    ("letter", 300): (2475, 3225, 1240, 36),
    ("letter", 600): (4950, 6450, 1238, 73),
}


def decode(encoded, expected):
    result = bytearray()
    p = 0
    while p < len(encoded):
        control = encoded[p]
        p += 1
        literals = control >> 5
        assert p + literals <= len(encoded), "truncated line"
        result.extend(bytes(control & 31))
        result.extend(encoded[p:p + literals])
        p += literals
        assert len(result) <= expected, "oversized decoded line"
    assert len(result) == expected, "incorrect line width"
    return result


def row_y(region, row, dpi, slot):
    if dpi == 600:
        phase = region % 4
        y = (region // 4 * 93 + row - (3 - phase) * 23) * 4 + phase
    elif region % 2:
        y = (region // 2 * 93 + row) * 2 + 1
    elif region == 0:
        y = (row - 46) * 2
    else:
        y = (47 + (region - 2) // 2 * 93 + row) * 2
    return y - (dpi // 300 if slot != 4 else 0)


def inspect(data, headers=None, preview_dir=None):
    root = Path(__file__).resolve().parent if headers is None else Path(headers)
    prologues = {key: (root / f"prologue_{key[0]}_{key[1]}.bin").read_bytes()
                 for key in PROFILES}
    assert data[:4096] == bytes(4096), "missing initial padding"
    p = 4096
    pages = []
    while True:
        skip = 0 if not pages else 7
        matching = [key for key, header in prologues.items()
                    if data[p:p + 820 - skip] == header[skip:]]
        assert len(matching) == 1, "unknown or ambiguous page header"
        size, dpi = matching[0]
        width, height, length, feeds = PROFILES[size, dpi]
        preview = None
        if preview_dir is not None:
            from PIL import Image
            preview = Image.new("L", ((width + 2) // 3, (height + 2) // 3), 255)
        p += 820 - skip
        begin = p
        assert data[p:p + 2] == b"I1"
        p += 2
        region = -1
        count = sum_x = sum_y = 0
        bbox = [width, height, -1, -1]
        slots = set()
        while data[p:p + 1] == b"F":
            assert data[p:p + 3] == (b"F\x10\x1d" if dpi == 300 else b"F\x88\x0e")
            p += 3
            region += 1
            if data[p:p + 5] != b"ivT2\x01":
                continue
            p += 5
            for record in range(93 * 5):
                command = data[p:p + 1]
                p += 1
                if command == b"Z":
                    continue
                slot = record % 5
                assert command == b"G" and slot != 3, "invalid nozzle record"
                encoded_size = int.from_bytes(data[p:p + 2], "little")
                p += 2
                assert p + encoded_size <= len(data)
                line = decode(data[p:p + encoded_size], length)
                p += encoded_size
                slots.add(slot)
                y = row_y(region, record // 5, dpi, slot)
                assert 0 <= y < height, "ink outside source page rows"
                bits = 4 if dpi == 300 else 2
                per_byte = 8 // bits
                for byte, value in enumerate(line):
                    if not value:
                        continue
                    for pixel in range(per_byte):
                        code = (value >> (8 - bits * (pixel + 1))) & ((1 << bits) - 1)
                        if not code:
                            continue
                        x = byte * per_byte + pixel
                        assert x < width, "ink outside source page columns"
                        if preview is not None:
                            preview.putpixel((x // 3, y // 3), 0)
                        count += 1
                        sum_x += x
                        sum_y += y
                        bbox = [min(bbox[0], x), min(bbox[1], y),
                                max(bbox[2], x), max(bbox[3], y)]
        assert region + 1 == feeds, "incomplete page feeds"
        body_hash = hashlib.sha256(data[begin:p]).hexdigest()
        assert data[p:p + 1] == b"\x0c", "missing page eject"
        p += 1
        pages.append({"media": size, "dpi": dpi, "feeds": feeds,
                      "body_hash": body_hash, "ink_pixels": count,
                      "bbox": bbox if count else None,
                      "centroid": [sum_x / count, sum_y / count] if count else None,
                      "slots": sorted(slots)})
        if preview is not None:
            destination = Path(preview_dir)
            destination.mkdir(parents=True, exist_ok=True)
            preview.save(destination / f"page-{len(pages)}.png")
        if data[p:p + 2] == b"\x1b@":
            assert data[p + 2:] == bytes(4096), "incorrect final reset/padding"
            return pages
        assert p < len(data), "truncated job"


if __name__ == "__main__":
    print(json.dumps(inspect(Path(sys.argv[1]).read_bytes()), indent=2))
