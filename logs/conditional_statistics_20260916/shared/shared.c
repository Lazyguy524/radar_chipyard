#include <stdint.h>
#define CPU_FULLCHAIN_FEATURE_DIM 21
#define CPU_FULLCHAIN_MAX_POINTS 511u
typedef struct {int16_t x,y,doppler,rcs;} radar_feature21_golden_point_t;
static int32_t round_shift_even_i64(int64_t value, unsigned int shift)
{
  uint64_t abs_value;
  uint64_t q_abs;
  uint64_t rem;
  uint64_t half;
  uint64_t rounded_abs;

  if (shift == 0u) {
    return (int32_t)value;
  }

  abs_value = (value < 0) ? (uint64_t)(-value) : (uint64_t)value;
  q_abs = abs_value >> shift;
  rem = abs_value & (((uint64_t)1u << shift) - 1u);
  half = (uint64_t)1u << (shift - 1u);
  rounded_abs = q_abs + ((rem > half) || ((rem == half) && (q_abs & 1u)));

  return (value < 0) ? -(int32_t)rounded_abs : (int32_t)rounded_abs;
}

static uint64_t round_div_even_u64(uint64_t numer, uint64_t denom)
{
  uint64_t q = numer / denom;
  uint64_t rem = numer - q * denom;
  uint64_t twice_rem = rem << 1;
  return q + ((twice_rem > denom) || ((twice_rem == denom) && (q & 1u)));
}

static int8_t clamp_s8_symmetric(int32_t value)
{
  if (value > 127) return 127;
  if (value < -127) return -127;
  return (int8_t)value;
}

static int8_t quant_q8p8(int32_t value)
{
  return clamp_s8_symmetric(round_shift_even_i64((int64_t)value * 105ll, 16u));
}

static int8_t quant_raw_count(uint32_t count)
{
  return quant_q8p8((int32_t)(count << 8));
}

static int32_t abs16_i32(int32_t value)
{
  int32_t abs_value = (value < 0) ? -value : value;
  return abs_value & 0xffff;
}

static int32_t range_v1p3_q8p8(int32_t x, int32_t y)
{
  int32_t ax = abs16_i32(x);
  int32_t ay = abs16_i32(y);
  int32_t hi = ax > ay ? ax : ay;
  int32_t lo = ax > ay ? ay : ax;
  return hi + (lo >> 1);
}

static int32_t mean_shift_v1p3(int64_t sum, uint32_t count)
{
  unsigned int shift;
  if (count <= 1u) shift = 0u;
  else if (count == 2u) shift = 1u;
  else if (count <= 4u) shift = 2u;
  else if (count <= 8u) shift = 3u;
  else if (count <= 16u) shift = 4u;
  else if (count <= 32u) shift = 5u;
  else if (count <= 64u) shift = 6u;
  else if (count <= 128u) shift = 7u;
  else if (count <= 256u) shift = 8u;
  else shift = 9u;
  return (int32_t)(sum >> shift);
}

static unsigned int bit_length_u64(uint64_t value)
{
  unsigned int bits = 0u;
  while (value != 0u) {
    bits++;
    value >>= 1;
  }
  return bits;
}

static int8_t density_recip_exact_lut_quant(uint32_t count, int32_t span_x, int32_t span_y)
{
  uint64_t sx = span_x > 0 ? (uint64_t)span_x : 0u;
  uint64_t sy = span_y > 0 ? (uint64_t)span_y : 0u;
  uint64_t area_q16p16 = sx * sy;
  unsigned int exponent;
  uint64_t mant8;
  uint64_t recip_q0p23;
  uint64_t prod;
  uint64_t density_q8p8;
  int64_t density_i64;

  if (count == 0u) {
    return 0;
  }
  if (area_q16p16 == 0u) {
    return 127;
  }

  exponent = bit_length_u64(area_q16p16) - 1u;
  if (exponent >= 7u) {
    mant8 = area_q16p16 >> (exponent - 7u);
  } else {
    mant8 = area_q16p16 << (7u - exponent);
  }
  if (mant8 < 128u) mant8 = 128u;
  if (mant8 > 255u) mant8 = 255u;

  recip_q0p23 = round_div_even_u64((uint64_t)1u << 23, mant8);
  prod = (uint64_t)count * recip_q0p23;
  if (exponent >= 8u) {
    density_q8p8 = (uint64_t)round_shift_even_i64((int64_t)prod, exponent - 8u);
  } else {
    density_q8p8 = prod << (8u - exponent);
  }

  density_i64 = (int64_t)density_q8p8;
  if (density_i64 > 0x7fffffffll) {
    density_i64 = 0x7fffffffll;
  }
  {
    int8_t quant = quant_q8p8((int32_t)density_i64);
    return quant < 0 ? 0 : quant;
  }
}

