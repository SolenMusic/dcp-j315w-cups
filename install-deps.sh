#!/bin/bash
# Install runtime packages only. Python is not needed to install or print.
set -euo pipefail
dry_run=0
if [[ ${1:-} == --dry-run && $# == 1 ]]; then
  dry_run=1
elif [[ $# != 0 ]]; then
  echo 'Usage: sudo ./install-deps.sh [--dry-run]' >&2
  exit 1
fi
[[ $(uname -s) == Linux ]] || { echo 'Linux only.' >&2; exit 1; }
root=$(cd -- "$(dirname -- "$0")" && pwd)
flavour=
if [[ -f "$root/BUNDLE_FLAVOUR" ]]; then
  read -r flavour < "$root/BUNDLE_FLAVOUR"
else
  . /etc/os-release
  case " ${ID:-} ${ID_LIKE:-} " in
    *debian*|*ubuntu*) flavour=debian ;;
    *fedora*|*rhel*|*centos*|*rocky*|*almalinux*) flavour=fedora ;;
    *arch*) flavour=arch ;;
    *opensuse*|*suse*|*sles*) flavour=opensuse ;;
    *alpine*) flavour=alpine ;;
    *) echo 'Use your package manager to install CUPS 2.x, cups-filters, Ghostscript and file.' >&2; exit 1 ;;
  esac
fi
case "$flavour" in
  debian|raspberrypi) packages=(cups cups-client cups-filters ghostscript file binutils avahi-daemon); manager=apt-get ;;
  fedora) packages=(cups cups-client cups-filters ghostscript file binutils avahi); manager=dnf ;;
  arch) packages=(cups cups-filters ghostscript file binutils avahi qpdf); manager=pacman ;;
  opensuse) packages=(cups cups-client cups-filters ghostscript file binutils avahi); manager=zypper ;;
  alpine) packages=(bash cups cups-client cups-filters ghostscript file binutils avahi); manager=apk ;;
  *) echo 'Unknown bundle flavour.' >&2; exit 1 ;;
esac
command -v "$manager" >/dev/null || { echo "This bundle needs $manager; download the bundle for your distribution." >&2; exit 1; }
echo "Runtime packages: ${packages[*]} ($manager)"
if [[ $dry_run == 1 ]]; then exit 0; fi
[[ $EUID == 0 ]] || { echo 'Run with sudo, or use --dry-run.' >&2; exit 1; }
case "$flavour" in
  debian|raspberrypi) apt-get update; apt-get install -y "${packages[@]}" ;;
  fedora) dnf install -y "${packages[@]}" ;;
  # Arch does not support partial upgrades. Make the full upgrade explicit.
  arch) pacman -Syu --needed "${packages[@]}" ;;
  opensuse) zypper --non-interactive install "${packages[@]}" ;;
  alpine) apk add "${packages[@]}" ;;
esac
if [[ $flavour == alpine && " $(id -nG root) " != *" lpadmin "* ]]; then
  # Alpine builds CUPS with lpadmin as its sole SystemGroup. Our root-run
  # queue installer needs root in that group for local CUPS authorization.
  adduser root lpadmin
fi
if command -v systemctl >/dev/null && [[ -d /run/systemd/system ]]; then
  systemctl enable --now cups.service
  systemctl enable --now avahi-daemon.service
elif [[ $flavour == alpine ]] && command -v rc-service >/dev/null && [[ -d /run/openrc ]]; then
  rc-update add cupsd default
  rc-update add avahi-daemon default
  rc-service cupsd start
  rc-service avahi-daemon start
fi
