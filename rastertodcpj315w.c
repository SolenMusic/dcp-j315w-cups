// DCP-J315W CUPS Driver: A4/A5/A6/Letter, monochrome and colour.
// The command framing and RLE were derived from black-box output comparisons.
// Native macOS and Linux builds share the same printer-language renderer.

#if defined(__linux__)
#define _GNU_SOURCE
#endif

#include <cups/raster.h>
#include <errno.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <signal.h>
#include <poll.h>
#include "colour600_table.h"
#if defined(__APPLE__)
#include <mach-o/dyld.h>
#endif

enum { ZERO_PAD = 4096, PROLOGUE_BYTES = 820, MAX_LINE_BYTES = 1240 };

static volatile sig_atomic_t cancelled = 0;

static void cancel_job(int signum) {
  (void)signum;
  cancelled = 1;
}

// The libcups default reader retries interrupted reads. Use a cancellable
// callback so SIGTERM also works while waiting for the next raster header.
typedef struct {
  int fd, failed;
  unsigned char buffer[65536];
  size_t begin, end;
  uint64_t delivered;
  unsigned char *row;
  size_t row_size;
} raster_input_t;

static ssize_t read_raster(void *context, unsigned char *buffer, size_t length) {
  raster_input_t *source = context;
  if (cancelled) return 0;
  // Keep libcups from buffering across page boundaries: compressed input's
  // eager reads otherwise hide partial headers as ordinary EOF. Our own
  // buffer keeps small reads inexpensive. Direct reads into the active pixel
  // row can remain large because they cannot consume the next page header.
  uintptr_t target = (uintptr_t)buffer, row = (uintptr_t)source->row;
  if (!source->row || target < row || target - row >= source->row_size)
    length = length ? 1 : 0;
  if (!length) return 0;
  struct pollfd input = {source->fd, POLLIN, 0};
  while (!cancelled && source->begin == source->end) {
    int ready = poll(&input, 1, 250);
    if (ready < 0) {
      if (errno == EINTR) continue;
      source->failed = 1;
      return -1;
    }
    if (!ready) continue;
    ssize_t count = read(source->fd, source->buffer, sizeof(source->buffer));
    if (count < 0 && errno == EINTR) continue;
    if (count < 0) source->failed = 1;
    if (count <= 0) return count;
    source->begin = 0;
    source->end = (size_t)count;
  }
  if (cancelled) return 0;
  if (length > source->end - source->begin) length = source->end - source->begin;
  memcpy(buffer, source->buffer + source->begin, length);
  source->begin += length;
  source->delivered += length;
  return (ssize_t)length;
}

typedef struct {
  unsigned width, height, line_bytes, regions, dpi, rows_per_region;
  const char *prologue_file;
  int footer_zero;
} profile_t;

static const profile_t profiles[] = {
  {581, 838, 292, 9, 150, 94, "prologue_a6_150.bin", 0},
  {1202, 1717, 604, 19, 150, 94, "prologue_a4_150.bin", 1},
  {1163, 1675, 584, 20, 300, 93, "prologue_a6_300.bin", 0},
  {2404, 3433, 1204, 38, 300, 93, "prologue_a4_300.bin", 0},
  {2325, 3350, 582, 40, 600, 93, "prologue_a6_600.bin", 0},
  {4808, 6867, 1202, 77, 600, 93, "prologue_a4_600.bin", 0},
  {1675, 2404, 840, 27, 300, 93, "prologue_a5_300.bin", 0},
  {3350, 4808, 838, 55, 600, 93, "prologue_a5_600.bin", 0},
  {2475, 3225, 1240, 36, 300, 93, "prologue_letter_300.bin", 0},
  {4950, 6450, 1238, 73, 600, 93, "prologue_letter_600.bin", 0},
};