static void feature21_density_exact_lut(const radar_feature21_golden_point_t *points, uint32_t raw_count, int8_t out[CPU_FULLCHAIN_FEATURE_DIM])
{
  uint32_t count = raw_count > CPU_FULLCHAIN_MAX_POINTS ? CPU_FULLCHAIN_MAX_POINTS : raw_count;
  int64_t sum_x = 0, sum_y = 0, sum_d = 0, sum_r = 0;
  int32_t min_x = 0, max_x = 0, min_y = 0, max_y = 0;
  int32_t min_d = 0, max_d = 0, min_r = 0, max_r = 0;
  int32_t min_range = 0, max_range = 0;
  uint32_t i;

  for (i = 0u; i < count; ++i) {
    const radar_feature21_golden_point_t *pt = &points[i];
    int32_t x = pt->x;
    int32_t y = pt->y;
    int32_t d = pt->doppler;
    int32_t r = pt->rcs;
    int32_t range = range_v1p3_q8p8(x, y);
    int first = (i == 0u);

    sum_x += x;
    sum_y += y;
    sum_d += d;
    sum_r += r;

    if (first || x < min_x) min_x = x;
    if (first || x > max_x) max_x = x;
    if (first || y < min_y) min_y = y;
    if (first || y > max_y) max_y = y;
    if (first || d < min_d) min_d = d;
    if (first || d > max_d) max_d = d;
    if (first || r < min_r) min_r = r;
    if (first || r > max_r) max_r = r;
    if (first || range < min_range) min_range = range;
    if (first || range > max_range) max_range = range;
  }

  {
    int32_t mean_x = mean_shift_v1p3(sum_x, count);
    int32_t mean_y = mean_shift_v1p3(sum_y, count);
    int32_t mean_d = mean_shift_v1p3(sum_d, count);
    int32_t mean_r = mean_shift_v1p3(sum_r, count);
    int32_t span_x = max_x - min_x;
    int32_t span_y = max_y - min_y;
    int32_t span_d = max_d - min_d;
    int32_t span_r = max_r - min_r;
    int32_t std_x = span_x >> 2;
    int32_t std_y = span_y >> 2;
    int32_t eig_major = std_x > std_y ? std_x : std_y;
    int32_t eig_minor = std_x > std_y ? std_y : std_x;

    out[0] = quant_raw_count(count);
    out[1] = quant_q8p8(mean_x);
    out[2] = quant_q8p8(mean_y);
    out[3] = quant_q8p8(std_x);
    out[4] = quant_q8p8(std_y);
    out[5] = quant_q8p8(span_x);
    out[6] = quant_q8p8(span_y);
    out[7] = quant_q8p8(min_range);
    out[8] = quant_q8p8(max_range);
    out[9] = quant_q8p8(range_v1p3_q8p8(mean_x, mean_y));
    out[10] = quant_q8p8(span_y);
    out[11] = quant_q8p8(eig_major);
    out[12] = quant_q8p8(eig_minor);
    out[13] = density_recip_exact_lut_quant(count, span_x, span_y);
    out[14] = quant_q8p8(mean_d);
    out[15] = quant_q8p8(span_d >> 2);
    out[16] = quant_q8p8(min_d);
    out[17] = quant_q8p8(max_d);
    out[18] = quant_q8p8(mean_r);
    out[19] = quant_q8p8(span_r >> 2);
    out[20] = quant_q8p8(max_r);
  }
}

