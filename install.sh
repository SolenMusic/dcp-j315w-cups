#!/bin/bash
# CUPS 2.x network installer. Printer transport for USB is a later milestone.
set -eu
export LC_ALL=C

usage() {
  cat <<'EOF'
Usage: ./install.sh [--discover | --address HOST | --uri URI] [--port PORT] [--queue NAME] [--install-deps] [--dry-run]

New installation: discover the printer or supply its address or CUPS device URI.
Upgrade: omit connection options to keep the existing native queue's connection.
--discover uses Bonjour, which can follow the printer after an IP address change.
--queue defaults to DCP_J315W; --port defaults to 9100.
Paper, colour and quality defaults are preserved on upgrades.
--dry-run validates and previews the operation without installing anything.
Actual installation requires sudo. Supports macOS and Linux with CUPS 2.x.
--install-deps installs Linux runtime packages using apt, dnf or pacman first.
EOF
}

fail() { echo "ERROR: $*" >&2; exit 1; }
queue=DCP_J315W
address=
device_uri=
discover=0
port=9100
port_set=0
dry_run=0
install_deps=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --address|--port|--queue|--uri)
      [ "$#" -ge 2 ] || fail "$1 needs a value."
      case "$1" in
        --address) address=$2 ;;
        --port) port=$2; port_set=1 ;;
        --queue) queue=$2 ;;
        --uri) device_uri=$2 ;;
      esac
      shift 2 ;;
    --dry-run) dry_run=1; shift ;;
    --discover) discover=1; shift ;;
    --install-deps) install_deps=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) fail "Unknown argument: $1 (use --help)." ;;
  esac
done

platform=$(uname -s)
case "$platform" in Darwin|Linux) ;; *) fail "Use this installer on macOS or Linux with CUPS 2.x." ;; esac
case "$queue" in ''|-*|*[!A-Za-z0-9_.-]*) fail "Use a queue name containing letters, digits, _, . or -." ;; esac
case "$port" in ''|*[!0-9]*) fail "Port must be a number from 1 to 65535." ;; esac
[ "$port" -ge 1 ] && [ "$port" -le 65535 ] || fail "Port must be from 1 to 65535."
[ "$port_set" -eq 0 ] || [ -n "$address" ] || fail "--port also requires --address."
connections=$discover
if [ -n "$address" ]; then connections=$((connections + 1)); fi
if [ -n "$device_uri" ]; then connections=$((connections + 1)); fi
[ "$connections" -le 1 ] || fail "Choose one of --discover, --address or --uri."
if [ -n "$device_uri" ]; then
  case "$device_uri" in
    *[[:space:]]*) fail "Device URI must not contain unescaped spaces or newlines." ;;
    socket://?*|dnssd://?*) ;;
    *) fail "Use a socket:// or dnssd:// raw network device URI." ;;
  esac
  case "$device_uri" in dnssd://*)
    case "$device_uri" in *._pdl-datastream._tcp.*) ;; *) fail "Use the printer's raw _pdl-datastream Bonjour service." ;; esac ;;
  esac
fi
if [ -n "$address" ]; then
  case "$address" in -*|*[!A-Za-z0-9._:-]*) fail "Supply an IP address or DNS hostname, without a URL or spaces." ;; esac
fi
if [ "$dry_run" -eq 0 ] && [ "$(id -u)" -ne 0 ]; then
  fail "Use sudo for installation, or --dry-run to preview it."
fi

source_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ "$install_deps" -eq 1 ]; then
  [ "$platform" = Linux ] || fail "macOS supplies CUPS; --install-deps is Linux only."
  if [ "$dry_run" -eq 1 ]; then
    "$source_dir/install-deps.sh" --dry-run
  else
    "$source_dir/install-deps.sh"
  fi
fi
owner_group=wheel
if [ "$platform" = Darwin ]; then
  install_dir=/Library/Printers/DCPJ315WCUPS
else
  owner_group=root
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
  [ -n "$serverbin" ] || fail "Cannot locate CUPS filters; install CUPS or its development tools."
  install_dir="$serverbin/filter/dcp-j315w-cups"
fi
ppd_path="$install_dir/DCP-J315W-CUPS.ppd"
filter_path="$install_dir/rastertodcpj315w"
previous_ppd="/etc/cups/ppd/$queue.ppd"
[ -x "$source_dir/rastertodcpj315w" ] || fail "Build the filter with ./build.sh first."
[ -r "$source_dir/DCP-J315W-CUPS.ppd.in" ] && [ -r "$source_dir/prepare_ppd.awk" ] && [ -r "$source_dir/uninstall.sh" ] || fail "Missing PPD template, generator or uninstaller."
if [ "$platform" = Darwin ]; then
  codesign --verify --strict "$source_dir/rastertodcpj315w" || fail "The source filter's signature is invalid."
  lipo "$source_dir/rastertodcpj315w" -verify_arch "$(uname -m)" || fail "Download the macOS filter for your CPU architecture."
else
  description=$(file -b "$source_dir/rastertodcpj315w")
  case "$description" in 'ELF 64-bit '*) ;; *) fail "Build a Linux executable with ./build.sh first." ;; esac
  interpreter=$(printf '%s\n' "$description" | sed -n 's/.*interpreter \([^, ]*\).*/\1/p')
  [ -z "$interpreter" ] || [ -e "$interpreter" ] || fail "Missing ELF loader $interpreter; download the correct glibc or Alpine/musl bundle."
  case "$(uname -m)" in
    x86_64) case "$description" in *x86-64*) ;; *) fail "This Linux filter is not x86_64." ;; esac ;;
    aarch64|arm64) case "$description" in *aarch64*) ;; *) fail "This Linux filter is not ARM64." ;; esac ;;
    *) fail "Only Linux x86_64 and ARM64 targets have been validated." ;;
  esac