static int write_all(const void *data, size_t size) {
  const unsigned char *p = data;
  while (size) {
    ssize_t n = write(STDOUT_FILENO, p, size);
    if (n < 0) {
      if (errno == EINTR) continue;
      if (!cancelled) perror("ERROR: Printer stream write failed");
      return 0;
    }
    if (n == 0) { fprintf(stderr, "ERROR: Short printer stream write\n"); return 0; }
    p += n;
    size -= (size_t)n;
  }
  return 1;
}

static int write_zeros(size_t count) {
  static const unsigned char zeros[ZERO_PAD] = {0};
  while (count) {
    size_t n = count < sizeof(zeros) ? count : sizeof(zeros);
    if (!write_all(zeros, n)) return 0;
    count -= n;
  }
  return 1;
}

static int close_open_job(void) {
  // The previous completed page already ejected; do not add a blank sheet.
  return write_all("\x1b@", 2) && write_zeros(ZERO_PAD);
}

static int nearby_dimension(unsigned input, unsigned expected, unsigned dpi) {
  unsigned difference = input > expected ? input - expected : expected - input;
  // Up to roughly 0.25 mm: metric IPP sizes and rounded PPD points can produce
  // a few different pixels. Large/custom geometries remain unsupported.
  return input && difference <= (dpi + 99) / 100;
}

typedef struct { unsigned low, high, part, total; } sample_axis_t;

static sample_axis_t sample_axis(unsigned output, unsigned count, unsigned input) {
  sample_axis_t axis = {0, 0, 0, 2 * count};
  int64_t position = (int64_t)(2 * output + 1) * input - count;
  if (position <= 0) return axis;
  if ((uint64_t)position >= (uint64_t)(input - 1) * axis.total) {
    axis.low = axis.high = input - 1;
    return axis;
  }
  axis.low = (unsigned)(position / axis.total);
  axis.high = axis.low + 1;
  axis.part = (unsigned)(position % axis.total);
  return axis;
}

static unsigned char blend(unsigned char a, unsigned char b, sample_axis_t axis) {
  return (unsigned char)((a * (axis.total - axis.part) + b * axis.part + axis.total / 2) / axis.total);
}

static int normalize_geometry(unsigned char *pixels, unsigned input_width,
                              unsigned input_height, unsigned stride,
                              const profile_t *profile) {
  unsigned width = profile->width, height = profile->height;
  unsigned output_stride = width * 3;
  unsigned char *row = NULL;
  sample_axis_t *columns = NULL;
  if (input_width != width) {
    row = malloc(output_stride);
    columns = malloc((size_t)width * sizeof(*columns));
    if (!row || !columns) {
      perror("ERROR: Cannot allocate geometry conversion buffers");
      free(row); free(columns); return 0;
    }
    for (unsigned x = 0; x < width; ++x) columns[x] = sample_axis(x, width, input_width);
  }
  // Each horizontal row uses a small temporary buffer; compact wider input
  // strides forward so later source rows remain intact.
  for (unsigned y = 0; y < input_height; ++y) {
    if (cancelled) { free(row); free(columns); return 0; }
    unsigned char *source = pixels + (size_t)y * stride;
    if (row) {
      for (unsigned x = 0; x < width; ++x)
        for (unsigned channel = 0; channel < 3; ++channel)
          row[x * 3 + channel] = blend(source[columns[x].low * 3 + channel],
                                      source[columns[x].high * 3 + channel], columns[x]);
      memcpy(source, row, output_stride);
    }
    memmove(pixels + (size_t)y * output_stride, source, output_stride);
  }
  free(row); free(columns);
  // Shrink from the beginning or expand from the end. The source rows used
  // by interpolation cannot have been overwritten by an earlier output row.
  if (input_height != height) {
    for (unsigned index = 0; index < height; ++index) {
      if (cancelled) return 0;
      unsigned y = height > input_height ? height - 1 - index : index;
      sample_axis_t axis = sample_axis(y, height, input_height);
      unsigned char *target = pixels + (size_t)y * output_stride;
      const unsigned char *low = pixels + (size_t)axis.low * output_stride;
      const unsigned char *high = pixels + (size_t)axis.high * output_stride;
      for (unsigned byte = 0; byte < output_stride; ++byte)
        target[byte] = blend(low[byte], high[byte], axis);
    }
  }
  return 1;
}

