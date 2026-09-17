/* Q1/Q2/Q3 use linear interpolation at (N-1)*k/4, represented times four. */
static int compare_i16(const void *a,const void *b){
  int x=*(const int16_t *)a,y=*(const int16_t *)b;return (x>y)-(x<y);
}
static int32_t quantile_times4(const int16_t *a,uint32_t n,uint32_t k){
  uint32_t t=k*(n-1),j=t/4,r=t%4,other=j+1<n?j+1:j;
  return (int32_t)(4-r)*a[j]+(int32_t)r*a[other];
}
void enrichment(const radar_feature21_golden_point_t *p,uint32_t n,int8_t *out){
  enrichment23(p,n,out);for(int i=23;i<36;i++)out[i]=0;
#if WANT_SUPPORT
  out[23]=fraction_i8(127,n);
#endif
#if WANT_WIDTH || WANT_ASYMMETRY || WANT_MEDIAN
  int16_t a[511];
  for(int c=0;c<4;c++){
    for(uint32_t i=0;i<n;i++)a[i]=c==0?p[i].x:(c==1?p[i].y:(c==2?p[i].doppler:p[i].rcs));
    qsort(a,n,sizeof(int16_t),compare_i16);
    int32_t q1=quantile_times4(a,n,1),q2=quantile_times4(a,n,2),q3=quantile_times4(a,n,3),span=(int32_t)a[n-1]-a[0];
#if WANT_WIDTH
    out[24+c]=fraction_i8((int64_t)127*(q3-q1),(int64_t)4*span);
#endif
#if WANT_ASYMMETRY
    out[28+c]=fraction_i8((int64_t)127*(q3+q1-2*q2),q3-q1);
#endif
#if WANT_MEDIAN
    out[32+c]=fraction_i8((int64_t)127*(2*q2-4*((int32_t)a[0]+a[n-1])),(int64_t)4*span);
#endif
  }
#endif
}
