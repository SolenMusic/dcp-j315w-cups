#!/usr/bin/env python3
"""Check status interpretation, including unknown ink readings, without a printer."""
from pathlib import Path
import subprocess

parser = Path(__file__).resolve().parent / "status_parse.awk"
status = """.1.3.6.1.2.1.25.3.2.1.5.1 = INTEGER: 2
.1.3.6.1.2.1.25.3.5.1.1.1 = INTEGER: 3
.1.3.6.1.2.1.25.3.5.1.2.1 = Hex-STRING: 00
.1.3.6.1.2.1.43.11.1.1.6.1.1 = STRING: "Black Ink Cartridge"
.1.3.6.1.2.1.43.11.1.1.8.1.1 = INTEGER: 500
.1.3.6.1.2.1.43.11.1.1.9.1.1 = INTEGER: -3
"""


def run(data):
    return subprocess.run(["awk", "-f", str(parser)], input=data, text=True, capture_output=True)


result = run(status)
assert result.returncode == 0 and "Printer: idle" in result.stdout
assert "some ink remains; percentage unavailable" in result.stdout
assert "approximately" not in result.stdout
print("PASS: qualitative ink readings are not invented percentages")
result = run(status.replace("Hex-STRING: 00", "Hex-STRING: 44"))
assert "Out of paper" in result.stdout and "Paper jam" in result.stdout and "errors: none" not in result.stdout
print("PASS: paper-out and jam flags decode in network bit order")
result = run(status.replace("INTEGER: -3", "INTEGER: 125"))
assert "approximately 25%" in result.stdout
result = run(status.replace("INTEGER: -3", "INTEGER: -2"))
assert "Black Ink Cartridge: unknown" in result.stdout
print("PASS: known relative levels and unknown readings are distinguished")
result = run(status.replace("Hex-STRING: 00", "Hex-STRING: ??"))
assert result.returncode != 0 and "errors: none" not in result.stdout
print("PASS: malformed status does not appear healthy")
