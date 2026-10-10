#!/usr/bin/env python3
"""Verify metric/point raster variations retain the complete printer canvas."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
from inspect_protocol import inspect

root = Path(__file__).resolve().parent
binary = Path(os.environ.get("DCPJ315W_FILTER", root / "rastertodcpj315w"))
generator = Path(sys.argv[1])
cases = [("a5", 300, 1673, 2405), ("a5", 300, 1677, 2402),
         ("a5", 300, 1673, 2402), ("a5", 300, 1677, 2405),
         ("a4", 300, 2405, 3433), ("a6", 300, 1165, 1673),
         ("a6", 300, 1162, 1675), ("a5", 600, 3346, 4810),
         ("a4", 600, 4810, 6866), ("a6", 600, 2330, 3346)]
with tempfile.TemporaryDirectory(prefix="dcpj315w-geometry-") as temp:
    raster = Path(temp) / "probe.ras"
    for media, dpi, width, height in cases:
        with raster.open("wb") as out:
            subprocess.run([generator, str(width), str(height), str(dpi)], stdout=out, check=True)
        result = subprocess.run([binary, raster], capture_output=True)
        assert result.returncode == 0, result.stderr
        pages = inspect(result.stdout)
        assert len(pages) == 1 and pages[0]["media"] == media and pages[0]["dpi"] == dpi
        from inspect_protocol import PROFILES
        target_width, target_height, _, _ = PROFILES[media, dpi]
        assert pages[0]["bbox"] == [0, 0, target_width - 1, target_height - 1]
        assert b"Normalizing raster geometry" in result.stderr
        print(f"PASS: {media}/{dpi} {width}x{height}: complete canvas and framing", flush=True)
    with raster.open("wb") as out:
        subprocess.run([generator, "1600", "2405", "300"], stdout=out, check=True)
    result = subprocess.run([binary, raster], capture_output=True)
    assert result.returncode == 1 and b"Unsupported raster" in result.stderr and not result.stdout
    print("PASS: materially wrong/custom geometry remains rejected", flush=True)
