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