static int read_prologue(const profile_t *profile,
                         unsigned char out[PROLOGUE_BYTES]) {
  char path[PATH_MAX];
  const char *override = getenv("DCPJ315W_PROLOGUE");
  if (override && *override) {
    if (snprintf(path, sizeof(path), "%s", override) >= (int)sizeof(path)) return 0;
  } else {
#if defined(__APPLE__)
    uint32_t path_size = sizeof(path);
    if (_NSGetExecutablePath(path, &path_size) != 0) return 0;
#elif defined(__linux__)
    ssize_t path_size = readlink("/proc/self/exe", path, sizeof(path) - 1);
    if (path_size < 0 || (size_t)path_size >= sizeof(path) - 1) return 0;
    path[path_size] = '\0';
#else
#error Unsupported platform
#endif
    char *slash = strrchr(path, '/');
    if (!slash || (size_t)(slash - path) + strlen(profile->prologue_file) + 2 > sizeof(path))
      return 0;
    strcpy(slash + 1, profile->prologue_file);
  }
  int fd = open(path, O_RDONLY);
  if (fd < 0) { perror("ERROR: Cannot open printer command header"); return 0; }
  size_t done = 0;
  while (done < PROLOGUE_BYTES) {
    ssize_t n = read(fd, out + done, PROLOGUE_BYTES - done);
    if (n < 0 && errno == EINTR) continue;
    if (n <= 0) { fprintf(stderr, "ERROR: Short printer command header: %s\n", path); close(fd); return 0; }
    done += (size_t)n;
  }
  unsigned char extra;
  ssize_t extra_size;
  do { extra_size = read(fd, &extra, 1); } while (extra_size < 0 && errno == EINTR);
  int valid = extra_size == 0;
  close(fd);
  if (!valid) fprintf(stderr, "ERROR: Printer command header is not 820 bytes: %s\n", path);
  return valid;
}

// Each control byte has a 5-bit zero-byte count and a 3-bit literal-byte count.
// The literal bytes immediately follow. Lines contain packed 2- or 4-bit pixels.
static size_t encode_line(const unsigned char *row, size_t line_bytes,
                          unsigned char *out) {
  size_t input = 0, output = 0;
  while (input < line_bytes) {
    size_t blank = 0;
    while (input + blank < line_bytes && row[input + blank] == 0) ++blank;
    while (blank >= 31) {
      out[output++] = 31;
      input += 31;
      blank -= 31;
    }
    if (input + blank == line_bytes) {
      if (blank) out[output++] = (unsigned char)blank;
      break;
    }
    size_t literals = 0;
    while (input + blank + literals < line_bytes &&
           row[input + blank + literals] != 0 && literals < 7) ++literals;
    out[output++] = (unsigned char)((literals << 5) | blank);
    memcpy(out + output, row + input + blank, literals);
    output += literals;
    input += blank + literals;
  }
  return output;
}

// At 300 dpi the K nozzle rows are interlaced across alternating passes.
// Controlled row-ID captures established this bijection for A4 and A6.
static void map_300_row(unsigned y, unsigned *region, unsigned *row) {
  if (y & 1) {
    unsigned half = (y - 1) / 2;
    *region = 1 + 2 * (half / 93);
    *row = half % 93;
  } else {
    unsigned half = y / 2;
    if (half < 47) { *region = 0; *row = 46 + half; }
    else {
      half -= 47;
      *region = 2 + 2 * (half / 93);
      *row = half % 93;
    }
  }
}

// At 600 dpi four phases share 93-nozzle passes. CMY's source rows use
// this map with y + 2; separate controlled colour row captures show that offset.
static void map_600_row(unsigned y, unsigned *region, unsigned *row) {
  unsigned phase = y & 3;
  unsigned position = y / 4 + (3 - phase) * 23;
  *region = phase + 4 * (position / 93);
  *row = position % 93;
}

