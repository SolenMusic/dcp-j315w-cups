# Release procedure

1. Update `VERSION`, PPD `FileVersion`, changelog and download links together.
2. Run the Build and verify workflow for the release source commit. All four CPU
   architecture/package jobs must pass, including macOS Installer lifecycle,
   Alpine musl PDF/installer checks and native Nix store-path checks. The Arch
   PDF test deliberately uses the documented QPDF workaround for its upstream
   regression; retain that limitation in the release notes while it applies.
3. Download that run's Linux tarballs and macOS artifacts. CI's macOS PKGs are
   unsigned packaging checks, not the public signed installer.
4. Combine the checked Mac binaries with `lipo`. Build the universal PKG locally
   using Developer ID Application/Installer identities. Keep keys and credentials
   in the local keychain, outside Git and workflow artifacts.
5. Notarize the signed PKG, staple the accepted ticket, and validate with `stapler`,
   `pkgutil --check-signature` and `spctl --assess --type install`.
6. Extract the signed universal payload and its two CPU slices. Verify their code
   signatures, then package the macOS tarballs using those signed slices.
7. Generate `SHA256SUMS` after signing/stapling. Extract each archive, validate its
   internal manifest, and confirm there are no local logs, private credentials or
   personal print documents in the assets.
8. Tag the source commit as `vVERSION`. Publish the release with the universal
   signed PKG, two Mac tarballs, ten Linux flavour/CPU tarballs and checksums.
9. Check the public asset names, sizes and checksums against the local files, and
   verify the tag refers to the intended source commit.

For `0.1.0`, the glibc Linux flavours share one AlmaLinux 9 build per CPU, checked
on Debian, Fedora and openSUSE, with the x86_64 Arch check and explicit QPDF
workaround. Alpine has separate native musl builds for both CPUs. Nix builds from
source using its own CUPS library, with the included recipe/configuration example.
Do not describe untested hardware or extra distributions as physically verified.

## Native Linux packaging revisions

The `Native Linux packages` workflow repackages checksum-verified release binaries
without changing their driver version. Dispatch it after the binary tarballs are
published. It supports all targets by default, or comma-separated `targets` for
rechecking a particular distro. It builds revisions 1 and 2, verifies real
installation, upgrades and removal, then uploads only revision 1.

Publish the `.deb`, `.rpm`, `.pkg.tar.zst` and `.apk` artifacts only from passing
jobs. Add them to the corresponding driver release, retain existing tarballs and
macOS assets, and extend SHA256SUMS. Keep the original driver tag unchanged and
record a separate `linux-packages-vVERSION-REVISION` source tag for the packaging
implementation. The release notes must link this packaging source and describe
which tests were performed. Use a new package revision for changed payloads;
never silently replace a published native package with different bytes.
