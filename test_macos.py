#!/usr/bin/env python3
"""Exercise Apple's PDF/CUPS pipeline offline using a development PPD."""
import os
from pathlib import Path
import platform
import subprocess
import tempfile

from inspect_protocol import inspect
from test_print_options import run

root = Path(__file__).resolve().parent
assert platform.system() == "Darwin"
binary = Path(os.environ.get("DCPJ315W_FILTER", root / "rastertodcpj315w")).resolve()
with tempfile.TemporaryDirectory(prefix="dcp-j315w-macos-") as tmp:
    folder = Path(tmp)
    ppd = folder / "driver.ppd"
    ppd.write_text((root / "DCP-J315W-CUPS.ppd.in").read_text().replace("@FILTER@", str(binary)))
    # A development executable is user-owned; install.sh checks the actual
    # root-owned filter separately after installation.
    subprocess.run(["cupstestppd", "-q", "-W", "filters", str(ppd)], check=True)
    os.environ["DCPJ315W_PPD"] = str(ppd)
    run(root / "fixtures/print-options.pdf", folder / "options")
    with (folder / "colour.log").open("wb") as log:
        result = subprocess.run(
            ["cupsfilter", "-e", "-p", str(ppd), "-i", "application/pdf", "-m", "printer/foo",
             "-o", "PageSize=A5", "-o", "Resolution=600dpi", "-o", "ColorModel=Color",
             "-o", "page-ranges=1", "-o", "fit-to-page=true", str(root / "fixtures/print-options.pdf")],
            stdout=subprocess.PIPE, stderr=log, timeout=180)
    if result.returncode:
        print((folder / "colour.log").read_text())
        result.check_returncode()
    pages = inspect(result.stdout)
    assert len(pages) == 1 and pages[0]["media"] == "a5" and pages[0]["dpi"] == 600
    assert pages[0]["slots"] == [0, 1, 2, 4]
    print("PASS: macOS A5/600 dpi colour PDF pipeline, all channels, complete framing")
