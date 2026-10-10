# Provenance

This driver was written with LLM-assisted coding and refined through controlled
protocol checks and physical prints on a Brother DCP-J315W.

- `rastertodcpj315w.c` implements the independently written renderer, compression,
  interlacing, bounded raster normalization and job/error handling.
- `prologue_*.bin` are 820-byte functional printer command sequences recorded
  during controlled black-box experiments. They are printer-language data,
  not native code, firmware or copies of a driver executable.
- `colour600_table.h` records measured dot-code distributions for 729 controlled
  RGB patches. It contains observed conversion behaviour, not an ICC profile.
  `derive_colour_table.py` documents how the table was computed.
- The PPD and shell installers were written for this project.
- The committed raster and PDF fixtures contain project-generated shapes, text
  and colour patterns. Personal print jobs, concept artwork, photographs and
  machine logs are not part of the repository or release archives.

The research and implementation were not separated into independent teams.
Accordingly this is described as a black-box reimplementation, not a strict
formal clean-room effort. No decompiled or disassembled vendor implementation
is included.

The project is licensed under MIT. CUPS, Ghostscript, operating-system libraries
and development tools are external dependencies with their own licences; the
binary tarballs do not bundle them. Brother's name identifies the compatible
hardware and does not imply affiliation or endorsement.
