# Printer protocol notes

Supported modes use a canonical printable raster canvas. Small differences from
metric IPP dimensions versus rounded PPD point dimensions are normalized using
bounded separable bilinear interpolation (up to 3 pixels at 300 dpi, 6 at 600 dpi).
Larger/custom raster dimensions are rejected. Exact-size input preserves the
verified output bytes.

| Paper | 300 dpi canvas | 600 dpi canvas |
| --- | --- | --- |
| A4 | 2404 × 3433 | 4808 × 6867 |
| A5 | 1675 × 2404 | 3350 × 4808 |
| A6 | 1163 × 1675 | 2325 × 3350 |
| Letter | 2475 × 3225 | 4950 × 6450 |

The input is chunked RGB24 CUPS raster. The PPD selects monochrome or colour in
`cupsInteger[15]`. Monochrome always uses the black ink slot. At 600 dpi, colour
conversion interpolates a measured 9 × 9 × 9 RGB table and diffuses categorical
dot-code probabilities in source row order before nozzle interlacing.

A job starts with 4096 zero bytes and an 820-byte mode-specific prologue.
Later pages omit the first 7 reset bytes. `I1` starts the image, then `F` commands
advance the paper. Active passes begin with `ivT2` plus byte 1 and contain 93
rows of five ink slots: C, M, Y, reserved, K. Reserved slots remain empty.

`Z` encodes an empty slot. `G` carries a little-endian two-byte payload length,
then run-length encoded packed pixels. The low five bits of each control byte
give a zero-byte count; the upper three give the following literal-byte count.
300 dpi packs two 4-bit pixels per byte; 600 dpi packs four 2-bit pixels per byte.

300 dpi interlaces two row phases; 600 dpi uses four, with 93 rows per pass.
The renderer applies the observed CMY registration offset relative to K:
one input row at 300 dpi, two at 600 dpi. See `inspect_protocol.py` for an
independent inverse mapping and stream validation.

Each completed page ends with form-feed. The final page ends with `ESC @` and
4096 zero bytes. A later-page preparation failure resets an already-open job
without emitting an extra blank-page eject. Cancellation finishes an active
nozzle pass before closing the page. CUPS/network buffering can still deliver
data already sent when a user cancels; physical interruption behaviour needs
further testing.

150 dpi A4/A6 profiles remain internal research fixtures, are not offered in
the PPD, and are not supported release print settings.
