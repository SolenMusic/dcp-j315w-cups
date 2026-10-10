# Verification

Developer checks use Python 3's standard library; optional PDF-fixture regeneration
and preview generation use ReportLab/Pillow. Neither Python nor these packages
are needed to install or print.

## Offline checks

```sh
./build.sh
python3 test_reliability.py
python3 test_discovery.py
python3 test_status.py
cc -std=c11 make_geometry_probe.c $(cups-config --cflags --ldflags --libs) -o /tmp/make_geometry_probe
python3 test_geometry.py /tmp/make_geometry_probe
```

The checks verify independently walked printer framing, exact baseline outputs,
truncated pages, recovery, cancellation, broken output pipes, discovery selection,
status decoding and metric raster variations. `DCPJ315W_FILTER` can select a
temporary materialized executable. Place `prologue_*.bin` beside it.

On macOS, `python3 test_macos.py` exercises the full PDF/CUPS pipeline without
submitting a job. On Linux, `python3 test_linux.py` checks all four paper sizes,
300 dpi monochrome, 600 dpi colour and collated copies through CUPS/Ghostscript.
`test_socket_backend.py` uses a local simulated printer only.

```sh
docker build -f Dockerfile.linux-test -t dcp-j315w-check .
docker run --rm dcp-j315w-check
docker run --rm dcp-j315w-check python3 test_installation_linux.py
```

`test_installation_linux.py` refuses to run outside a disposable Docker container.
It tests create/upgrade/remove operations, shared files and held-job protection.
Do not run it on a personal CUPS server.

GitHub Actions builds both macOS CPUs and both Linux CPUs. Linux release binaries
are built against AlmaLinux 9, then run through Debian/Fedora PDF pipeline and
installer checks. An additional x86_64 Arch check uses Arch's native CUPS stack.
The same glibc build is checked on openSUSE Tumbleweed for both CPUs. Alpine 3.24
gets separate native musl builds, the full PDF pipeline and installer lifecycle
checks. The native Nix derivation builds/checks both CPUs and verifies that the
installed filter can locate its command data in the Nix store. These additions
have not been physically tested with the printer.
The Arch PDF check uses the documented qpdf normalization workaround for an
upstream libcupsfilters 2.2.x/PDFio regression. It does not establish that all PDFs
work with the affected unmodified system pipeline. The ARM Arch tarball shares
the checked ARM64 ELF but is not an Arch Linux ARM
hardware certification.

`test_macos_installer.py` checks the actual unsigned PKG's installation, upgrade,
held-job protection and removal in disposable GitHub macOS runners only. It refuses
to run unless explicitly placed in that environment and never submits a printable
job. Do not run it on your personal Mac.

## Physical checks completed before v0.1.0

| Environment | Confirmed |
| --- | --- |
| macOS, ARM64, Wi-Fi DCP-J315W | A4 text and multiple pages; A5 even borders; page selection and fitted landscape/oversized pages; Bonjour printing; 600 dpi colour artwork comparison |
| Fedora 41, x86_64, Wi-Fi DCP-J315W | A5 monochrome at 300 dpi; A5 colour at 600 dpi; two selected A5 pages in order with complete fitted frames |

The Fedora laptop ran CUPS 2.4.14, cups-filters 2.0.1 and Ghostscript 10.03.1.
Its initial metric raster-size mismatch was fixed by bounded normalization and
retested physically. Controlled regression streams retained their original bytes.

Physical Intel Mac, ARM Linux, Steam Deck, A6, Letter, copy collation, long jobs,
network interruption, paper-out and active cancellation checks remain outstanding.
ICC accuracy and photo media have not been calibrated. Physical feedback is
model-specific and must not be generalized to other Brother printers.