fi
for mode in a4_150 a4_300 a4_600 a5_300 a5_600 a6_150 a6_300 a6_600 letter_300 letter_600; do
  header="$source_dir/prologue_$mode.bin"
  [ -r "$header" ] || fail "Missing command header: $mode."
  [ "$(wc -c < "$header" | tr -d ' ')" = 820 ] || fail "Command header $mode is not 820 bytes."
done
lpstat -r >/dev/null || fail "The local CUPS scheduler is unavailable."
if [ "$discover" -eq 1 ]; then
  [ -r "$source_dir/discover.sh" ] || fail "Missing discovery helper."
  device_uri=$(/bin/sh "$source_dir/discover.sh" --uri-only) || fail "Could not choose a discovered printer."
fi
existing=0
if lpstat -p "$queue" >/dev/null 2>&1; then
  existing=1
  [ -r "$previous_ppd" ] || fail "Cannot read the existing queue's PPD."
  # Accept this project's pre-release installation when upgrading an existing
  # queue explicitly. Keep old shared files for any other pre-release queues.
  if [ "$platform" = Darwin ]; then
    legacy_filter=/Library/Printers/DCPJ315WNative/rastertobrother_native
  else
    legacy_filter="$serverbin/filter/dcpj315w-native/rastertobrother_native"
  fi
  awk -v filter="$filter_path" -v legacy="$legacy_filter" '
    /^\*cupsFilter:/ { if (index($0, " " filter "\"") || index($0, " " legacy "\"")) found=1 }
    END { exit !found }
  ' "$previous_ppd" || fail "Queue $queue belongs to another driver; choose a separate queue name."
  uri=$(lpstat -v "$queue" | sed 's/^[^:]*: //')
  [ -n "$uri" ] || fail "Cannot determine the existing printer connection."
else
  previous_ppd=/dev/null
  [ -n "$address" ] || [ -n "$device_uri" ] || fail "Supply --discover, --address HOST or --uri URI for a new queue."
fi
if [ -n "$address" ]; then
  case "$address" in *:*) uri="socket://[$address]:$port" ;; *) uri="socket://$address:$port" ;; esac
fi
if [ -n "$device_uri" ]; then uri=$device_uri; fi
pending=$(lpstat -W not-completed -o "$queue" 2>/dev/null || true)
[ -z "$pending" ] || fail "Queue $queue has unfinished jobs. Finish or cancel them before upgrading."

scratch=$(mktemp -d "${TMPDIR:-/tmp}/dcpj315w-install.XXXXXX")
trap 'rm -rf "$scratch"' 0 HUP INT TERM
awk -v filter="$filter_path" -f "$source_dir/prepare_ppd.awk" \
  "$previous_ppd" "$source_dir/DCP-J315W-CUPS.ppd.in" > "$scratch/queue.ppd"
# Before a first install the filter path does not exist yet. Check PPD syntax
# now, then check the real installed filter and permissions before queue changes.
cupstestppd -q -W filters "$scratch/queue.ppd" || fail "Generated PPD did not validate."
if [ "$existing" -eq 1 ]; then
  echo "Upgrade native queue: $queue"
else
  echo "Create native queue: $queue"
fi
echo "Printer connection: $uri"
awk '/^\*Default(PageSize|Resolution|ColorModel):/ { print }' "$scratch/queue.ppd"
if [ "$dry_run" -eq 1 ]; then
  echo "Dry run complete; no installed files or queues changed."
  exit 0
fi

install -d -o root -g "$owner_group" -m 755 "$install_dir"
install -o root -g "$owner_group" -m 755 "$source_dir/rastertodcpj315w" "$filter_path.next"
mv -f "$filter_path.next" "$filter_path"
for header in "$source_dir"/prologue_*.bin; do
  install -o root -g "$owner_group" -m 644 "$header" "$install_dir/$(basename "$header")"
done
install -o root -g "$owner_group" -m 644 "$scratch/queue.ppd" "$ppd_path.next"
mv -f "$ppd_path.next" "$ppd_path"
if [ "$platform" = Linux ] && command -v restorecon >/dev/null; then
  restorecon -R "$install_dir"
fi
if [ "$platform" = Darwin ]; then codesign --verify --strict "$filter_path"; fi
cupstestppd -q "$ppd_path"
install -o root -g "$owner_group" -m 755 "$source_dir/uninstall.sh" "$install_dir/uninstall.sh"
if [ "$existing" -eq 1 ]; then
  # Retain sharing, policy, enabled state and URI; update the display name.
  if [ -n "$address" ] || [ -n "$device_uri" ]; then
    lpadmin -p "$queue" -v "$uri" -P "$ppd_path"
  else
    lpadmin -p "$queue" -P "$ppd_path"
  fi
  lpadmin -p "$queue" -D "DCP-J315W CUPS Driver"
else
  lpadmin -p "$queue" -E -v "$uri" -P "$ppd_path" \
    -D "DCP-J315W CUPS Driver"
fi
echo "Installed native queue: $queue"
