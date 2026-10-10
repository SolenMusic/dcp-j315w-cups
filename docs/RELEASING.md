# Release procedure

1. Update `VERSION`, PPD `FileVersion`, changelog and download links together.
2. Run the Build and verify workflow for the release source commit. All four CPU
   jobs must pass, including the actual macOS Installer lifecycle checks. The Arch
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
   signed PKG, two Mac tarballs, six Linux flavour/CPU tarballs and checksums.
9. Check the public asset names, sizes and checksums against the local files, and
   verify the tag refers to the intended source commit.

For `0.1.0`, the runtime Linux flavours share one AlmaLinux 9 build per CPU, checked
on Debian and Fedora, with the x86_64 Arch check and explicit QPDF workaround.
Do not describe untested hardware or extra distributions as physically verified.
