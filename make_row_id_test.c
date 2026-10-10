#include <cups/raster.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

// Research input: identify where each CUPS raster row appears in the 300-dpi stream.
int main(int argc, char **argv) {
  if (argc != 3) { fprintf(stderr, "usage: %s base.ras output.ras\n", argv[0]); return 2; }
  int in = open(argv[1], O_RDONLY);
  int out = open(argv[2], O_WRONLY | O_CREAT | O_TRUNC, 0644);
  if (in < 0 || out < 0) { perror("open"); return 1; }
  cups_raster_t *r = cupsRasterOpen(in, CUPS_RASTER_READ);
  cups_raster_t *w = cupsRasterOpen(out, CUPS_RASTER_WRITE);
  cups_page_header2_t h;
  if (!r || !w || !cupsRasterReadHeader2(r, &h) ||
      h.cupsBitsPerPixel != 24 || h.cupsWidth < 1163) return 1;
  if (!cupsRasterWriteHeader2(w, &h)) return 1;
  unsigned char *row = malloc(h.cupsBytesPerLine);
  if (!row) return 1;
  for (unsigned y = 0; y < h.cupsHeight; ++y) {
    memset(row, 255, h.cupsBytesPerLine);
    unsigned x0 = 20 + y % 1000;
    for (unsigned x = x0; x < x0 + 16; ++x) memset(row + x * 3, 0, 3);
    if (y >= 1000)
      for (unsigned x = 1120; x < 1136; ++x) memset(row + x * 3, 0, 3);
    if (cupsRasterWritePixels(w, row, h.cupsBytesPerLine) != h.cupsBytesPerLine) return 1;
  }
  free(row);
  cupsRasterClose(r);
  cupsRasterClose(w);
  close(in);
  close(out);
  return 0;
}