static void pack_ink(unsigned char *line, unsigned x, unsigned char ink,
                     unsigned dpi) {
  if (dpi == 600) {
    // Single-pixel bar captures establish two bits per 600-dpi source pixel.
    line[x / 4] |= (unsigned char)((ink & 3u) << (6 - 2 * (x & 3)));
  } else {
    line[x / 2] |= (unsigned char)(x & 1 ? ink : ink << 4);
  }
}

static unsigned halftone_threshold(unsigned x, unsigned y) {
  static const unsigned char bayer[4][4] = {
    { 0,  8,  2, 10}, {12,  4, 14,  6},
    { 3, 11,  1,  9}, {15,  7, 13,  5}
  };
  return 16u * bayer[y & 3][x & 3] + 8;
}

static void colour600_probabilities(const unsigned char *rgb,
                                    unsigned char probabilities[4][3]) {
  // Cache only RGB-to-ink probabilities; the spatial halftone is still applied
  // per pixel. This keeps repeated artwork colours inexpensive to render.
  static struct {
    uint32_t key;
    unsigned char probabilities[4][3];
  } cache[4096];
  uint32_t colour = ((uint32_t)rgb[0] << 16) | ((uint32_t)rgb[1] << 8) | rgb[2];
  unsigned bucket = (colour * 2654435761u) >> 20;
  if (cache[bucket].key != colour + 1) {
    unsigned base[3], fraction[3], sums[4][3] = {{0}};
    for (unsigned axis = 0; axis < 3; ++axis) {
      base[axis] = rgb[axis] >> 5;
      fraction[axis] = base[axis] == 7 ?
        (rgb[axis] - 224u) * 256u / 31u : (rgb[axis] & 31u) * 8u;
    }
    for (unsigned corner = 0; corner < 8; ++corner) {
      unsigned r = corner & 1, g = (corner >> 1) & 1, b = (corner >> 2) & 1;
      unsigned weight = (r ? fraction[0] : 256u - fraction[0]) *
                        (g ? fraction[1] : 256u - fraction[1]) *
                        (b ? fraction[2] : 256u - fraction[2]);
      if (!weight) continue;
      unsigned node = ((base[0] + r) * 9 + base[1] + g) * 9 + base[2] + b;
      for (unsigned channel = 0; channel < 4; ++channel)
        for (unsigned level = 0; level < 3; ++level)
          sums[channel][level] += weight * colour600_table[node][channel][level];
    }
    for (unsigned channel = 0; channel < 4; ++channel)
      for (unsigned level = 0; level < 3; ++level)
        cache[bucket].probabilities[channel][level] =
          (unsigned char)((sums[channel][level] + (1u << 23)) >> 24);
    cache[bucket].key = colour + 1;
  }
  memcpy(probabilities, cache[bucket].probabilities, 12);
}

