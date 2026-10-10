# DCP-J315W CUPS Driver

An independent, open-source printing driver for the **Brother DCP-J315W**,
for native macOS and Linux printing over Wi-Fi or Ethernet.

**This release supports only the DCP-J315W.** Other printer models have not been
tested and should not be assumed compatible. The project is not affiliated with
or endorsed by Brother.

This project was created with **LLM-assisted coding**, with automated checks and
hands-on printing on a real DCP-J315W guiding development. It began with a simple
wish to keep a working printer usable when its original driver stops keeping up.
I hope it keeps your printer running for a while longer, too.

## Download v0.1.0

Each download contains the native filter, printer description, Bash installer,
uninstaller, documentation and checksums. No compilation or Python is needed to
install a binary download.

| System | Intel / x86_64 | ARM64 |
| --- | --- | --- |
| macOS | [Download](https://github.com/SolenMusic/dcp-j315w-cups/releases/download/v0.1.0/dcp-j315w-cups-0.1.0-macos-x86_64.tar.gz) | [Download](https://github.com/SolenMusic/dcp-j315w-cups/releases/download/v0.1.0/dcp-j315w-cups-0.1.0-macos-arm64.tar.gz) |
| Debian / Ubuntu | [Download](https://github.com/SolenMusic/dcp-j315w-cups/releases/download/v0.1.0/dcp-j315w-cups-0.1.0-linux-debian-x86_64.tar.gz) | [Download](https://github.com/SolenMusic/dcp-j315w-cups/releases/download/v0.1.0/dcp-j315w-cups-0.1.0-linux-debian-arm64.tar.gz) |
| Red Hat / Fedora | [Download](https://github.com/SolenMusic/dcp-j315w-cups/releases/download/v0.1.0/dcp-j315w-cups-0.1.0-linux-fedora-x86_64.tar.gz) | [Download](https://github.com/SolenMusic/dcp-j315w-cups/releases/download/v0.1.0/dcp-j315w-cups-0.1.0-linux-fedora-arm64.tar.gz) |
| Arch / Arch Linux ARM | [Download](https://github.com/SolenMusic/dcp-j315w-cups/releases/download/v0.1.0/dcp-j315w-cups-0.1.0-linux-arch-x86_64.tar.gz) | [Download](https://github.com/SolenMusic/dcp-j315w-cups/releases/download/v0.1.0/dcp-j315w-cups-0.1.0-linux-arch-arm64.tar.gz) |

macOS builds target macOS 11 and later. Linux builds require glibc 2.34 or later
and CUPS 2.x (`libcups.so.2`). Linux bundles use an AlmaLinux 9 ABI baseline; the
three flavours differ in their dependency installer, not in printer rendering.
The ARM Arch download is for **Arch Linux ARM**, a separate distribution.
Minimum OS versions and every distribution release have not been tested on
physical hardware. See [verification and limitations](docs/TESTING.md).

macOS binaries have an ad hoc code signature, **not an Apple Developer ID
signature or notarization**. Installation currently uses Terminal and `sudo`.
A graphical macOS `.pkg` installer can also be built; see
[macOS Installer signing and notarization](docs/MACOS-RELEASE.md).

## Install

Extract the download and open Terminal in the extracted folder. Use the printer's
actual network address in place of the documentation example:

```sh
sudo ./install.sh --address 192.0.2.10
```

On Linux, install missing runtime dependencies first, or use:

```sh
sudo ./install.sh --install-deps --address 192.0.2.10
```

The Linux dependency helper uses `apt-get`, `dnf`, or `pacman`. On Arch it performs
a full `pacman -Syu` upgrade, as required to avoid partial upgrades. Review the
plan using `./install-deps.sh --dry-run` before running it.

For Bonjour discovery instead of a fixed address:

```sh
./discover.sh
sudo ./install.sh --discover
```

Choose **DCP-J315W CUPS Driver** in your application's printer menu. The CUPS queue
is named `DCP_J315W`. Installation does not make it your system default or replace
an existing Brother queue. The default settings are **A4, monochrome, 300 dpi**.
Select **Colour** and **Fine (600 dpi)** for colour artwork.

```sh
lp -d DCP_J315W -o media=A4 -o fit-to-page=true document.pdf
lp -d DCP_J315W -o media=A4 -o ColorModel=Color -o Resolution=600dpi -o fit-to-page=true artwork.pdf
```

Load matching paper in the printer. There is no automatic paper-size detection.
See [installation, upgrades and removal](docs/INSTALL.md) for more details.

## Features

- A4, A5, A6 and US Letter on plain paper, at 300 or 600 dpi.
- Black-only monochrome; colour with basic separation at 300 dpi and measured
  multilevel colour conversion with error diffusion at 600 dpi.
- Multiple pages, page selection, copies, collation and fitting through CUPS.
- Raw network printing on port 9100, including Bonjour discovery.
- Cancellation/error handling and a separate read-only SNMP status helper.
- Native builds on macOS Intel/ARM64 and Linux x86_64/ARM64.

Physical printing has been confirmed on an ARM Mac and a Fedora 41 x86_64 laptop.
The Fedora checks cover A5 monochrome, colour and multiple fitted pages. macOS
checks include A4 documents, A5 borders, and a successful 600 dpi artwork comparison
against the original Brother driver. Automated checks cover all offered paper
profiles and both architectures. This is an initial release; broader real-world
feedback is welcome.

## Limitations

- Network printing only. USB support is planned after the printing implementation.
- No scanning, maintenance commands, firmware updates or ink-percentage estimation.
- No AirPrint/iOS bridge, Windows driver, borderless printing, photo-paper profiles
  or ICC colour management.
- Colour has been visually checked, not instrumentally calibrated. 600 dpi is
  preferred for artwork; 300 dpi colour is basic.
- A6 and Letter are checked offline but have not been physically tested.
- Arch's libcupsfilters 2.2.x PDF-processing regression can produce blank pages
  before rendering reaches this driver. A [QPDF workaround](docs/INSTALL.md#arch-pdf-processing-regression)
  is verified; unrestricted PDF printing on that affected stack is not supported.
- Physical tests of interruption, paper-out, long jobs and every target machine
  remain outstanding. Future macOS releases and CUPS 3 are not guaranteed compatible.

## Build from source

The renderer is C11 and links to the system CUPS library. The installation tools
are shell scripts. Python is used only for developer verification tools.

### macOS

Install Apple's command-line development tools if needed:

```sh
xcode-select --install
./build.sh
```

The build uses Apple's `cups-config` and applies/verifies an ad hoc signature.
To select an architecture explicitly:

```sh
CFLAGS='-arch arm64 -mmacosx-version-min=11.0' ./build.sh
# On an Intel Mac, or to cross-build using Apple's SDK:
CFLAGS='-arch x86_64 -mmacosx-version-min=11.0' ./build.sh
```

### Linux

Install a C compiler and CUPS development headers:

```sh
# Debian / Ubuntu
sudo apt-get install build-essential libcups2-dev
# Red Hat / Fedora
sudo dnf install gcc cups-devel
# Arch / Arch Linux ARM
sudo pacman -Syu --needed base-devel cups
```

Then run `./build.sh` and use `sudo ./install.sh --address PRINTER_ADDRESS`.
The binary is built for the host CPU. `CC`, `CFLAGS`, `LDFLAGS` and `OUTPUT` can
override the compiler, flags and output location. Printer command-header files
must sit beside the executable.

To create a release tarball from a built executable:

```sh
./package.sh macos arm64
# Or, on Linux x86_64:
./package.sh linux-fedora x86_64
```

[Developer checks](docs/TESTING.md) and [printer protocol notes](docs/PROTOCOL.md)
describe the repeatable verification. GitHub Actions builds and checks both CPUs
and generates all eight binary downloads.

## Licence and provenance

The project's source, documentation and functional calibration data are licensed
under [MIT](LICENSE). You may use, modify and redistribute them, including in
commercial software, subject to MIT's notice requirement.

The printer protocol was studied through controlled input/output observations of
the original driver. This is an independent black-box reimplementation, not a
formal clean-room project with separated research and implementation teams.
No Brother driver executable, firmware or ICC profile is distributed. System CUPS
and rendering libraries retain their own licences and are not bundled.
See [provenance](docs/PROVENANCE.md).

## Contributing

Bug reports and small improvements are welcome. Please include your OS, CPU,
printer model, paper size, resolution, colour mode, and relevant CUPS error output.
Remove document contents, usernames and private network addresses before posting
logs. Please do not treat similar printer names as evidence of compatibility.
Contributions are accepted under the project's MIT licence.
