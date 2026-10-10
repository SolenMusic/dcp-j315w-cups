#!/bin/sh
# Read standard printer status. This never sends a print job or SNMP SET.
set -eu
export LC_ALL=C
if [ "$#" -ne 1 ] || [ "$1" = --help ] || [ "$1" = -h ]; then
  echo "Usage: ./status.sh PRINTER_ADDRESS"
  echo "Read device state, error flags and reported ink levels over SNMP."
  echo "Requires Net-SNMP snmpget/snmpwalk; no administrator privileges needed."
  [ "$#" -eq 1 ] && { [ "$1" = --help ] || [ "$1" = -h ]; } && exit 0
  exit 2
fi
address=$1
case "$address" in ''|-*|*[!A-Za-z0-9._:-]*) echo "Invalid printer address." >&2; exit 2 ;; esac
command -v snmpget >/dev/null && command -v snmpwalk >/dev/null || {
  echo "Status unavailable: install the Net-SNMP command-line tools." >&2; exit 1;
}
source_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
scratch=$(mktemp -d "${TMPDIR:-/tmp}/dcpj315w-status.XXXXXX")
trap 'rm -rf "$scratch"' 0 HUP INT TERM
case "$address" in *:*) target="udp6:[$address]:161" ;; *) target=$address ;; esac
if ! snmpget -v 1 -c public -t 2 -r 0 -On -Oe -Ox "$target" \
  1.3.6.1.2.1.25.3.2.1.5.1 1.3.6.1.2.1.25.3.5.1.1.1 \
  1.3.6.1.2.1.25.3.5.1.2.1 > "$scratch/status" 2> "$scratch/error"; then
  echo "Status unavailable: printer did not answer the SNMP query. It may be offline, unreachable, or have SNMP disabled." >&2
  cat "$scratch/error" >&2
  exit 1
fi
if ! snmpwalk -v 1 -c public -t 2 -r 0 -On -Oe "$target" \
  1.3.6.1.2.1.43.11.1.1 >> "$scratch/status" 2> "$scratch/error"; then
  echo "Ink-supply details unavailable; reporting device status only." >&2
fi
echo "Printer address: $address"
awk -f "$source_dir/status_parse.awk" "$scratch/status"
