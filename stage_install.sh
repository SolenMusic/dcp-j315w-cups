#!/bin/sh
# Make regular local files for installation from a cloud-managed workspace.
set -eu
source_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
stage=$(mktemp -d /private/tmp/dcpj315w-package.XXXXXX)
complete=0
cleanup() { if [ "$complete" -eq 0 ]; then rm -rf "$stage"; fi; }
trap cleanup 0 HUP INT TERM
for name in rastertodcpj315w install.sh install-deps.sh uninstall.sh discover.sh prepare_ppd.awk DCP-J315W-CUPS.ppd.in; do
  [ -r "$source_dir/$name" ] || { echo "Missing $name; build the filter first." >&2; exit 1; }
  cat "$source_dir/$name" > "$stage/$name"
  case "$name" in rastertodcpj315w|*.sh) chmod 755 "$stage/$name" ;; *) chmod 644 "$stage/$name" ;; esac
done
for header in "$source_dir"/prologue_*.bin; do
  cat "$header" > "$stage/$(basename "$header")"
  chmod 644 "$stage/$(basename "$header")"
done
complete=1
printf '%s\n' "$stage"
