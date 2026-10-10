// Consume a streamed CUPS raster and write small controlled media fixtures.
#include <cups/raster.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char **argv) {
  if (argc != 2) return 2;
  cups_raster_t *input = cupsRasterOpen(0, CUPS_RASTER_READ);
  cups_page_header2_t h;
  if (!input || !cupsRasterReadHeader2(input, &h) || h.cupsBitsPerPixel != 24 ||
      h.cupsBytesPerLine != h.cupsWidth * 3 || h.cupsWidth < 900) return 1;
  const char *names[4] = {"blank", "rows", "yellow", "edges"};
  cups_raster_t *outputs[4] = {0};
  int fds[4];
  for (unsigned kind = 0; kind < 4; ++kind) {
    char path[4096];
    if (snprintf(path, sizeof(path), "%s-%s.ras", argv[1], names[kind]) >= (int)sizeof(path)) return 1;
    fds[kind] = open(path, O_CREAT | O_TRUNC | O_WRONLY, 0644);
    outputs[kind] = cupsRasterOpen(fds[kind], CUPS_RASTER_WRITE_COMPRESSED);
    cups_page_header2_t header = h;
    header.cupsInteger[15] = kind == 2;
    if (!outputs[kind] || !cupsRasterWriteHeader2(outputs[kind], &header)) return 1;
  }
  unsigned char *row = malloc(h.cupsBytesPerLine);
  if (!row) return 1;
  for (unsigned y = 0; y < h.cupsHeight; ++y) {
    if (cupsRasterReadPixels(input, row, h.cupsBytesPerLine) != h.cupsBytesPerLine) return 1;
    for (unsigned kind = 0; kind < 4; ++kind) {
      memset(row, 255, h.cupsBytesPerLine);
      unsigned thickness = h.HWResolution[0] / 150;
      for (unsigned x = 0; x < h.cupsWidth; ++x) {
        unsigned period = h.cupsWidth < 1600 ? 512 : 1024;
        unsigned left = 16 + y % period;
        unsigned marker = (h.cupsWidth < 1600 ? 700 : 1400) + (y / period) * 32;
        int active = kind == 1 || kind == 2 ?
          ((x >= left && x < left + 16) || (x >= marker && x < marker + 16)) :
          kind == 3 && (x < thickness || x + thickness >= h.cupsWidth ||
                        y < thickness || y + thickness >= h.cupsHeight);
        if (active) {
          row[x * 3] = row[x * 3 + 1] = kind == 2 ? 255 : 0;
          row[x * 3 + 2] = 0;
        }
      }
      if (cupsRasterWritePixels(outputs[kind], row, h.cupsBytesPerLine) != h.cupsBytesPerLine) return 1;
    }
  }
  cups_page_header2_t next;
  if (cupsRasterReadHeader2(input, &next)) {
    fprintf(stderr, "expected one input page\n");
    return 1;
  }
  for (unsigned kind = 0; kind < 4; ++kind) { cupsRasterClose(outputs[kind]); close(fds[kind]); }
  cupsRasterClose(input); free(row);
  fprintf(stderr, "%ux%u, %u dpi\n", h.cupsWidth, h.cupsHeight, h.HWResolution[0]);
  return 0;
}