static void proxy_raw(const radar_feature21_golden_point_t *points, uint32_t raw_count, int32_t out[CPU_FULLCHAIN_FEATURE_DIM])
{
  uint32_t count = raw_count > CPU_FULLCHAIN_MAX_POINTS ? CPU_FULLCHAIN_MAX_POINTS : raw_count;
  int64_t sum_x = 0, sum_y = 0, sum_d = 0, sum_r = 0;
  int32_t min_x = 0, max_x = 0, min_y = 0, max_y = 0;
  int32_t min_d = 0, max_d = 0, min_r = 0, max_r = 0;
  int32_t min_range = 0, max_range = 0;
  uint32_t i;

  for (i = 0u; i < count; ++i) {
    const radar_feature21_golden_point_t *pt = &points[i];
    int32_t x = pt->x;
    int32_t y = pt->y;
    int32_t d = pt->doppler;
    int32_t r = pt->rcs;
    int32_t range = range_v1p3_q8p8(x, y);
    int first = (i == 0u);

    sum_x += x;
    sum_y += y;
    sum_d += d;
    sum_r += r;

    if (first || x < min_x) min_x = x;
    if (first || x > max_x) max_x = x;
    if (first || y < min_y) min_y = y;
    if (first || y > max_y) max_y = y;
    if (first || d < min_d) min_d = d;
    if (first || d > max_d) max_d = d;
    if (first || r < min_r) min_r = r;
    if (first || r > max_r) max_r = r;
    if (first || range < min_range) min_range = range;
    if (first || range > max_range) max_range = range;
  }

  {
    int32_t mean_x = mean_shift_v1p3(sum_x, count);
    int32_t mean_y = mean_shift_v1p3(sum_y, count);
    int32_t mean_d = mean_shift_v1p3(sum_d, count);
    int32_t mean_r = mean_shift_v1p3(sum_r, count);
    int32_t span_x = max_x - min_x;
    int32_t span_y = max_y - min_y;
    int32_t span_d = max_d - min_d;
    int32_t span_r = max_r - min_r;
    int32_t std_x = span_x >> 2;
    int32_t std_y = span_y >> 2;
    int32_t eig_major = std_x > std_y ? std_x : std_y;
    int32_t eig_minor = std_x > std_y ? std_y : std_x;

    out[0] = (int32_t)(count << 8);
    out[1] = (mean_x);
    out[2] = (mean_y);
    out[3] = (std_x);
    out[4] = (std_y);
    out[5] = (span_x);
    out[6] = (span_y);
    out[7] = (min_range);
    out[8] = (max_range);
    out[9] = (range_v1p3_q8p8(mean_x, mean_y));
    out[10] = (span_y);
    out[11] = (eig_major);
    out[12] = (eig_minor);
    out[13] = density_recip_exact_lut_quant(count, span_x, span_y);
    out[14] = (mean_d);
    out[15] = (span_d >> 2);
    out[16] = (min_d);
    out[17] = (max_d);
    out[18] = (mean_r);
    out[19] = (span_r >> 2);
    out[20] = (max_r);
  }
}

