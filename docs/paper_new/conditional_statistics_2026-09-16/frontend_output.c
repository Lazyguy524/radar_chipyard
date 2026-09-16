/* Integer-only output quantizer; appended after the frozen feature kernel. */
void frontend(const radar_feature21_golden_point_t *p,uint32_t n,int mode,const int32_t *shifts,int8_t *out) {
  int64_t values[84];int8_t old[21];int32_t neg[3];extract_all(p,n,values,old,neg);
  for(int j=0;j<21;j++) {
    int64_t v=values[mode*21+j];int s=shifts[j];
    v=s<0?v*((int64_t)1<<(-s)):r64(v,(unsigned)s);
    out[j]=v>127?127:(v<-127?-127:(int8_t)v);
  }
}
