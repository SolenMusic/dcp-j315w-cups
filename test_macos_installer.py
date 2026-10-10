#!/usr/bin/env python3
"""Install/upgrade/remove the actual PKG in a disposable GitHub macOS runner.

Never run on a personal Mac. No jobs are printed: the only job is held, and the
temporary queue points to localhost port 9, not a physical printer.
"""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile

assert sys.platform == "darwin" and os.geteuid() == 0
assert os.environ.get("GITHUB_ACTIONS") == "true", "disposable GitHub runner only"
package = Path(sys.argv[1]).resolve()
driver = Path("/Library/Printers/DCPJ315WCUPS")
public_ppd = Path("/Library/Printers/PPDs/Contents/Resources/DCP-J315W-CUPS.ppd")
queue = "DCP_J315W_PackageTest"


def command(*args, check=True):
    result = subprocess.run(args, capture_output=True, text=True, timeout=120)
    if check and result.returncode:
        print(result.stdout, result.stderr, flush=True)
        result.check_returncode()
    return result


assert not driver.exists(), "runner must start without this driver"
assert command("lpstat", "-p", queue, check=False).returncode != 0
command("installer", "-pkg", str(package), "-target", "/")
assert (driver / "rastertodcpj315w").is_file() and public_ppd.is_file()
command("codesign", "--verify", "--strict", str(driver / "rastertodcpj315w"))
command("cupstestppd", "-q", str(public_ppd))
command(str(driver / "configure.sh"), "--queue", queue, "--address", "127.0.0.1", "--port", "9")
try:
    command("lpadmin", "-p", queue, "-o", "PageSize=A5", "-o", "PageRegion=A5",
            "-o", "Resolution=600dpi", "-o", "ColorModel=Color")
    before = command("lpoptions", "-p", queue, "-l").stdout
    connection = command("lpstat", "-v", queue).stdout
    command("installer", "-pkg", str(package), "-target", "/")
    assert command("lpoptions", "-p", queue, "-l").stdout == before
    assert command("lpstat", "-v", queue).stdout == connection
    print("PASS: actual PKG install/upgrade preserves paper, colour, resolution and connection", flush=True)
    digest = hashlib.sha256((driver / "rastertodcpj315w").read_bytes()).hexdigest()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt") as held:
        held.write("Held installer verification; never print.\n")
        held.flush()
        command("lp", "-d", queue, "-H", "hold", held.name)
        result = command("installer", "-pkg", str(package), "-target", "/", check=False)
        assert result.returncode != 0, "PKG upgrade must refuse an unfinished job"
    assert hashlib.sha256((driver / "rastertodcpj315w").read_bytes()).hexdigest() == digest
    command("cancel", queue)
    print("PASS: PKG preinstall rejects unfinished jobs before changing the renderer", flush=True)
finally:
    command("cancel", queue, check=False)
    command(str(driver / "uninstall.sh"), "--queue", queue)
assert not driver.exists() and not public_ppd.exists()
assert command("pkgutil", "--pkg-info", "org.dcp-j315w-cups.driver", check=False).returncode != 0
print("PASS: uninstaller removes final driver, public PPD and package receipt", flush=True)