static const uint32_t recip16[512] = {0,65536,32768,21845,16384,13107,10923,9362,8192,7282,6554,5958,5461,5041,4681,4369,4096,3855,3641,3449,3277,3121,2979,2849,2731,2621,2521,2427,2341,2260,2185,2114,2048,1986,1928,1872,1820,1771,1725,1680,1638,1598,1560,1524,1489,1456,1425,1394,1365,1337,1311,1285,1260,1237,1214,1192,1170,1150,1130,1111,1092,1074,1057,1040,1024,1008,993,978,964,950,936,923,910,898,886,874,862,851,840,830,819,809,799,790,780,771,762,753,745,736,728,720,712,705,697,690,683,676,669,662,655,649,643,636,630,624,618,612,607,601,596,590,585,580,575,570,565,560,555,551,546,542,537,533,529,524,520,516,512,508,504,500,496,493,489,485,482,478,475,471,468,465,462,458,455,452,449,446,443,440,437,434,431,428,426,423,420,417,415,412,410,407,405,402,400,397,395,392,390,388,386,383,381,379,377,374,372,370,368,366,364,362,360,358,356,354,352,350,349,347,345,343,341,340,338,336,334,333,331,329,328,326,324,323,321,320,318,317,315,314,312,311,309,308,306,305,303,302,301,299,298,297,295,294,293,291,290,289,287,286,285,284,282,281,280,279,278,277,275,274,273,272,271,270,269,267,266,265,264,263,262,261,260,259,258,257,256,255,254,253,252,251,250,249,248,247,246,245,245,244,243,242,241,240,239,238,237,237,236,235,234,233,232,232,231,230,229,228,228,227,226,225,224,224,223,222,221,221,220,219,218,218,217,216,216,215,214,213,213,212,211,211,210,209,209,208,207,207,206,205,205,204,204,203,202,202,201,200,200,199,199,198,197,197,196,196,195,194,194,193,193,192,192,191,191,190,189,189,188,188,187,187,186,186,185,185,184,184,183,183,182,182,181,181,180,180,179,179,178,178,177,177,176,176,175,175,174,174,173,173,172,172,172,171,171,170,170,169,169,168,168,168,167,167,166,166,165,165,165,164,164,163,163,163,162,162,161,161,161,160,160,159,159,159,158,158,158,157,157,156,156,156,155,155,155,154,154,153,153,153,152,152,152,151,151,151,150,150,150,149,149,149,148,148,148,147,147,147,146,146,146,145,145,145,144,144,144,143,143,143,142,142,142,142,141,141,141,140,140,140,139,139,139,139,138,138,138,137,137,137,137,136,136,136,135,135,135,135,134,134,134,133,133,133,133,132,132,132,132,131,131,131,131,130,130,130,130,129,129,129,129,128};
static const uint32_t recip24[512] = {0,16777216,8388608,5592405,4194304,3355443,2796203,2396745,2097152,1864135,1677722,1525201,1398101,1290555,1198373,1118481,1048576,986895,932068,883011,838861,798915,762601,729444,699051,671089,645278,621378,599186,578525,559241,541201,524288,508400,493448,479349,466034,453438,441506,430185,419430,409200,399458,390168,381300,372827,364722,356962,349525,342392,335544,328965,322639,316551,310689,305040,299593,294337,289262,284360,279620,275036,270600,266305,262144,258111,254200,250406,246724,243148,239675,236299,233017,229825,226719,223696,220753,217886,215093,212370,209715,207126,204600,202135,199729,197379,195084,192842,190650,188508,186414,184365,182361,180400,178481,176602,174763,172961,171196,169467,167772,166111,164483,162886,161319,159783,158276,156796,155345,153919,152520,151146,149797,148471,147169,145889,144631,143395,142180,140985,139810,138655,137518,136400,135300,134218,133153,132104,131072,130056,129056,128070,127100,126144,125203,124276,123362,122461,121574,120699,119837,118987,118149,117323,116508,115705,114912,114131,113360,112599,111848,111107,110376,109655,108943,108240,107546,106861,106185,105517,104858,104206,103563,102928,102300,101680,101068,100462,99864,99273,98690,98112,97542,96978,96421,95870,95325,94787,94254,93727,93207,92692,92183,91679,91181,90688,90200,89718,89241,88768,88301,87839,87381,86929,86480,86037,85598,85164,84733,84308,83886,83469,83056,82646,82241,81840,81443,81049,80660,80274,79892,79513,79138,78766,78398,78034,77672,77314,76960,76608,76260,75915,75573,75234,74898,74565,74235,73908,73584,73263,72944,72629,72316,72005,71698,71392,71090,70790,70493,70198,69905,69615,69327,69042,68759,68478,68200,67924,67650,67378,67109,66841,66576,66313,66052,65793,65536,65281,65028,64777,64528,64281,64035,63792,63550,63310,63072,62836,62602,62369,62138,61909,61681,61455,61231,61008,60787,60568,60350,60133,59919,59705,59494,59283,59075,58867,58662,58457,58254,58053,57852,57654,57456,57260,57065,56872,56680,56489,56299,56111,55924,55738,55554,55370,55188,55007,54828,54649,54471,54295,54120,53946,53773,53601,53431,53261,53092,52925,52759,52593,52429,52265,52103,51942,51782,51622,51464,51306,51150,50995,50840,50686,50534,50382,50231,50081,49932,49784,49637,49490,49345,49200,49056,48913,48771,48630,48489,48349,48210,48072,47935,47798,47663,47528,47393,47260,47127,46995,46864,46733,46603,46474,46346,46218,46091,45965,45839,45714,45590,45467,45344,45222,45100,44979,44859,44739,44620,44502,44384,44267,44151,44035,43919,43805,43691,43577,43464,43352,43240,43129,43019,42908,42799,42690,42582,42474,42367,42260,42154,42048,41943,41838,41734,41631,41528,41425,41323,41222,41121,41020,40920,40820,40721,40623,40525,40427,40330,40233,40137,40041,39946,39851,39756,39662,39569,39476,39383,39291,39199,39108,39017,38926,38836,38746,38657,38568,38480,38392,38304,38217,38130,38044,37958,37872,37787,37702,37617,37533,37449,37366,37283,37200,37118,37036,36954,36873,36792,36712,36631,36552,36472,36393,36314,36236,36158,36080,36003,35926,35849,35772,35696,35620,35545,35470,35395,35320,35246,35172,35099,35026,34953,34880,34808,34735,34664,34592,34521,34450,34380,34309,34239,34169,34100,34031,33962,33893,33825,33757,33689,33622,33554,33487,33421,33354,33288,33222,33157,33091,33026,32961,32897,32832};
/* Appended to the unchanged legacy feature functions and reciprocal tables. */
static int64_t r64(int64_t a, unsigned s) {
  if (!s) return a;
  uint64_t v=a<0?(uint64_t)(-a):(uint64_t)a;
  uint64_t q=v>>s, rem=v&(((uint64_t)1<<s)-1),half=(uint64_t)1<<(s-1);
  q+=(rem>half)||((rem==half)&&(q&1));
  return a<0?-(int64_t)q:(int64_t)q;
}
static int32_t clip16(int64_t x) {return x<-32768?-32768:(x>32767?32767:(int32_t)x);}
static int32_t moments(const radar_feature21_golden_point_t *p,uint32_t n,int r,int centered,int64_t *out) {
  int64_t origin[4]={0,0,0,0},s[4]={0,0,0,0},xx=0,yy=0,xy=0,mu[4];
  if(centered){origin[0]=p[0].x;origin[1]=p[0].y;origin[2]=p[0].doppler;origin[3]=p[0].rcs;}
  for(uint32_t i=0;i<n;i++){
    int64_t d[4]={p[i].x-origin[0],p[i].y-origin[1],p[i].doppler-origin[2],p[i].rcs-origin[3]};
    for(int j=0;j<4;j++)s[j]+=d[j];
    xx+=d[0]*d[0];yy+=d[1]*d[1];xy+=d[0]*d[1];
  }
  int64_t inv=r==24?recip24[n]:recip16[n];
  for(int j=0;j<4;j++)mu[j]=r64(s[j]*inv,r-4);
  int32_t mx=clip16(origin[0]+r64(mu[0],4)),my=clip16(origin[1]+r64(mu[1],4));
  out[1]=mx;out[2]=my;out[14]=clip16(origin[2]+r64(mu[2],4));out[18]=clip16(origin[3]+r64(mu[3],4));
  out[9]=range_v1p3_q8p8(mx,my);
  int64_t vx=r64(xx*inv,r)-r64(mu[0]*mu[0],8);
  int64_t vy=r64(yy*inv,r)-r64(mu[1]*mu[1],8);
  int64_t cov=r64(xy*inv,r)-r64(mu[0]*mu[1],8);
  int negatives=(vx<0)+(vy<0);if(vx<0)vx=0;if(vy<0)vy=0;
  out[3]=vx;out[4]=vy;out[10]=cov;
  out[11]=vx>vy?vx:vy;out[12]=vx>vy?vy:vx;
  return negatives;
}
void extract_all(const radar_feature21_golden_point_t *p,uint32_t n,int64_t *out,int8_t *legacy,int32_t *neg) {
  int32_t raw[21];proxy_raw(p,n,raw);feature21_density_exact_lut(p,n,legacy);
  for(int m=0;m<4;m++)for(int j=0;j<21;j++)out[m*21+j]=raw[j];
  neg[0]=moments(p,n,24,1,out+21);neg[1]=moments(p,n,16,1,out+42);neg[2]=moments(p,n,16,0,out+63);
}
/* Actual single-pass candidate; one shared set of first moments and extrema.
 * mode=0: old proxy statistics; mode=16/24: centered second moments.
 * Integer values and output slot units match the frozen diagnostic kernel. */
