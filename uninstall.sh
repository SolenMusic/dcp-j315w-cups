#!/bin/sh
set -eu
export LC_ALL=C
queue=DCP_J315W
dry_run=0
queue_only=0
fail() { echo "ERROR: $*" >&2; exit 1; }
while [ "$#" -gt 0 ]; do
  case "$1" in
    --queue) [ "$#" -ge 2 ] || fail "--queue needs a value."; queue=$2; shift 2 ;;
    --dry-run) dry_run=1; shift ;;
    --queue-only) queue_only=1; shift ;;
    --help|-h)
      echo "Usage: ./uninstall.sh [--queue NAME] [--dry-run]"
      echo "Remove a native queue; retain driver files if another queue uses them."
      echo "Actual removal requires sudo."
      exit 0 ;;
    *) fail "Unknown argument: $1 (use --help)." ;;
  esac
done
platform=$(uname -s)
case "$platform" in Darwin|Linux) ;; *) fail "This uninstaller is for macOS or Linux." ;; esac
case "$queue" in ''|-*|*[!A-Za-z0-9_.-]*) fail "Invalid queue name." ;; esac
if [ "$dry_run" -eq 0 ] && [ "$(id -u)" -ne 0 ]; then
  fail "Use sudo for removal, or --dry-run to preview it."
fi
if [ "$platform" = Darwin ]; then
  install_dir=/Library/Printers/DCPJ315WCUPS
else
  serverbin=
  if command -v cups-config >/dev/null; then serverbin=$(cups-config --serverbin); fi
  if [ -z "$serverbin" ]; then
    for directory in /usr/lib/cups /usr/libexec/cups /usr/lib64/cups; do
      if [ -x "$directory/backend/socket" ] && [ -d "$directory/filter" ]; then
        [ -z "$serverbin" ] || fail "Multiple CUPS locations found; install cups-devel to identify the active installation."
        serverbin=$directory
      fi
    done
  fi
  [ -n "$serverbin" ] || fail "Cannot locate CUPS filters."
  install_dir="$serverbin/filter/dcp-j315w-cups"
fi
filter_path="$install_dir/rastertodcpj315w"
ppd="/etc/cups/ppd/$queue.ppd"
uses_native() {
  awk -v filter="$filter_path" '
    /^\*cupsFilter:/ { if (index($0, " " filter "\"")) found=1 }
    END { exit !found }
  ' "$1"
}
lpstat -r >/dev/null || fail "The local CUPS scheduler is unavailable."
existing=0
if lpstat -p "$queue" >/dev/null 2>&1; then
  existing=1
  [ -r "$ppd" ] && uses_native "$ppd" || fail "Queue $queue belongs to another driver."
  pending=$(lpstat -W not-completed -o "$queue" 2>/dev/null || true)
  [ -z "$pending" ] || fail "Queue $queue has unfinished jobs. Finish or cancel them first."
fi
shared=0
for other in /etc/cups/ppd/*.ppd; do
  [ -f "$other" ] || continue
  [ "$other" != "$ppd" ] || continue
  [ -r "$other" ] || fail "Cannot check other printer queues; use sudo for removal."
  if uses_native "$other"; then shared=1; fi
done
if [ "$existing" -eq 1 ]; then echo "Remove native queue: $queue"; else echo "Queue $queue is already absent."; fi
if [ "$queue_only" -eq 1 ]; then
  [ "$platform" = Linux ] || fail "Queue-only removal is for Linux packages."
  echo "Driver files are managed by your package manager."
elif [ "$shared" -eq 1 ]; then
  echo "Retain driver files: another queue uses them."
else
  echo "Remove this driver's installed files."
fi
if [ "$dry_run" -eq 1 ]; then echo "Dry run complete; no files or queues changed."; exit 0; fi
if [ "$existing" -eq 1 ]; then lpadmin -x "$queue"; fi
if [ "$queue_only" -eq 1 ]; then echo "Native queue removal complete."; exit 0; fi
if [ "$shared" -eq 0 ]; then
  # Remove only the files installed by this project. Leave unexpected files.
  for name in rastertodcpj315w DCP-J315W-CUPS.ppd DCP-J315W-CUPS.ppd.in uninstall.sh \
      install.sh install-deps.sh configure.sh stage_install.sh discover.sh status.sh \
      status_parse.awk prepare_ppd.awk VERSION LICENSE README.md CHANGELOG.md; do
    rm -f "$install_dir/$name"
  done
  if [ "$platform" = Darwin ]; then
    public_ppd=/Library/Printers/PPDs/Contents/Resources/DCP-J315W-CUPS.ppd
    if [ -r "$public_ppd" ] && uses_native "$public_ppd"; then rm -f "$public_ppd"; fi
    for name in INSTALL.md PROVENANCE.md PROTOCOL.md TESTING.md MACOS-RELEASE.md RELEASING.md NIXOS.md; do
      rm -f "$install_dir/docs/$name"
    done
    if [ -d "$install_dir/docs" ]; then rmdir "$install_dir/docs" 2>/dev/null || true; fi
    if pkgutil --pkg-info org.dcp-j315w-cups.driver >/dev/null 2>&1; then
      pkgutil --forget org.dcp-j315w-cups.driver >/dev/null
    fi
  fi
  for mode in a4_150 a4_300 a4_600 a5_300 a5_600 a6_150 a6_300 a6_600 letter_300 letter_600; do
    rm -f "$install_dir/prologue_$mode.bin"
  done
  if [ -d "$install_dir" ]; then
    rmdir "$install_dir" 2>/dev/null || echo "Retained directory containing other files: $install_dir"
  fi
fi
echo "Native queue removal complete."
