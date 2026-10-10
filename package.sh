#!/bin/bash
# Create a binary release tarball. All installers use shell; no Python needed.
set -euo pipefail
root=$(cd -- "$(dirname -- "$0")" && pwd)
cd "$root"
if [[ $# != 2 ]]; then
  echo 'Usage: ./package.sh macos|linux-debian|linux-fedora|linux-arch x86_64|arm64' >&2
  exit 1
fi
platform=$1
arch=$2
case "$arch" in x86_64|arm64) ;; *) echo 'Unsupported CPU.' >&2; exit 1 ;; esac
case "$platform" in
  macos) [[ $(uname -s) == Darwin ]]; lipo rastertodcpj315w -verify_arch "$arch" ;;
  linux-debian|linux-fedora|linux-arch)
    [[ $(uname -s) == Linux ]]
    description=$(file -b rastertodcpj315w)
    case "$arch:$description" in x86_64:*ELF*x86-64*|arm64:*ELF*aarch64*) ;; *) echo 'Wrong executable architecture.' >&2; exit 1 ;; esac ;;
  *) echo 'Unsupported release platform.' >&2; exit 1 ;;
esac
read -r version < VERSION
[[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo 'Invalid VERSION.' >&2; exit 1; }
name="dcp-j315w-cups-$version-$platform-$arch"
mkdir -p dist
stage=$(mktemp -d "${TMPDIR:-/tmp}/dcp-j315w-release.XXXXXX")
trap 'rm -rf "$stage"' EXIT
mkdir "$stage/$name"
for item in rastertodcpj315w install.sh install-deps.sh uninstall.sh discover.sh status.sh status_parse.awk prepare_ppd.awk DCP-J315W-CUPS.ppd.in VERSION LICENSE README.md CHANGELOG.md; do
  cp "$item" "$stage/$name/$item"
done
cp prologue_*.bin "$stage/$name/"
mkdir "$stage/$name/docs"
cp docs/INSTALL.md docs/PROVENANCE.md "$stage/$name/docs/"
if [[ $platform == linux-* ]]; then
  printf '%s\n' "${platform#linux-}" > "$stage/$name/BUNDLE_FLAVOUR"
fi
chmod 755 "$stage/$name/rastertodcpj315w" "$stage/$name/"*.sh
(
  cd "$stage/$name"
  if command -v sha256sum >/dev/null; then
    find . -type f ! -name SHA256SUMS -print | LC_ALL=C sort | while IFS= read -r item; do sha256sum "$item"; done > SHA256SUMS
  else
    find . -type f ! -name SHA256SUMS -print | LC_ALL=C sort | while IFS= read -r item; do shasum -a 256 "$item"; done > SHA256SUMS
  fi
)
export COPYFILE_DISABLE=1
if [[ $(uname -s) == Darwin ]]; then
  tar --uid 0 --gid 0 --uname root --gname wheel -czf "dist/$name.tar.gz" -C "$stage" "$name"
else
  tar --owner=0 --group=0 --numeric-owner -czf "dist/$name.tar.gz" -C "$stage" "$name"
fi
echo "Created dist/$name.tar.gz"
