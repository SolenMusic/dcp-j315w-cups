#!/usr/bin/env python3
"""Verify page selection/copy order and fitted geometry through macOS CUPS.

Usage: python3 test_print_options.py fixture.pdf temporary-output-directory
Set DCPJ315W_PPD to test a development PPD instead of the installed one.
No jobs are sent to a printer. No Brother software is required.
"""
import json
import os
from pathlib import Path
import subprocess
import sys

from inspect_protocol import inspect


def run(fixture, output):
    output.mkdir(parents=True, exist_ok=True)
    ppd = os.environ.get("DCPJ315W_PPD", "/Library/Printers/DCPJ315WCUPS/DCP-J315W-CUPS.ppd")
    command = ["cupsfilter", "-e", "-p", ppd, "-i", "application/pdf",
               "-m", "printer/foo", "-o", "PageSize=A4", "-o", "Resolution=300dpi",
               "-o", "ColorModel=Mono"]

    def capture(name, options):
        with (output / f"{name}.log").open("wb") as log:
            result = subprocess.run(command + options + [str(fixture)],
                                    stdout=subprocess.PIPE, stderr=log, check=True, timeout=120)
        (output / f"{name}.prn").write_bytes(result.stdout)
        pages = inspect(result.stdout)
        assert all(page["media"] == "a4" and page["dpi"] == 300 and
                   page["slots"] == [4] for page in pages)
        (output / f"{name}.json").write_text(json.dumps(pages, indent=2))
        return pages

    baseline = capture("baseline", [])
    assert len(baseline) == 4
    identities = [page["body_hash"] for page in baseline]
    assert len(set(identities)) == 4, "fixture pages must have distinct content"
    selected = capture("range", ["-o", "page-ranges=2-3"])
    assert [page["body_hash"] for page in selected] == identities[1:3]
    print("PASS: page range 2-3 selects exactly the corresponding source pages", flush=True)
    for collate, expected in (("True", identities[:2] * 2),
                              ("False", [identities[0]] * 2 + [identities[1]] * 2)):
        pages = capture(f"copies-{collate}", ["-n", "2", "-o", "page-ranges=1-2",
                                              "-o", f"Collate={collate}"])
        assert [page["body_hash"] for page in pages] == expected
        print(f"PASS: two copies, Collate={collate}, exact content/order and no blank sheet", flush=True)
    portrait = capture("fit-portrait", ["-o", "page-ranges=1", "-o", "fit-to-page=true"])
    assert len(portrait) == 1 and portrait[0]["body_hash"] == identities[0]
    fitted = capture("fit", ["-o", "page-ranges=3-4", "-o", "fit-to-page=true"])
    assert len(fitted) == 2
    for page, original in zip(fitted, baseline[2:]):
        assert page["body_hash"] != original["body_hash"]
        x0, y0, x1, y1 = page["bbox"]
        assert 0 < x0 < 160 and 0 < y0 < 160
        assert 2240 < x1 < 2403 and 3270 < y1 < 3432
        assert page["ink_pixels"] > original["ink_pixels"]
    print("PASS: landscape and oversized pages fit inside all four printable edges", flush=True)
    # Use a landscape source at actual size. macOS fit-to-page can choose its
    # own rotation, even when orientation-requested is supplied.
    rotated = capture("landscape", ["-o", "page-ranges=3", "-o", "orientation-requested=4"])
    assert len(rotated) == 1 and rotated[0]["body_hash"] != identities[2]
    x0, y0, x1, y1 = rotated[0]["bbox"]
    assert 0 < x0 < x1 < 2403 and 0 < y0 < y1 < 3432
    assert rotated[0]["bbox"] == baseline[0]["bbox"]
    print("PASS: landscape source at actual size has the complete frame after explicit rotation", flush=True)


if __name__ == "__main__":
    run(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())
