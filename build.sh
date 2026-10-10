#!/bin/sh
set -eu
root="$(cd "$(dirname "$0")" && pwd)"
if ! command -v cups-config >/dev/null 2>&1; then
  echo "cups-config is required (install the CUPS development package)." >&2
  exit 1
fi
output=${OUTPUT:-"$root/rastertodcpj315w"}
temp_output=$(mktemp "${output}.XXXXXX")
trap 'rm -f "$temp_output"' 0 HUP INT TERM
"${CC:-cc}" -std=c11 -Wall -Wextra -Werror -O2 ${CFLAGS:-} \
  $(cups-config --cflags --ldflags) "$root/rastertodcpj315w.c" \
  $(cups-config --libs) ${LDFLAGS:-} -o "$temp_output"
if [ "$(uname -s)" = Darwin ]; then
  # Explicit local signing avoids Taskgated rejecting a linker-only signature.
  /usr/bin/codesign --force --sign - --identifier dcp-j315w-cups.filter "$temp_output"
  /usr/bin/codesign --verify --strict "$temp_output"
fi
# A fresh inode avoids stale macOS executable/signature caches after a rebuild.
chmod 755 "$temp_output"
mv -f "$temp_output" "$output"
if command -v file >/dev/null 2>&1; then
  file "$output"
else
  echo "Built $output"
fi
