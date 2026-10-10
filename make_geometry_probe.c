// Controlled near-boundary raster shapes; offline fixtures only.
#include <cups/raster.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(int argc, char **argv) {
  if (argc != 4) return 2;
  unsigned width = (unsigned)strtoul(argv[1], NULL, 10);
  unsigned height = (unsigned)strtoul(argv[2], NULL, 10);
  unsigned dpi = (unsigned)strtoul(argv[3], NULL, 10);
  if (width < 500 || width > 6000 || height < 500 || height > 8000 || (dpi != 300 && dpi != 600)) return 2;
  cups_page_header2_t h = {0};
  h.HWResolution[0] = h.HWResolution[1] = dpi;
  h.cupsWidth = width; h.cupsHeight = height;
  h.cupsBitsPerColor = 8; h.cupsBitsPerPixel = 24;
  h.cupsBytesPerLine = width * 3;
  h.cupsColorSpace = CUPS_CSPACE_RGB; h.cupsColorOrder = CUPS_ORDER_CHUNKED;
  h.cupsNumColors = 3; h.NumCopies = 1;
  cups_raster_t *r = cupsRasterOpen(1, CUPS_RASTER_WRITE_COMPRESSED);
  unsigned char *row = malloc(h.cupsBytesPerLine);
  if (!r || !row || !cupsRasterWriteHeader2(r, &h)) return 1;
  for (unsigned y = 0; y < height; ++y) {
    memset(row, 255, h.cupsBytesPerLine);
    for (unsigned x = 0; x < width; ++x) {
      if (x < 4 || x >= width - 4 || y < 4 || y >= height - 4 ||
          (x >= 100 && x < 140 && y >= 100 && y < 160))
        memset(row + x * 3, 0, 3);
    }
    if (cupsRasterWritePixels(r, row, h.cupsBytesPerLine) != h.cupsBytesPerLine) return 1;
  }
  free(row); cupsRasterClose(r); return 0;
}
