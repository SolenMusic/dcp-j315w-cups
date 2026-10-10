#!/bin/bash
# Developer ID credentials stay in the local keychain, never in the repository.
set -euo pipefail
export COPYFILE_DISABLE=1
root=$(cd -- "$(dirname -- "$0")" && pwd)
cd "$root"
unsigned=0
binary="$root/rastertodcpj315w"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --unsigned) unsigned=1; shift ;;
    --binary) [[ $# -ge 2 ]] || exit 1; binary=$2; shift 2 ;;
    *) echo 'Usage: ./build-macos-installer.sh [--binary FILE] [--unsigned]' >&2; exit 1 ;;
  esac
done
[[ $(uname -s) == Darwin && -f $binary ]] || { echo 'Build a macOS filter first.' >&2; exit 1; }
architectures=$(lipo "$binary" -archs)
case "$architectures" in
  arm64) arch=arm64; host_arch=arm64 ;;
  x86_64) arch=x86_64; host_arch=x86_64 ;;
  'x86_64 arm64'|'arm64 x86_64') arch=universal; host_arch=x86_64,arm64 ;;
  *) echo "Unsupported architectures: $architectures" >&2; exit 1 ;;
esac
read -r version < VERSION
work=$(mktemp -d "${TMPDIR:-/tmp}/dcp-j315w-installer.XXXXXX")
trap 'rm -rf "$work"' EXIT
payload="$work/root/Library/Printers/DCPJ315WCUPS"
mkdir -p "$payload" "$work/root/Library/Printers/PPDs/Contents/Resources" "$work/resources" dist
cp -X "$binary" "$payload/rastertodcpj315w"
for item in install.sh install-deps.sh uninstall.sh discover.sh status.sh status_parse.awk prepare_ppd.awk stage_install.sh VERSION LICENSE README.md CHANGELOG.md; do
  cp -X "$item" "$payload/$item"
done
cp -X macos/configure.sh "$payload/configure.sh"
cp -X DCP-J315W-CUPS.ppd.in prologue_*.bin "$payload/"
mkdir "$payload/docs"
cp -X docs/*.md "$payload/docs/"
sed 's|@FILTER@|/Library/Printers/DCPJ315WCUPS/rastertodcpj315w|' DCP-J315W-CUPS.ppd.in > "$work/root/Library/Printers/PPDs/Contents/Resources/DCP-J315W-CUPS.ppd"
chmod 755 "$payload/rastertodcpj315w" "$payload/"*.sh
find "$work/root" -type d -exec chmod 755 {} +
if [[ $unsigned == 0 ]]; then
  : "${APPLICATION_SIGN_IDENTITY:?Set a Developer ID Application signing identity.}"
  : "${INSTALLER_SIGN_IDENTITY:?Set a Developer ID Installer signing identity.}"
  [[ $APPLICATION_SIGN_IDENTITY == 'Developer ID Application: '* && $INSTALLER_SIGN_IDENTITY == 'Developer ID Installer: '* ]] || {
    echo 'Developer ID Application and Developer ID Installer certificates are required.' >&2; exit 1;
  }
  codesign --force --sign "$APPLICATION_SIGN_IDENTITY" --options runtime --timestamp --identifier dcp-j315w-cups.filter "$payload/rastertodcpj315w"
else
  codesign --force --sign - --identifier dcp-j315w-cups.filter "$payload/rastertodcpj315w"
fi
codesign --verify --strict "$payload/rastertodcpj315w"
pkgbuild --root "$work/root" --scripts "$root/macos/scripts" --ownership recommended \
  --identifier org.dcp-j315w-cups.driver --version "$version" --install-location / "$work/driver.pkg"
cp -X LICENSE "$work/resources/LICENSE.txt"
cat > "$work/resources/Welcome.html" <<'HTML'
<html><body><h1>DCP-J315W CUPS Driver</h1><p>Native printing for the Brother DCP-J315W on macOS Intel and Apple Silicon.</p><p>Supports A4, A5, A6 and US Letter on plain paper, in monochrome or colour at 300/600 dpi.</p><p>This installer adds the driver and attempts to discover your printer on the local network. Existing queues using this project's driver are upgraded with their settings preserved. The system default printer is unchanged.</p><p>Only the DCP-J315W is supported. USB, scanning and AirPrint are not included.</p><p>Created with LLM-assisted coding. I hope this keeps your printer running for a while longer.</p></body></html>
HTML
cat > "$work/resources/Conclusion.html" <<'HTML'
<html><body><h1>Driver installed</h1><p>If the printer was discovered, choose <b>DCP-J315W CUPS Driver</b> when printing.</p><p>Otherwise, open <b>System Settings → Printers &amp; Scanners → Add Printer</b> and select <b>DCP-J315W CUPS Driver</b> in the Use menu. For manual setup, run this in Terminal with your printer's network address:</p><pre>sudo /Library/Printers/DCPJ315WCUPS/configure.sh --address PRINTER_ADDRESS</pre><p>Default settings: A4, monochrome, 300 dpi. For artwork choose Colour and Fine (600 dpi). Load paper matching the selected size.</p></body></html>
HTML
cat > "$work/distribution.xml" <<EOF
<?xml version="1.0" encoding="utf-8"?>
<installer-gui-script minSpecVersion="2">
  <title>DCP-J315W CUPS Driver $version</title>
  <welcome file="Welcome.html" mime-type="text/html"/>
  <license file="LICENSE.txt" mime-type="text/plain"/>
  <conclusion file="Conclusion.html" mime-type="text/html"/>
  <options customize="never" require-scripts="false" hostArchitectures="$host_arch"/>
  <domains enable_localSystem="true" enable_currentUserHome="false" enable_anywhere="false"/>
  <allowed-os-versions><os-version min="11.0"/></allowed-os-versions>
  <choices-outline><line choice="driver"/></choices-outline>
  <choice id="driver" visible="false"><pkg-ref id="org.dcp-j315w-cups.driver"/></choice>
  <pkg-ref id="org.dcp-j315w-cups.driver" version="$version" onConclusion="none">driver.pkg</pkg-ref>
</installer-gui-script>
EOF
suffix=
if [[ $unsigned == 1 ]]; then suffix=-unsigned; fi
output="$root/dist/dcp-j315w-cups-$version-macos-$arch$suffix.pkg"
product_args=(--distribution "$work/distribution.xml" --resources "$work/resources" --package-path "$work")
if [[ $unsigned == 0 ]]; then product_args+=(--sign "$INSTALLER_SIGN_IDENTITY"); fi
productbuild "${product_args[@]}" "$output"
pkgutil --check-signature "$output" || [[ $unsigned == 1 ]]
echo "Created $output"
