#!/usr/bin/env python3
"""Verify Linux builds, controlled protocol output, failures and CUPS PDF input.

Runs offline without a printer or CUPS daemon. Dockerfile.linux-test supplies
the compiler and CUPS/GS PDF filters; install equivalent packages for a host run.
"""
import os
from pathlib import Path
import platform
import subprocess
import tempfile

from inspect_protocol import inspect

root = Path(__file__).resolve().parent
assert platform.system() == "Linux"
binary = root / "rastertodcpj315w"
print("Linux target:", platform.machine(), flush=True)
print(subprocess.check_output(["file", str(binary)], text=True).strip(), flush=True)
for script in ("test_reliability.py", "test_discovery.py", "test_status.py"):
    subprocess.run(["python3", str(root / script)], cwd=root, check=True)
with tempfile.TemporaryDirectory(prefix="dcpj315w-linux-") as temp:
    folder = Path(temp)
    ppd = folder / "native.ppd"
    ppd.write_text((root / "DCP-J315W-CUPS.ppd.in").read_text().replace("@FILTER@", str(binary)))
    subprocess.run(["cupstestppd", "-q", str(ppd)], check=True)
    for size in ("A4", "A5", "A6", "Letter"):
        for dpi, color in ((300, "Mono"), (600, "Color")):
            args = ["cupsfilter", "-e", "-p", str(ppd), "-i", "application/pdf",
                    "-m", "printer/foo", "-o", f"PageSize={size}", "-o", f"Resolution={dpi}dpi",
                    "-o", f"ColorModel={color}", "-o", "page-ranges=1", "-o", "fit-to-page=true",
                    str(root / "fixtures/print-options.pdf")]
            with (folder / f"{size}-{dpi}.log").open("wb") as log:
                result = subprocess.run(args, stdout=subprocess.PIPE, stderr=log, timeout=180)
            if result.returncode:
                print((folder / f"{size}-{dpi}.log").read_text(), flush=True)
            assert result.returncode == 0, (size, dpi, result.returncode)
            pages = inspect(result.stdout)
            assert len(pages) == 1 and pages[0]["media"] == size.lower() and pages[0]["dpi"] == dpi
            assert pages[0]["ink_pixels"] > 0
            assert pages[0]["slots"] == ([4] if color == "Mono" else [0, 1, 2, 4])
            print(f"PASS: Linux PDF pipeline {size}/{dpi}/{color}: valid complete page", flush=True)
    args = ["cupsfilter", "-e", "-p", str(ppd), "-i", "application/pdf", "-m", "printer/foo",
            "-n", "2", "-o", "PageSize=A4", "-o", "Resolution=300dpi", "-o", "ColorModel=Mono",
            "-o", "page-ranges=1-2", "-o", "Collate=True", str(root / "fixtures/print-options.pdf")]
    with (folder / "copies.log").open("wb") as log:
        result = subprocess.run(args, stdout=subprocess.PIPE, stderr=log, timeout=180)
    if result.returncode:
        print((folder / "copies.log").read_text(), flush=True)
    assert result.returncode == 0
    pages = inspect(result.stdout)
    assert len(pages) == 4
    hashes = [page["body_hash"] for page in pages]
    assert hashes[0] == hashes[2] and hashes[1] == hashes[3] and hashes[0] != hashes[1]
    print("PASS: Linux collated copies produce complete pages 1,2,1,2", flush=True)
print("LINUX VERIFICATION COMPLETE", flush=True)
