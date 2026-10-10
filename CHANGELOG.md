# Changelog

## 0.1.0

Initial public release of DCP-J315W CUPS Driver.

- Native macOS Intel/ARM64 and Linux x86_64/ARM64 builds.
- A4/A5/A6/Letter plain-paper printing at 300/600 dpi.
- Black-only monochrome and 600 dpi colour with measured conversion and error diffusion.
- Multi-page jobs, CUPS print options, raw network transport and Bonjour discovery.
- Bounded normalization of metric/PPD raster rounding differences, verified on Fedora 41.
- Cancellation, truncated-job recovery, error reporting and read-only SNMP status.
- Bash installation, guarded upgrades/removal and distribution-specific Linux bundles.
- A universal graphical macOS Installer with Developer ID signing and notarization tooling.
- Actual PKG installation, upgrade, held-job protection and removal checks on both macOS CPUs.
- A documented and verified QPDF workaround for Arch's upstream PDF-processing regression.
- Build instructions, automated verification, MIT licensing and documented provenance.
- Production driver names and controls without prototype or experimental labels.

USB, scanning, AirPrint bridging, Windows and photo-media calibration are not included.
