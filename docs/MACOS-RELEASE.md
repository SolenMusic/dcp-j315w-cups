# macOS Installer signing and notarization

`build-macos-installer.sh` creates a standard graphical `.pkg` installer using
Apple's `pkgbuild` and `productbuild`. It installs the driver and its PPD, upgrades
existing queues using this project's driver, or attempts to create a queue using
Bonjour discovery. If discovery fails, the driver remains available in macOS's
Add Printer dialog. The installer refuses an upgrade while a native queue has
unfinished jobs. No Python is involved.

## Build an installer

Build the filter first. For a universal installer, build both architectures and
combine them with `lipo` before signing:

```sh
mkdir -p build/arm64 build/x86_64
OUTPUT="$PWD/build/arm64/rastertodcpj315w" CFLAGS='-arch arm64 -mmacosx-version-min=11.0' ./build.sh
OUTPUT="$PWD/build/x86_64/rastertodcpj315w" CFLAGS='-arch x86_64 -mmacosx-version-min=11.0' ./build.sh
lipo -create build/arm64/rastertodcpj315w build/x86_64/rastertodcpj315w -output build/rastertodcpj315w-universal
```

The release workflow checks the two architectures independently. For a release,
use the binaries from a successful run for the exact commit being tagged.

## Developer ID

Distribution outside the Mac App Store requires **Developer ID Application** to
sign the filter and **Developer ID Installer** to sign the package. Apple
Development certificates are not replacements for these. The signing identities
must be installed in your local keychain with their private keys.

Apple's account setup instructions:
[Create Developer ID certificates](https://developer.apple.com/help/account/certificates/create-developer-id-certificates/).

Keep signing credentials outside the repository:

```sh
export APPLICATION_SIGN_IDENTITY='Developer ID Application: YOUR ACCOUNT NAME (TEAMID)'
export INSTALLER_SIGN_IDENTITY='Developer ID Installer: YOUR ACCOUNT NAME (TEAMID)'
./build-macos-installer.sh --binary build/rastertodcpj315w-universal
```

The filter is signed with a secure timestamp and hardened runtime. The outer
installer is signed with Developer ID Installer. The unsigned CI package checks
packaging structure only and is named explicitly with `-unsigned.pkg`.

## Notarize

Store notarization credentials using Apple's interactive command. Enter the
app-specific password only at the secure prompt, never in a shell command or
source file:

```sh
xcrun notarytool store-credentials dcp-j315w-cups
```

Use your Developer Team ID and an app-specific Apple ID password, or an App Store
Connect API key according to Apple's instructions. Then:

```sh
./notarize-macos-installer.sh dist/dcp-j315w-cups-0.1.1-macos-universal.pkg dcp-j315w-cups
```

The helper waits for up to 60 seconds and prints the submission ID before waiting.
If Apple needs longer, resume that submission with `notarytool wait`; do not
resubmit. After acceptance, staple and validate the ticket, then run Gatekeeper's
installer assessment. Only publish after these checks pass:

```sh
xcrun stapler staple dist/dcp-j315w-cups-0.1.1-macos-universal.pkg
xcrun stapler validate dist/dcp-j315w-cups-0.1.1-macos-universal.pkg
spctl --assess --verbose --type install dist/dcp-j315w-cups-0.1.1-macos-universal.pkg
```

The public signing identity is determined by the Apple Developer account. No
private key, password, certificate export or local notarization profile belongs
in the public repository. Recompute release checksums after signing and stapling.