static int prepare_colour600(unsigned char *pixels, const profile_t *profile) {
  enum { ERROR_SCALE = 4096 };
  // Diffuse categorical probabilities in source-image order, before nozzle
  // interlacing. Each channel selects one of four physical dot codes.
  // Convert RGB to one packed CMYK byte in place; the first row is traversed
  // forwards, and every later destination row precedes its unread RGB source.
  size_t stride = ((size_t)profile->width + 2) * 16;
  int32_t *errors = calloc(stride * 2, sizeof(*errors));
  if (!errors) { perror("ERROR: Cannot allocate colour halftone buffer"); return 0; }
  int32_t *current = errors, *next = errors + stride;
  for (unsigned y = 0; y < profile->height; ++y) {
    if (cancelled) { free(errors); return 0; }
    memset(next, 0, stride * sizeof(*next));
    int direction = y & 1 ? -1 : 1;
    int x = direction > 0 ? 0 : (int)profile->width - 1;
    for (unsigned n = 0; n < profile->width; ++n, x += direction) {
      size_t pixel = (size_t)y * profile->width + (unsigned)x;
      unsigned char rgb[3], probabilities[4][3], packed = 0;
      memcpy(rgb, pixels + pixel * 3, 3);
      if (rgb[0] == 255 && rgb[1] == 255 && rgb[2] == 255) {
        pixels[pixel] = 0;
        continue;
      }
      colour600_probabilities(rgb, probabilities);
      for (unsigned channel = 0; channel < 4; ++channel) {
        unsigned distribution[4] = {
          255u - probabilities[channel][0],
          probabilities[channel][0] - probabilities[channel][1],
          probabilities[channel][1] - probabilities[channel][2],
          probabilities[channel][2]
        };
        unsigned chosen = 0;
        int deterministic = 0;
        int32_t adjusted[4];
        size_t index = ((size_t)x + 1) * 16 + channel * 4;
        for (unsigned level = 0; level < 4; ++level) {
          adjusted[level] = (int32_t)distribution[level] * ERROR_SCALE + current[index + level];
          if (adjusted[level] > adjusted[chosen]) chosen = level;
          if (distribution[level] == 255) { chosen = level; deterministic = 1; break; }
        }
        packed |= (unsigned char)(chosen << (6 - 2 * channel));
        // Deterministic white/solid inks consume incoming error without
        // introducing stray dots outside artwork or into exact black text.
        if (deterministic) continue;
        size_t ahead = (size_t)(x + 1 + direction) * 16 + channel * 4;
        size_t behind = (size_t)(x + 1 - direction) * 16 + channel * 4;
        for (unsigned level = 0; level < 4; ++level) {
          int32_t error = adjusted[level] - (level == chosen ? 255 * ERROR_SCALE : 0);
          current[ahead + level] += error * 7 / 16;
          next[behind + level] += error * 3 / 16;
          next[index + level] += error * 5 / 16;
          next[ahead + level] += error / 16;
        }
      }
      pixels[pixel] = packed;
    }
    int32_t *swap = current; current = next; next = swap;
  }
  free(errors);
  return 1;
}

static void unpack_inks(unsigned char packed, unsigned char out[4]) {
  for (unsigned channel = 0; channel < 4; ++channel)
    out[channel] = (packed >> (6 - 2 * channel)) & 3;
}

// Legacy RGB path for 150/300 dpi colour and black-only output at all resolutions.
// 600 dpi colour is prepared separately in source-image order.
static void ink_nibbles(const unsigned char *rgb, unsigned x, unsigned y,
                        int colour, unsigned char out[4]) {
  memset(out, 0, 4);
  if (colour) {
    unsigned c = 255u - rgb[0], m = 255u - rgb[1], yellow = 255u - rgb[2];
    unsigned k = c < m ? c : m;
    if (yellow < k) k = yellow;
    unsigned coverage[4] = {c - k, m - k, yellow - k, k};
    for (unsigned channel = 0; channel < 4; ++channel)
      if (coverage[channel] > halftone_threshold(x + channel, y + channel * 2))
        out[channel] = 0x0f;
    return;
  }
  unsigned grey = (54u * rgb[0] + 183u * rgb[1] + 19u * rgb[2] + 128) >> 8;
  if (grey < halftone_threshold(x, y)) out[3] = 0x0f;
}

