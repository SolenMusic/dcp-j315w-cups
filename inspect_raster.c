// Count actual raster pages, including copies expanded by the macOS RIP.
#include <cups/raster.h>
#include <stdio.h>
#include <stdlib.h>
int main(void) {
  cups_raster_t *r = cupsRasterOpen(0, CUPS_RASTER_READ);
  cups_page_header2_t h;
  unsigned pages = 0;
  while (cupsRasterReadHeader2(r, &h)) {
    unsigned char *row = malloc(h.cupsBytesPerLine);
    if (!row) return 1;
    for (unsigned y = 0; y < h.cupsHeight; ++y)
      if (cupsRasterReadPixels(r, row, h.cupsBytesPerLine) != h.cupsBytesPerLine)
        return 1;
    free(row);
    fprintf(stderr, "page %u: %ux%u dpi=%u NumCopies=%u\n", ++pages,
            h.cupsWidth, h.cupsHeight, h.HWResolution[0], h.NumCopies);
  }
  printf("%u\n", pages);
  cupsRasterClose(r);
  return pages ? 0 : 1;
}
