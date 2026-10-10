#!/bin/sh
# Discover only this model's raw network-printing service using CUPS.
set -eu
export LC_ALL=C
uri_only=0
timeout=8
fail() { echo "ERROR: $*" >&2; exit 1; }
while [ "$#" -gt 0 ]; do
  case "$1" in
    --uri-only) uri_only=1; shift ;;
    --timeout) [ "$#" -ge 2 ] || fail "--timeout needs a value."; timeout=$2; shift 2 ;;
    --help|-h)
      echo "Usage: ./discover.sh [--uri-only] [--timeout SECONDS]"
      echo "Find a Brother DCP-J315W on the local network. --uri-only requires one match."
      exit 0 ;;
    *) fail "Unknown argument: $1." ;;
  esac
done
case "$timeout" in ''|*[!0-9]*) fail "Timeout must be 1-30 seconds." ;; esac
[ "$timeout" -ge 1 ] && [ "$timeout" -le 30 ] || fail "Timeout must be 1-30 seconds."
scratch=$(mktemp -d "${TMPDIR:-/tmp}/dcpj315w-discover.XXXXXX")
trap 'rm -rf "$scratch"' 0 HUP INT TERM
attempt=0
while [ "$attempt" -lt 2 ]; do
  attempt=$((attempt + 1))
  lpinfo --include-schemes dnssd --timeout "$timeout" -l -v > "$scratch/devices" ||
    fail "CUPS discovery failed; check the scheduler and permissions."
  awk '
  function emit() {
    if (uri ~ /^dnssd:\/\// && uri ~ /\._pdl-datastream\._tcp\./ &&
        ((id ~ /(^|;)(MFG|MANUFACTURER):Brother;/ && id ~ /(^|;)(MDL|MODEL):DCP-J315W;/) ||
         model == "Brother DCP-J315W")) print uri
  }
  /^Device: uri = / { emit(); uri=$0; sub(/^Device: uri = /,"",uri); id=""; model="" }
  /^[ \t]*make-and-model = / { model=$0; sub(/^[ \t]*make-and-model = /,"",model) }
  /^[ \t]*device-id = / { id=$0; sub(/^[ \t]*device-id = /,"",id) }
  END { emit() }
' "$scratch/devices" | sort -u > "$scratch/matches"
  [ -s "$scratch/matches" ] && break
done
matches=$(wc -l < "$scratch/matches" | tr -d ' ')
[ "$matches" -gt 0 ] || fail "No DCP-J315W raw-print service found. Check Wi-Fi, printer power, and local discovery, or use --address."
if [ "$uri_only" -eq 1 ]; then
  if [ "$matches" -ne 1 ]; then
    cat "$scratch/matches" >&2
    fail "Multiple DCP-J315W printers found; choose one explicitly with install.sh --uri."
  fi
else
  echo "DCP-J315W network printer connection(s):"
fi
cat "$scratch/matches"
