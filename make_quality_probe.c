// Controlled high-resolution inputs for offline protocol reconstruction.
#include <cups/raster.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char **argv) {
  if (argc != 5 && argc != 6) {
    fprintf(stderr, "usage: %s base.ras output.ras blank|box|rows|bars|cube RRGGBB [colour]\n", argv[0]);
    return 2;
  }
  int fd = open(argv[1], O_RDONLY), out = open(argv[2], O_CREAT | O_TRUNC | O_WRONLY, 0644);
  cups_raster_t *reader = cupsRasterOpen(fd, CUPS_RASTER_READ);
  cups_raster_t *writer = cupsRasterOpen(out, CUPS_RASTER_WRITE_COMPRESSED);
  cups_page_header2_t h;
  if (!reader || !writer || !cupsRasterReadHeader2(reader, &h) ||
      h.cupsBitsPerPixel != 24 || h.cupsBytesPerLine != h.cupsWidth * 3 ||
      h.cupsWidth < 2325) return 1;
  unsigned rgb = (unsigned)strtoul(argv[4], NULL, 16);
  if (argc == 6) {
    if (strcmp(argv[5], "colour")) return 2;
    h.cupsInteger[15] = 1;
  }
  unsigned char *row = malloc(h.cupsBytesPerLine);
  if (!row || !cupsRasterWriteHeader2(writer, &h)) return 1;
  for (unsigned y = 0; y < h.cupsHeight; ++y) {
    memset(row, 255, h.cupsBytesPerLine);
    for (unsigned x = 0; x < h.cupsWidth; ++x) {
      if (!strcmp(argv[3], "cube")) {
        if (x >= 32 && x < 32 + 27 * 64 && y >= 32 && y < 32 + 27 * 64) {
          unsigned node = ((y - 32) / 64) * 27 + (x - 32) / 64;
          unsigned levels[3] = {node / 81, (node / 9) % 9, node % 9};
          for (unsigned channel = 0; channel < 3; ++channel)
            row[x * 3 + channel] = levels[channel] == 8 ? 255 : levels[channel] * 32;
        }
        continue;
      }
      int ink = 0;
      if (!strcmp(argv[3], "box")) ink = x >= 200 && x < 400 && y >= 200 && y < 400;
      else if (!strcmp(argv[3], "bars"))
        ink = y >= 200 && y < 240 && (x == 200 || x == 205 || x == 210 || x == 215);
      else if (!strcmp(argv[3], "rows")) {
        unsigned left = 64 + y % 2048;
        unsigned marker = 2220 + (y / 2048) * 20;
        ink = (x >= left && x < left + 12) || (x >= marker && x < marker + 12);
      } else if (strcmp(argv[3], "blank")) return 2;
      if (ink) {
        row[x * 3] = (unsigned char)(rgb >> 16);
        row[x * 3 + 1] = (unsigned char)(rgb >> 8);
        row[x * 3 + 2] = (unsigned char)rgb;
      }
    }
    if (cupsRasterWritePixels(writer, row, h.cupsBytesPerLine) != h.cupsBytesPerLine) return 1;
  }
  free(row);
  cupsRasterClose(reader); cupsRasterClose(writer); close(fd); close(out);
  return 0;
}
