// Small compressed fixtures for job handling checks; never sent to a printer.
#include <cups/raster.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(int argc, char **argv) {
  if (argc != 3 && argc != 4) return 2;
  int legacy = argc == 4 && !strcmp(argv[3], "legacy150");
  if (argc == 4 && !legacy) return 2;
  int pages = atoi(argv[1]), dense = atoi(argv[2]);
  cups_raster_t *r = cupsRasterOpen(1, CUPS_RASTER_WRITE_COMPRESSED);
  cups_page_header2_t h = {0};
  h.HWResolution[0] = h.HWResolution[1] = 300;
  h.cupsWidth = 2404; h.cupsHeight = 3433;
  h.cupsBitsPerColor = 8; h.cupsBitsPerPixel = 24;
  h.cupsBytesPerLine = h.cupsWidth * 3;
  h.cupsColorSpace = CUPS_CSPACE_RGB;
  h.cupsColorOrder = CUPS_ORDER_CHUNKED;
  h.cupsNumColors = 3; h.NumCopies = 1;
  h.PageSize[0] = 595; h.PageSize[1] = 842;
  if (legacy) {
    h.HWResolution[0] = h.HWResolution[1] = 150;
    h.cupsWidth = 581; h.cupsHeight = 838;
    h.cupsBytesPerLine = h.cupsWidth * 3;
    h.PageSize[0] = 297; h.PageSize[1] = 420;
  }
  unsigned char *row = malloc(h.cupsBytesPerLine);
  if (!r || !row || pages < 1) return 1;
  for (int page = 0; page < pages; ++page) {
    if (!cupsRasterWriteHeader2(r, &h)) return 1;
    for (unsigned y = 0; y < h.cupsHeight; ++y) {
      memset(row, dense ? 0 : 255, h.cupsBytesPerLine);
      if (!dense && y >= 100 && y < 120)
        memset(row + (100 + page * 40) * 3, 0, 60);
      if (cupsRasterWritePixels(r, row, h.cupsBytesPerLine) != h.cupsBytesPerLine)
        return 1;
    }
  }
  cupsRasterClose(r);
  free(row);
  return 0;
}