typedef struct {
  uint32_t n;
  int32_t origin[4],lo[4],hi[4],range_lo,range_hi;
  int64_t sum[4],xx,yy,xy;
} shared_state;

static void shared_update(shared_state *s,const radar_feature21_golden_point_t *p,int mode) {
  int32_t v[4]={p->x,p->y,p->doppler,p->rcs};
  int32_t range=range_v1p3_q8p8(v[0],v[1]);
  if(!s->n){
    for(int j=0;j<4;j++){s->origin[j]=mode?v[j]:0;s->lo[j]=v[j];s->hi[j]=v[j];}
    s->range_lo=range;s->range_hi=range;
  }
  int64_t d[4];
  for(int j=0;j<4;j++){
    d[j]=(int64_t)v[j]-s->origin[j];s->sum[j]+=d[j];
    if(v[j]<s->lo[j])s->lo[j]=v[j];if(v[j]>s->hi[j])s->hi[j]=v[j];
  }
  if(range<s->range_lo)s->range_lo=range;if(range>s->range_hi)s->range_hi=range;
  if(mode){s->xx+=d[0]*d[0];s->yy+=d[1]*d[1];s->xy+=d[0]*d[1];}
  s->n++;
}

static void shared_finish(const shared_state *s,int mode,int64_t *out) {
  int32_t mean[4],span[4];int64_t mu[4]={0,0,0,0};
  int64_t inv=mode==24?recip24[s->n]:recip16[s->n];
  for(int j=0;j<4;j++){
    span[j]=s->hi[j]-s->lo[j];
    if(mode){mu[j]=r64(s->sum[j]*inv,mode-4);mean[j]=clip16(s->origin[j]+r64(mu[j],4));}
    else mean[j]=mean_shift_v1p3(s->sum[j],s->n);
  }
  int64_t vx=span[0]>>2,vy=span[1]>>2,cov=span[1];
  if(mode){
    vx=r64(s->xx*inv,mode)-r64(mu[0]*mu[0],8);if(vx<0)vx=0;
    vy=r64(s->yy*inv,mode)-r64(mu[1]*mu[1],8);if(vy<0)vy=0;
    cov=r64(s->xy*inv,mode)-r64(mu[0]*mu[1],8);
  }
  out[0]=(int64_t)s->n<<8;out[1]=mean[0];out[2]=mean[1];out[3]=vx;out[4]=vy;
  out[5]=span[0];out[6]=span[1];out[7]=s->range_lo;out[8]=s->range_hi;
  out[9]=range_v1p3_q8p8(mean[0],mean[1]);out[10]=cov;
  out[11]=vx>vy?vx:vy;out[12]=vx>vy?vy:vx;
  out[13]=density_recip_exact_lut_quant(s->n,span[0],span[1]);
  out[14]=mean[2];out[15]=span[2]>>2;out[16]=s->lo[2];out[17]=s->hi[2];
  out[18]=mean[3];out[19]=span[3]>>2;out[20]=s->hi[3];
}

void shared_extract(const radar_feature21_golden_point_t *p,uint32_t n,int mode,int64_t *out) {
  shared_state s={0};for(uint32_t i=0;i<n;i++)shared_update(&s,p+i,mode);shared_finish(&s,mode,out);
}

void shared_frontend(const radar_feature21_golden_point_t *p,uint32_t n,int mode,const int32_t *shifts,int8_t *out) {
  int64_t values[21];shared_extract(p,n,mode,values);
  for(int j=0;j<21;j++){
    int64_t v=values[j];int shift=shifts[j];v=shift<0?v*((int64_t)1<<(-shift)):r64(v,(unsigned)shift);
    out[j]=v>127?127:(v<-127?-127:(int8_t)v);
  }
}
