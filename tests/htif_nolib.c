#include <stdarg.h>
#include <stddef.h>
#include <stdint.h>

#define HTIF_DEV_SHIFT 56
#define HTIF_DEV_MASK  0xff
#define HTIF_CMD_SHIFT 48
#define HTIF_CMD_MASK  0xff
#define HTIF_PAYLOAD_MASK ((1ULL << HTIF_CMD_SHIFT) - 1ULL)

#define HTIF_TOHOST(dev, cmd, payload) ( \
  (((uint64_t)(dev) & HTIF_DEV_MASK) << HTIF_DEV_SHIFT) | \
  (((uint64_t)(cmd) & HTIF_CMD_MASK) << HTIF_CMD_SHIFT) | \
  ((uint64_t)(payload) & HTIF_PAYLOAD_MASK))

#define SYS_write 64UL

volatile uint64_t tohost __attribute__((section(".htif"))) = 0;
volatile uint64_t fromhost __attribute__((section(".htif"))) = 0;

void *memset(void *dst, int value, size_t len)
{
  unsigned char *out = (unsigned char *)dst;
  size_t i;

  for (i = 0; i < len; ++i) {
    out[i] = (unsigned char)value;
  }
  return dst;
}

void *memcpy(void *dst, const void *src, size_t len)
{
  unsigned char *out = (unsigned char *)dst;
  const unsigned char *in = (const unsigned char *)src;
  size_t i;

  for (i = 0; i < len; ++i) {
    out[i] = in[i];
  }
  return dst;
}

static long htif_syscall(uint64_t a0, uint64_t a1, uint64_t a2, unsigned long n)
{
  volatile uint64_t buf[8];
  uint64_t cmd;

  buf[0] = n;
  buf[1] = a0;
  buf[2] = a1;
  buf[3] = a2;

  cmd = HTIF_TOHOST(0, 0, (uintptr_t)&buf);
  asm volatile ("" ::: "memory");
  tohost = cmd;
  while (fromhost == 0) {
  }
  fromhost = 0;
  asm volatile ("" ::: "memory");
  return (long)buf[0];
}

static long htif_write_raw(const char *ptr, size_t len)
{
  return htif_syscall(1, (uintptr_t)ptr, len, SYS_write);
}

void htif_exit(int code)
{
  uint64_t cmd = HTIF_TOHOST(0, 0, ((uint64_t)code << 1) | 1ULL);
  for (;;) {
    fromhost = 0;
    tohost = cmd;
  }
}

struct printbuf {
  char data[128];
  size_t used;
  int total;
};

static void printbuf_flush(struct printbuf *pb)
{
  if (pb->used != 0) {
    htif_write_raw(pb->data, pb->used);
    pb->total += (int)pb->used;
    pb->used = 0;
  }
}

static void printbuf_putc(struct printbuf *pb, char ch)
{
  if (pb->used == sizeof(pb->data)) {
    printbuf_flush(pb);
  }
  pb->data[pb->used++] = ch;
}

static void printbuf_write(struct printbuf *pb, const char *s, size_t n)
{
  size_t i;

  for (i = 0; i < n; ++i) {
    printbuf_putc(pb, s[i]);
  }
}

static size_t cstr_len(const char *s)
{
  size_t n = 0;
  while (s[n] != '\0') {
    ++n;
  }
  return n;
}

static void print_unsigned(struct printbuf *pb, unsigned long long value, unsigned base, unsigned width, char pad)
{
  char tmp[32];
  const char *digits = "0123456789abcdef";
  unsigned i = 0;

  if (base < 2 || base > 16) {
    return;
  }

  do {
    tmp[i++] = digits[value % base];
    value /= base;
  } while (value != 0);

  while (i < width) {
    printbuf_putc(pb, pad);
    --width;
  }

  while (i > 0) {
    printbuf_putc(pb, tmp[--i]);
  }
}

static void print_signed(struct printbuf *pb, long long value)
{
  unsigned long long mag;

  if (value < 0) {
    printbuf_putc(pb, '-');
    mag = (unsigned long long)(-(value + 1)) + 1ULL;
  } else {
    mag = (unsigned long long)value;
  }
  print_unsigned(pb, mag, 10, 0, ' ');
}

int vprintf(const char *fmt, va_list ap)
{
  struct printbuf pb = { .used = 0, .total = 0 };

  while (*fmt != '\0') {
    unsigned width = 0;
    char pad = ' ';
    int long_flag = 0;

    if (*fmt != '%') {
      printbuf_putc(&pb, *fmt++);
      continue;
    }

    ++fmt;
    if (*fmt == '%') {
      printbuf_putc(&pb, *fmt++);
      continue;
    }

    if (*fmt == '0') {
      pad = '0';
      ++fmt;
    }

    while (*fmt >= '0' && *fmt <= '9') {
      width = width * 10u + (unsigned)(*fmt - '0');
      ++fmt;
    }

    while (*fmt == 'l') {
      long_flag = 1;
      ++fmt;
    }

    switch (*fmt) {
      case 'c': {
        int ch = va_arg(ap, int);
        printbuf_putc(&pb, (char)ch);
        break;
      }
      case 'd': {
        if (long_flag) {
          print_signed(&pb, va_arg(ap, long));
        } else {
          print_signed(&pb, va_arg(ap, int));
        }
        break;
      }
      case 'p': {
        uintptr_t value = (uintptr_t)va_arg(ap, void *);
        printbuf_write(&pb, "0x", 2);
        print_unsigned(&pb, value, 16, sizeof(uintptr_t) * 2u, '0');
        break;
      }
      case 's': {
        const char *s = va_arg(ap, const char *);
        if (s == NULL) {
          s = "(null)";
        }
        printbuf_write(&pb, s, cstr_len(s));
        break;
      }
      case 'u': {
        if (long_flag) {
          print_unsigned(&pb, va_arg(ap, unsigned long), 10, width, pad);
        } else {
          print_unsigned(&pb, va_arg(ap, unsigned int), 10, width, pad);
        }
        break;
      }
      case 'x': {
        if (long_flag) {
          print_unsigned(&pb, va_arg(ap, unsigned long), 16, width, pad);
        } else {
          print_unsigned(&pb, va_arg(ap, unsigned int), 16, width, pad);
        }
        break;
      }
      default:
        printbuf_putc(&pb, '%');
        if (pad == '0') {
          printbuf_putc(&pb, '0');
        }
        if (width != 0) {
          char width_buf[10];
          unsigned idx = 0;
          while (width != 0) {
            width_buf[idx++] = (char)('0' + (width % 10u));
            width /= 10u;
          }
          while (idx > 0) {
            printbuf_putc(&pb, width_buf[--idx]);
          }
        }
        if (long_flag) {
          printbuf_putc(&pb, 'l');
        }
        printbuf_putc(&pb, *fmt);
        break;
    }

    if (*fmt != '\0') {
      ++fmt;
    }
  }

  printbuf_flush(&pb);
  return pb.total;
}

int printf(const char *fmt, ...)
{
  int ret;
  va_list ap;

  va_start(ap, fmt);
  ret = vprintf(fmt, ap);
  va_end(ap);
  return ret;
}

int puts(const char *s)
{
  struct printbuf pb = { .used = 0, .total = 0 };
  printbuf_write(&pb, s, cstr_len(s));
  printbuf_putc(&pb, '\n');
  printbuf_flush(&pb);
  return pb.total;
}

void exit(int code)
{
  htif_exit(code);
}
