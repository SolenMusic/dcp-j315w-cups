# Installation and removal

The driver requires a DCP-J315W on the local network and CUPS 2.x. Raw TCP port
9100 must be reachable. The example address `192.0.2.10` is documentation-only.

## Verify a download

The GitHub release provides `SHA256SUMS` for its archives. Inside each extracted
archive is another `SHA256SUMS` covering its files:

```sh
# Linux
sha256sum -c SHA256SUMS
# macOS
shasum -a 256 -c SHA256SUMS
```

## macOS

The graphical `.pkg` installer installs the driver and attempts Bonjour setup.
If no unique printer is found, add it using System Settings and choose
**DCP-J315W CUPS Driver** in the Use menu. Manual configuration is available with
`sudo /Library/Printers/DCPJ315WCUPS/configure.sh --address PRINTER_ADDRESS`.
The instructions below describe the alternative tarball installer.

Choose the ARM64 download for Apple Silicon, or x86_64 for Intel. Extract it, then:

```sh
./install.sh --address 192.0.2.10 --dry-run
sudo ./install.sh --address 192.0.2.10
```

This installs under `/Library/Printers/DCPJ315WCUPS` and creates `DCP_J315W`.
The display name is DCP-J315W CUPS Driver. Public binaries use Developer ID
Application signatures; the universal `.pkg` also has a Developer ID Installer
signature and a stapled notarization ticket. Local source builds use ad hoc
signatures. Building locally is also supported.

For a cloud-managed source checkout that cannot be read by an administrator,
`stage=$(./stage_install.sh)` creates ordinary files in `/private/tmp`;
then run `sudo "$stage/install.sh" --address 192.0.2.10`.

## Linux

Select the tarball matching your CPU and package-manager family. ARM64 is also
called aarch64. All Linux tarballs share a portable AlmaLinux 9 build, with
distribution-specific dependency handling. They are not `.deb` or `.rpm` packages.

```sh
./install-deps.sh --dry-run
sudo ./install-deps.sh
sudo ./install.sh --address 192.0.2.10
```

The dependency helper installs CUPS, cups-filters, Ghostscript, `file` and Avahi.
It starts CUPS and Avahi when systemd is running. It does not install Python.
If these packages are already present, omit it. Net-SNMP is optional for
`status.sh`: install `snmp` on Debian or `net-snmp-utils` on Fedora; on Arch use
`net-snmp`.

The filter is installed in the active CUPS server's `filter/dcp-j315w-cups`
directory. On SELinux systems the installer applies the normal file contexts
using `restorecon`, when available. Do not disable SELinux to troubleshoot.

SteamOS/Steam Deck and other immutable systems may need an installation method
that survives OS updates. The Arch tarball does not bypass their read-only system
policy. A physical Steam Deck test has not yet been performed.

### Arch PDF-processing regression

The Arch stack checked during this release uses libcupsfilters 2.2.x, whose PDFio
rewrite rejects compound PDF stream filters and can silently produce blank pages.
This happens before the driver receives raster data. OpenPrinting documents the
broader regression and a QPDF-based 2.1.2 release:
[upstream notice](https://openprinting.github.io/libcupsfilters-2.1.2).

Until your distribution supplies a corrected PDF-processing stack, normalize an
affected PDF with QPDF before printing it. The Arch dependency helper includes
`qpdf`:

```sh
qpdf --stream-data=uncompress document.pdf normalized.pdf
lp -d DCP_J315W -o media=A4 -o fit-to-page=true normalized.pdf
```

The release's Arch pipeline checks exercise this workaround explicitly. The
driver does not replace your system's PDF filters or silently change documents
submitted from applications. Update the system printing stack when a fix becomes
available; this initial release cannot guarantee arbitrary PDFs on affected Arch
versions.

## Discovery and options

```sh
./discover.sh
sudo ./install.sh --discover
```

Bonjour discovery accepts only the DCP-J315W raw `_pdl-datastream._tcp` service,
rejects ambiguous matches, and can follow an address change when multicast works.
Avahi may need to be running on Linux. Direct `--address` is a fallback.
`--uri` accepts an explicit raw socket or Bonjour URI. `--port` changes the raw
port when used with `--address`; it defaults to 9100.

Use `--queue NAME` to select a different CUPS queue name. Print settings default
to A4, monochrome, 300 dpi. The original Brother queue and system default are
preserved. Match the selected paper size to the loaded paper.

## Upgrade

When the queue has no unfinished jobs:

```sh
sudo ./install.sh
```

An upgrade keeps its connection, supported paper/colour/resolution defaults,
sharing, policy and enabled state. Its display name is updated. Add `--queue NAME`
for a non-default queue. The installer refuses to overwrite another driver's queue.

For the pre-release queue used during development:

```sh
sudo ./install.sh --queue DCP_J315W_Native
```

This migrates its PPD to the release renderer without renaming the CUPS queue.
Pre-release files are retained because other queues may still reference them.

## Remove

```sh
./uninstall.sh --dry-run
sudo ./uninstall.sh
```

Use `--queue NAME` if needed. Removal refuses unfinished jobs and unrelated queues.
It retains shared driver files when another native queue references them, and
removes this project's known files when the final queue is removed. Unexpected
files are retained.

## Status

```sh
./status.sh PRINTER_ADDRESS
```

This reads standard SNMP status without changing printer settings. It reports
printer state, error flags and available supply information. The tested printer
reports “some ink remains” rather than ink percentages; unknown values stay unknown.
A timeout means status is unavailable, not proof that the printer is offline.
