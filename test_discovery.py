#!/usr/bin/env python3
"""Check discovery selection using controlled CUPS listings, no network needed."""
import os
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parent
record = """Device: uri = dnssd://Brother%20DCP-J315W._pdl-datastream._tcp.local./
        class = network
        info = Brother DCP-J315W
        make-and-model = Brother DCP-J315W
        device-id = MFG:Brother;MDL:DCP-J315W;
        location =
"""
with tempfile.TemporaryDirectory(prefix="dcpj315w-discovery-") as temp:
    folder = Path(temp)
    stub = folder / "lpinfo"
    stub.write_text("#!/bin/sh\ncat \"$DCPJ315W_DISCOVERY_LIST\"\n")
    stub.chmod(0o755)
    listing = folder / "devices.txt"
    env = dict(os.environ, PATH=str(folder) + os.pathsep + os.environ["PATH"],
               DCPJ315W_DISCOVERY_LIST=str(listing))
    command = [str(root / "discover.sh"), "--uri-only", "--timeout", "1"]
    listing.write_text(record + record)  # Same device may be reported twice.
    result = subprocess.run(command, env=env, capture_output=True, text=True)
    expected = record.splitlines()[0].split(" = ", 1)[1]
    assert result.returncode == 0 and result.stdout.strip() == expected
    print("PASS: matching printer selected, duplicate reports collapsed")
    listing.write_text(record + record.replace("Brother%20DCP", "Second%20DCP"))
    result = subprocess.run(command, env=env, capture_output=True, text=True)
    assert result.returncode != 0 and "Multiple" in result.stderr and not result.stdout
    print("PASS: multiple printers require explicit selection")
    listing.write_text(record.replace("DCP-J315W", "DCP-J4120DW"))
    result = subprocess.run(command, env=env, capture_output=True, text=True)
    assert result.returncode != 0 and "No DCP-J315W" in result.stderr
    print("PASS: different model rejected")
    listing.write_text(record.replace("_pdl-datastream", "_ipp"))
    result = subprocess.run(command, env=env, capture_output=True, text=True)
    assert result.returncode != 0 and "No DCP-J315W" in result.stderr
    print("PASS: incompatible IPP transport excluded from raw-print discovery")
    stub.write_text("#!/bin/sh\nif [ ! -f \"$DCPJ315W_DISCOVERY_LIST.once\" ]; then\n"
                    " touch \"$DCPJ315W_DISCOVERY_LIST.once\"\nelse\n"
                    " cat \"$DCPJ315W_DISCOVERY_LIST\"\nfi\n")
    listing.write_text(record)
    result = subprocess.run(command, env=env, capture_output=True, text=True)
    assert result.returncode == 0 and result.stdout.strip() == expected
    print("PASS: empty initial discovery gets one bounded retry")
