#!/bin/bash
# Use credentials previously stored by notarytool in the local keychain.
set -euo pipefail
if [[ $# != 2 ]]; then
  echo 'Usage: ./notarize-macos-installer.sh installer.pkg KEYCHAIN_PROFILE' >&2
  exit 1
fi
package=$1
profile=$2
[[ -f $package && $package == *.pkg ]] || exit 1
pkgutil --check-signature "$package"
result=$(mktemp "${TMPDIR:-/tmp}/dcp-j315w-notary.XXXXXX")
trap 'rm -f "$result"' EXIT
# Separate submission from waiting, so a delayed submission can be resumed.
xcrun notarytool submit "$package" --keychain-profile "$profile" --output-format plist > "$result"
id=$(/usr/libexec/PlistBuddy -c 'Print :id' "$result")
echo "Notarization submission: $id"
if ! xcrun notarytool wait "$id" --keychain-profile "$profile" --timeout 60s --output-format plist > "$result"; then
  echo "Submission is pending or unavailable. Resume with notarytool wait $id; do not resubmit." >&2
  exit 1
fi
status=$(/usr/libexec/PlistBuddy -c 'Print :status' "$result")
if [[ $status != Accepted ]]; then
  echo "Notarization status: $status (submission $id). Do not publish this package." >&2
  exit 1
fi
xcrun stapler staple "$package"
xcrun stapler validate "$package"
spctl --assess --verbose --type install "$package"