static int print_page(const cups_page_header2_t *h, const unsigned char *pixels,
                      const unsigned char prologue[PROLOGUE_BYTES],
                      const profile_t *profile, int colour, int first, int last) {
  int packed_inks = colour && profile->dpi == 600;
  const unsigned char start[] = {'I', 0x10};
  const unsigned char start_300[] = {'I', 0x31};
  const unsigned char feed_150[] = {'F', 0xc0, 0x3a};
  const unsigned char feed_300[] = {'F', 0x10, 0x1d};
  const unsigned char feed_600[] = {'F', 0x88, 0x0e};
  const unsigned char region_marker[] = {'i', 'v', 'T', '2', 0x01};
  const unsigned char end_a6[] = {0x0c, 0x1b, '@'};
  const unsigned char end_a4[] = {0x0c, 0x00, 0x1b, '@'};
  // The reset sequence occurs only at the beginning of a job. Later pages
  // reuse the same 820-byte header, omitting its first seven reset bytes.
  unsigned row_map[2][77 * 94];
  for (unsigned kind = 0; kind < 2; ++kind) {
    for (unsigned k = 0; k < 77 * 94; ++k) row_map[kind][k] = UINT_MAX;
    for (unsigned y = 0; y < profile->height; ++y) {
      unsigned region, row;
      if (profile->dpi == 600) map_600_row(y + (kind ? 2 : 0), &region, &row);
      else if (profile->dpi == 300) map_300_row(y + (kind ? 1 : 0), &region, &row);
      else { region = y / 94; row = y % 94; }
      if (region >= profile->regions || row >= profile->rows_per_region) return 0;
      row_map[kind][region * profile->rows_per_region + row] = y;
    }
  }
  if ((first && !write_zeros(ZERO_PAD)) ||
      !write_all(prologue + (first ? 0 : 7),
                 PROLOGUE_BYTES - (first ? 0 : 7)) ||
      !write_all(profile->dpi >= 300 ? start_300 : start, 2)) return 0;

  for (unsigned region = 0; region < profile->regions; ++region) {
    if (cancelled) goto finish_page;
    // Observed in A4 jobs with a following page, immediately before the
    // final three feed commands of the current page.
    if (!last && profile->footer_zero && region == profile->regions - 3 &&
        !write_all("t", 1)) return 0;
    const unsigned char *feed = profile->dpi == 600 ? feed_600 :
                                profile->dpi == 300 ? feed_300 : feed_150;
    if (!write_all(feed, 3)) return 0;
    int active = 0;
    for (unsigned kind = 0; kind < (colour ? 2u : 1u) && !active; ++kind) {
      for (unsigned row = 0; row < profile->rows_per_region && !active; ++row) {
        unsigned y = row_map[kind][region * profile->rows_per_region + row];
        if (y == UINT_MAX) continue;
        const unsigned char *source = pixels + (size_t)y *
          (packed_inks ? profile->width : h->cupsBytesPerLine);
        for (unsigned x = 0; x < profile->width; ++x) {
          unsigned char ink[4];
          if (packed_inks) unpack_inks(source[x], ink);
          else ink_nibbles(source + x * 3, x, y, colour, ink);
          if (kind ? (ink[0] || ink[1] || ink[2]) : ink[3]) { active = 1; break; }
        }
      }
    }
    if (!active) continue;
    if (!write_all(region_marker, sizeof(region_marker))) return 0;

    for (unsigned row = 0; row < profile->rows_per_region; ++row) {
      // Finish the current nozzle pass before honoring SIGTERM at the next
      // region boundary, so all five-slot rows in this pass stay complete.
      unsigned char lines[4][MAX_LINE_BYTES] = {{0}};
      for (unsigned kind = 0; kind < (colour ? 2u : 1u); ++kind) {
        unsigned y = row_map[kind][region * profile->rows_per_region + row];
        if (y == UINT_MAX) continue;
        const unsigned char *source = pixels + (size_t)y *
          (packed_inks ? profile->width : h->cupsBytesPerLine);
        for (unsigned x = 0; x < profile->width; ++x) {
          unsigned char ink[4];
          if (packed_inks) unpack_inks(source[x], ink);
          else ink_nibbles(source + x * 3, x, y, colour, ink);
          if (kind) {
            for (unsigned channel = 0; channel < 3; ++channel)
              pack_ink(lines[channel], x, ink[channel], profile->dpi);
          } else pack_ink(lines[3], x, ink[3], profile->dpi);
        }
      }
      // The stream contains C, M, Y, reserved, K slots in that order.
      for (unsigned slot = 0; slot < 5; ++slot) {
        if (slot == 3) { if (!write_all("Z", 1)) return 0; continue; }
        const unsigned char *line = lines[slot == 4 ? 3 : slot];
        int nonzero = 0;
        for (unsigned k = 0; k < profile->line_bytes; ++k)
          if (line[k]) { nonzero = 1; break; }
        if (!nonzero) {
          if (!write_all("Z", 1)) return 0;
        } else {
          unsigned char encoded[MAX_LINE_BYTES * 2];
          size_t length = encode_line(line, profile->line_bytes, encoded);
          unsigned char header[3] = {'G', (unsigned char)length,
                                     (unsigned char)(length >> 8)};
          if (!write_all(header, sizeof(header)) || !write_all(encoded, length)) return 0;
        }
      }
    }
  }
finish_page:
  if (!last && !cancelled) {
    const unsigned char page_end[] = {0x0c, 0x00};
    return write_all(page_end, profile->footer_zero ? 2 : 1);
  }
  if (profile->footer_zero)
    return write_all(end_a4, sizeof(end_a4)) && write_zeros(ZERO_PAD);
  return write_all(end_a6, sizeof(end_a6)) && write_zeros(ZERO_PAD);
}

