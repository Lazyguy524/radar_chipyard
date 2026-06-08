
#define _POSIX_C_SOURCE 199309L
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

typedef struct { float x, y, d, r; } Point4;

static double now_sec(void) {
  struct timespec ts;
  clock_gettime(CLOCK_MONOTONIC, &ts);
  return (double)ts.tv_sec + (double)ts.tv_nsec * 1e-9;
}

static int8_t clamp_i8(int32_t v) {
  if (v > 127) return 127;
  if (v < -127) return -127;
  return (int8_t)v;
}

static void compute21(const Point4* p, uint32_t n, float* f) {
  float sx=0, sy=0, sd=0, sr=0, sx2=0, sy2=0, sd2=0, sr2=0;
  float minx=1e30f, maxx=-1e30f, miny=1e30f, maxy=-1e30f;
  float mind=1e30f, maxd=-1e30f, maxr=-1e30f, minrng=1e30f, maxrng=0;
  float minaz=1e30f, maxaz=-1e30f;
  if (n == 0) { memset(f, 0, 21 * sizeof(float)); return; }
  for (uint32_t i=0; i<n; ++i) {
    float x=p[i].x, y=p[i].y, d=p[i].d, r=p[i].r;
    sx += x; sy += y; sd += d; sr += r;
    sx2 += x*x; sy2 += y*y; sd2 += d*d; sr2 += r*r;
    if (x < minx) minx = x; if (x > maxx) maxx = x;
    if (y < miny) miny = y; if (y > maxy) maxy = y;
    if (d < mind) mind = d; if (d > maxd) maxd = d;
    if (r > maxr) maxr = r;
    float rng = sqrtf(x*x + y*y);
    if (rng < minrng) minrng = rng; if (rng > maxrng) maxrng = rng;
    float az = atan2f(y, x);
    if (az < minaz) minaz = az; if (az > maxaz) maxaz = az;
  }
  float inv = 1.0f / (float)n;
  float mx = sx * inv, my = sy * inv, md = sd * inv, mr = sr * inv;
  float vx = fmaxf(sx2 * inv - mx*mx, 0.0f);
  float vy = fmaxf(sy2 * inv - my*my, 0.0f);
  float vd = fmaxf(sd2 * inv - md*md, 0.0f);
  float vr = fmaxf(sr2 * inv - mr*mr, 0.0f);
  float spanx = maxx - minx, spany = maxy - miny;
  float area = spanx * spany; if (area < 1e-4f) area = 1e-4f;
  float covxx=0, covyy=0, covxy=0;
  if (n >= 2) {
    for (uint32_t i=0; i<n; ++i) {
      float dx = p[i].x - mx;
      float dy = p[i].y - my;
      covxx += dx*dx; covyy += dy*dy; covxy += dx*dy;
    }
    float denom = 1.0f / (float)(n - 1);
    covxx *= denom; covyy *= denom; covxy *= denom;
  }
  float eig_delta = sqrtf((covxx - covyy) * (covxx - covyy) + 4.0f * covxy * covxy);
  float eig_major = 0.5f * (covxx + covyy + eig_delta);
  float eig_minor = 0.5f * (covxx + covyy - eig_delta);
  f[0]=(float)n; f[1]=mx; f[2]=my; f[3]=sqrtf(vx); f[4]=sqrtf(vy);
  f[5]=spanx; f[6]=spany; f[7]=minrng; f[8]=maxrng; f[9]=sqrtf(mx*mx+my*my);
  f[10]=maxaz-minaz; f[11]=eig_major; f[12]=eig_minor; f[13]=(float)n/area;
  f[14]=md; f[15]=sqrtf(vd); f[16]=mind; f[17]=maxd; f[18]=mr; f[19]=sqrtf(vr); f[20]=maxr;
}

static void select14(const float* f21, float* f14) {
  int idx[14] = {0,1,2,3,4,5,6,9,10,11,12,13,14,15};
  for (int i=0; i<14; ++i) f14[i] = f21[idx[i]];
}

static void select18(const float* f21, float* f18) {
  for (int i=0; i<18; ++i) f18[i] = f21[i];
}

static void quantize(const float* f, int dim, float scale, int8_t* q) {
  for (int i=0; i<dim; ++i) q[i] = clamp_i8((int32_t)lrintf(f[i] / scale));
}

