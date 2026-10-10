#!/usr/bin/env python3
"""Exercise install/upgrade/removal inside a disposable Linux container only.

Run as root in Dockerfile.linux-test. Do not run this on a personal computer:
it starts its own CUPS daemon and creates temporary queues with no print output.
"""
import os
from pathlib import Path
import platform
import subprocess
import time

root = Path(__file__).resolve().parent
assert platform.system() == "Linux" and os.geteuid() == 0
assert Path("/.dockerenv").exists(), "run in the disposable test container"
queue = "DCP_J315W_InstallTest"
other = "DCP_J315W_SecondTest"
install_dir = Path(subprocess.check_output(["cups-config", "--serverbin"], text=True).strip()) / "filter/dcp-j315w-cups"


def command(*args, check=True):
    result = subprocess.run(args, cwd=root, capture_output=True, text=True)
    if check and result.returncode:
        print(result.stdout, result.stderr, flush=True)
        result.check_returncode()
    return result


daemon = subprocess.Popen(["cupsd", "-f"], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
try:
    for attempt in range(30):
        if command("lpstat", "-r", check=False).returncode == 0:
            break
        time.sleep(0.1)
    else:
        raise AssertionError("CUPS did not start")
    for name in (queue, other):
        assert command("lpstat", "-p", name, check=False).returncode != 0
    command("./install.sh", "--queue", queue, "--address", "127.0.0.1", "--port", "9")
    command("lpadmin", "-p", queue, "-o", "PageSize=A5", "-o", "PageRegion=A5",
            "-o", "Resolution=600dpi", "-o", "ColorModel=Color")
    before = command("lpoptions", "-p", queue, "-l").stdout
    connection = command("lpstat", "-v", queue).stdout
    command("./install.sh", "--queue", queue)
    assert command("lpoptions", "-p", queue, "-l").stdout == before
    assert command("lpstat", "-v", queue).stdout == connection
    print("PASS: Linux upgrade preserves A5/Colour/600 dpi and connection", flush=True)
    held = Path("/tmp/installer-held.txt")
    held.write_text("Held verification job - never print\n")
    command("lp", "-d", queue, "-H", "hold", str(held))
    for script in ("./install.sh", "./uninstall.sh"):
        result = command(script, "--queue", queue, "--dry-run", check=False)
        assert result.returncode != 0 and "unfinished jobs" in result.stderr
    command("cancel", queue)
    print("PASS: Linux upgrade/removal reject unfinished jobs; held job cancelled", flush=True)
    command("./install.sh", "--queue", other, "--address", "127.0.0.1", "--port", "9")
    command("./uninstall.sh", "--queue", queue)
    assert command("lpstat", "-p", queue, check=False).returncode != 0
    assert (install_dir / "rastertodcpj315w").exists()
    print("PASS: Linux queue removal preserves files shared with another native queue", flush=True)
    command("./uninstall.sh", "--queue", other)
    assert not install_dir.exists()
    print("PASS: removing the final Linux native queue removes its installed files", flush=True)
    print("LINUX INSTALLER VERIFICATION COMPLETE - no physical printer contacted", flush=True)
finally:
    daemon.terminate()
    try:
        daemon.wait(timeout=5)
    except subprocess.TimeoutExpired:
        daemon.kill()
        daemon.wait()
