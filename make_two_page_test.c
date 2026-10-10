#include <cups/raster.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char **argv) {
  if (argc != 3) {
    fprintf(stderr, "usage: %s base.ras output.ras\n", argv[0]);
    return 2;
  }
  int in = open(argv[1], O_RDONLY);
  int out = open(argv[2], O_WRONLY | O_CREAT | O_TRUNC, 0644);
  if (in < 0 || out < 0) { perror("open"); return 1; }
  cups_raster_t *r = cupsRasterOpen(in, CUPS_RASTER_READ);
  cups_raster_t *w = cupsRasterOpen(out, CUPS_RASTER_WRITE);
  cups_page_header2_t h;
  if (!r || !w || !cupsRasterReadHeader2(r, &h) ||
      h.cupsBitsPerPixel != 24 || h.cupsBytesPerLine != 3 * h.cupsWidth) {
    fprintf(stderr, "expected RGB24 base raster\n"); return 1;
  }
  unsigned char *row = malloc(h.cupsBytesPerLine);
  if (!row) return 1;
  for (unsigned page = 0; page < 2; ++page) {
    if (!cupsRasterWriteHeader2(w, &h)) return 1;
    for (unsigned y = 0; y < h.cupsHeight; ++y) {
      memset(row, 255, h.cupsBytesPerLine);
      if (y >= 100 && y < 200) {
        unsigned left = page ? 300 : 100;
        for (unsigned x = left; x < left + 100 && x < h.cupsWidth; ++x)
          memset(row + x * 3, 0, 3);
      }
      if (cupsRasterWritePixels(w, row, h.cupsBytesPerLine) != h.cupsBytesPerLine)
        return 1;
    }
  }
  free(row);
  cupsRasterClose(r);
  cupsRasterClose(w);
  close(in);
  close(out);
  return 0;
}