static size_t read_file(const char* path, void** out) {
  FILE* fp = fopen(path, "rb");
  if (!fp) { perror(path); exit(2); }
  fseek(fp, 0, SEEK_END);
  long n = ftell(fp);
  fseek(fp, 0, SEEK_SET);
  void* buf = malloc((size_t)n);
  if (!buf) { fprintf(stderr, "oom\n"); exit(2); }
  if (fread(buf, 1, (size_t)n, fp) != (size_t)n) { fprintf(stderr, "read failed\n"); exit(2); }
  fclose(fp);
  *out = buf;
  return (size_t)n;
}

int main(int argc, char** argv) {
  if (argc != 7) {
    fprintf(stderr, "usage: %s points.bin offsets_u32.bin scale14 scale18 scale21 repeat\n", argv[0]);
    return 2;
  }
  Point4* points = NULL;
  uint32_t* offsets = NULL;
  size_t point_bytes = read_file(argv[1], (void**)&points);
  size_t offset_bytes = read_file(argv[2], (void**)&offsets);
  uint32_t nsamples = (uint32_t)(offset_bytes / sizeof(uint32_t) - 1);
  float scale14 = strtof(argv[3], NULL), scale18 = strtof(argv[4], NULL), scale21 = strtof(argv[5], NULL);
  int repeat = atoi(argv[6]);
  (void)point_bytes;
  volatile int checksum = 0;
  float f21[21], f18[18], f14[14];
  int8_t q21[21], q18[18], q14[14];

  double t0 = now_sec();
  for (int r=0; r<repeat; ++r) {
    for (uint32_t s=0; s<nsamples; ++s) {
      compute21(&points[offsets[s]], offsets[s+1] - offsets[s], f21);
      select14(f21, f14);
      quantize(f14, 14, scale14, q14);
      checksum += q14[0];
    }
  }
  double t14 = now_sec() - t0;

  t0 = now_sec();
  for (int r=0; r<repeat; ++r) {
    for (uint32_t s=0; s<nsamples; ++s) {
      compute21(&points[offsets[s]], offsets[s+1] - offsets[s], f21);
      select18(f21, f18);
      quantize(f18, 18, scale18, q18);
      checksum += q18[0];
    }
  }
  double t18 = now_sec() - t0;

  t0 = now_sec();
  for (int r=0; r<repeat; ++r) {
    for (uint32_t s=0; s<nsamples; ++s) {
      compute21(&points[offsets[s]], offsets[s+1] - offsets[s], f21);
      quantize(f21, 21, scale21, q21);
      checksum += q21[0];
    }
  }
  double t21 = now_sec() - t0;

  t0 = now_sec();
  for (int r=0; r<repeat; ++r) {
    for (uint32_t s=0; s<nsamples; ++s) {
      compute21(&points[offsets[s]], offsets[s+1] - offsets[s], f21);
      checksum += (int)f21[0];
    }
  }
  double t_feature_only = now_sec() - t0;

  t0 = now_sec();
  for (int r=0; r<repeat; ++r) {
    for (uint32_t s=0; s<nsamples; ++s) {
      compute21(&points[offsets[s]], offsets[s+1] - offsets[s], f21);
      float extra = f21[7] + f21[8] + f21[16] + f21[17] + f21[18] + f21[19] + f21[20];
      checksum += (int)extra;
    }
  }
  double t_complex7 = now_sec() - t0;

  double denom = (double)nsamples * (double)repeat;
  printf("{\"samples\":%u,\"repeat\":%d,\"checksum\":%d,"
         "\"feature21_only_avg_us\":%.6f,"
         "\"feature14_quant_avg_us\":%.6f,"
         "\"feature18_quant_avg_us\":%.6f,"
         "\"feature21_quant_avg_us\":%.6f,"
         "\"complex7_proxy_avg_us\":%.6f}\n",
         nsamples, repeat, checksum,
         t_feature_only * 1e6 / denom,
         t14 * 1e6 / denom,
         t18 * 1e6 / denom,
         t21 * 1e6 / denom,
         t_complex7 * 1e6 / denom);
  free(points);
  free(offsets);
  return 0;
}