int main(int argc, char **argv) {
  struct sigaction action = {0};
  action.sa_handler = cancel_job;
  sigemptyset(&action.sa_mask);
  if (sigaction(SIGTERM, &action, NULL) != 0) {
    perror("ERROR: Cannot install cancellation handler");
    return 1;
  }
  signal(SIGPIPE, SIG_IGN);
  const char *input_path = NULL;
  if (argc == 2) input_path = argv[1];
  else if (argc == 7) input_path = argv[6];
  else if (argc != 1 && argc != 6) {
    fprintf(stderr, "usage: %s file.ras (or CUPS filter arguments)\n", argv[0]);
    return 2;
  }
  int fd = input_path ? open(input_path, O_RDONLY) : STDIN_FILENO;
  if (fd < 0) { perror("ERROR: Cannot open raster input"); return 1; }
  raster_input_t input = {.fd = fd};
  cups_raster_t *raster = cupsRasterOpenIO(read_raster, &input, CUPS_RASTER_READ);
  if (!raster) {
    if (!cancelled) fprintf(stderr, "ERROR: Could not open CUPS raster\n");
    if (fd != STDIN_FILENO) close(fd);
    return cancelled ? 0 : 1;
  }
  cups_page_header2_t h;
  if (!cupsRasterReadHeader2(raster, &h)) {
    if (!cancelled) fprintf(stderr, "ERROR: No complete raster page header\n");
    cupsRasterClose(raster);
    if (fd != STDIN_FILENO) close(fd);
    return cancelled ? 0 : 1;
  }
  int first = 1, ok = 1, job_open = 0;
  unsigned page = 0;
  do {
    if (cancelled) break;
    const profile_t *profile = NULL;
    for (unsigned i = 0; i < sizeof(profiles) / sizeof(profiles[0]); ++i)
      if (h.HWResolution[0] == profiles[i].dpi && h.HWResolution[1] == profiles[i].dpi &&
          nearby_dimension(h.cupsWidth, profiles[i].width, profiles[i].dpi) &&
          nearby_dimension(h.cupsHeight, profiles[i].height, profiles[i].dpi))
        profile = &profiles[i];
    if (!profile || h.cupsColorSpace != CUPS_CSPACE_RGB ||
        h.cupsColorOrder != CUPS_ORDER_CHUNKED ||
        h.cupsInteger[15] > 1 || (h.cupsInteger[15] && profile->dpi < 300) ||
        h.cupsBitsPerPixel != 24 || h.cupsBitsPerColor != 8 ||
        h.cupsBytesPerLine != h.cupsWidth * 3 ||
        h.HWResolution[0] != profile->dpi || h.HWResolution[1] != profile->dpi) {
      fprintf(stderr, "ERROR: Unsupported raster %ux%u, dpi=%ux%u, colorspace=%u, bits=%u, bytes/row=%u, mode=%u; use A4/A5/A6/Letter RGB24 at 300/600 dpi\n",
              h.cupsWidth, h.cupsHeight, h.HWResolution[0], h.HWResolution[1],
              (unsigned)h.cupsColorSpace, h.cupsBitsPerPixel, h.cupsBytesPerLine, h.cupsInteger[15]);
      ok = 0;
      break;
    }
    unsigned char prologue[PROLOGUE_BYTES];
    if (!read_prologue(profile, prologue)) { ok = 0; break; }
    cups_page_header2_t render_header = h;
    render_header.cupsWidth = profile->width;
    render_header.cupsHeight = profile->height;
    render_header.cupsBytesPerLine = profile->width * 3;
    unsigned stride = (h.cupsWidth > profile->width ? h.cupsWidth : profile->width) * 3;
    unsigned rows = h.cupsHeight > profile->height ? h.cupsHeight : profile->height;
    size_t pixel_size = (size_t)stride * rows;
    unsigned char *pixels = malloc(pixel_size);
    if (!pixels) { perror("ERROR: Cannot allocate page buffer"); ok = 0; break; }
    for (unsigned y = 0; y < h.cupsHeight; ++y) {
      if (cancelled) { ok = 0; break; }
      input.row = pixels + (size_t)y * stride;
      input.row_size = h.cupsBytesPerLine;
      if (cupsRasterReadPixels(raster, input.row,
                               h.cupsBytesPerLine) != h.cupsBytesPerLine) {
        if (!cancelled) fprintf(stderr, "ERROR: Incomplete raster data on page %u, row %u\n", page + 1, y);
        ok = 0;
        break;
      }
    }
    input.row = NULL;
    if (!ok) { free(pixels); break; }
    if (h.cupsWidth != profile->width || h.cupsHeight != profile->height) {
      fprintf(stderr, "INFO: Normalizing raster geometry %ux%u to %ux%u at %u dpi\n",
              h.cupsWidth, h.cupsHeight, profile->width, profile->height, profile->dpi);
      if (!normalize_geometry(pixels, h.cupsWidth, h.cupsHeight, stride, profile)) {
        free(pixels); ok = 0; break;
      }
    }
    cups_page_header2_t next;
    uint64_t before_header = input.delivered;
    int has_next = cupsRasterReadHeader2(raster, &next);
    if (cancelled) { free(pixels); break; }
    int header_failed = !has_next &&
                        (input.failed || input.delivered != before_header);
    if (header_failed)
      fprintf(stderr, "ERROR: Incomplete or unreadable raster header after page %u\n", page + 1);
    if (h.cupsInteger[15] && profile->dpi == 600) {
      fprintf(stderr, "INFO: Preparing colour page %u\n", page + 1);
      if (!prepare_colour600(pixels, profile)) {
        free(pixels); ok = 0; break;
      }
    }
    fprintf(stderr, "INFO: Rendering page %u at %u dpi (%s)\n", ++page,
            profile->dpi, h.cupsInteger[15] ? "colour" : "monochrome");
    ok = print_page(&render_header, pixels, prologue, profile, h.cupsInteger[15], first, !has_next);
    job_open = ok && has_next && !cancelled;
    free(pixels);
    if (ok && !cancelled) fprintf(stderr, "PAGE: %u 1\n", page);
    if (header_failed) ok = 0;
    if (!ok || !has_next) break;
    h = next;
    first = 0;
  } while (1);
  if (job_open && !close_open_job()) ok = 0;
  cupsRasterClose(raster);
  if (fd != STDIN_FILENO) close(fd);
  if (cancelled) fprintf(stderr, "INFO: Native print job cancelled\n");
  return cancelled || ok ? 0 : 1;
}
