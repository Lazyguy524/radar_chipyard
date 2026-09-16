/* Compile-time feature selection: mean-only does not execute second moments.
 * These are host C operations, not a claim about synthesized FPGA resources. */
static int64_t single_inverse(uint32_t n,int bits) {
  if(bits==24)return recip24[n];if(bits==16)return recip16[n];
  return round_div_even_u64((uint64_t)1<<bits,n);
}
static void shared_frontend(const radar_feature21_golden_point_t *p,uint32_t n,
                            int unused_mode,const int32_t *shifts,int8_t *output) {
  (void)unused_mode;
  int32_t first[4]={p[0].x,p[0].y,p[0].doppler,p[0].rcs},origin[4],lo[4],hi[4],rlo=0,rhi=0;
  int64_t sums[4]={0},xx=0,yy=0,xy=0,mean_delta[4]={0};
  for(int j=0;j<4;j++)origin[j]=((FEATURE_FLAGS&1)||((FEATURE_FLAGS&2)&&j<2))?first[j]:0;
  for(uint32_t i=0;i<n;i++){
    int32_t v[4]={p[i].x,p[i].y,p[i].doppler,p[i].rcs};int64_t d[4];
    for(int j=0;j<4;j++){
      if(!i)lo[j]=hi[j]=v[j];else{if(v[j]<lo[j])lo[j]=v[j];if(v[j]>hi[j])hi[j]=v[j];}
      d[j]=(int64_t)v[j]-origin[j];sums[j]+=d[j];
    }
    if(FEATURE_FLAGS&2){xx+=d[0]*d[0];yy+=d[1]*d[1];xy+=d[0]*d[1];}
    int32_t r=range_v1p3_q8p8(v[0],v[1]);if(!i)rlo=rhi=r;else{if(r<rlo)rlo=r;if(r>rhi)rhi=r;}
  }
  int32_t mean[4],span[4];int64_t im=0,iv=0;
  if(FEATURE_FLAGS&1)im=single_inverse(n,MEAN_RECIP_BITS);
  if(FEATURE_FLAGS&2)iv=((FEATURE_FLAGS&1)&&MEAN_RECIP_BITS==SPATIAL_RECIP_BITS)?im:single_inverse(n,SPATIAL_RECIP_BITS);
  for(int j=0;j<4;j++){
    span[j]=hi[j]-lo[j];
    if(FEATURE_FLAGS&1){mean_delta[j]=r64(sums[j]*im,MEAN_RECIP_BITS-4);mean[j]=clip16(origin[j]+r64(mean_delta[j],4));}
    else mean[j]=mean_shift_v1p3(sums[j]+(int64_t)n*origin[j],n);
  }
  int64_t vx=span[0]>>2,vy=span[1]>>2,cov=span[1];
  if(FEATURE_FLAGS&2){
    int64_t ux=((FEATURE_FLAGS&1)&&MEAN_RECIP_BITS==SPATIAL_RECIP_BITS)?mean_delta[0]:r64(sums[0]*iv,SPATIAL_RECIP_BITS-4);
    int64_t uy=((FEATURE_FLAGS&1)&&MEAN_RECIP_BITS==SPATIAL_RECIP_BITS)?mean_delta[1]:r64(sums[1]*iv,SPATIAL_RECIP_BITS-4);
    vx=r64(xx*iv,SPATIAL_RECIP_BITS)-r64(ux*ux,8);vy=r64(yy*iv,SPATIAL_RECIP_BITS)-r64(uy*uy,8);
    cov=r64(xy*iv,SPATIAL_RECIP_BITS)-r64(ux*uy,8);if(vx<0)vx=0;if(vy<0)vy=0;
  }
  int64_t out[21]={(int64_t)n<<8,mean[0],mean[1],vx,vy,span[0],span[1],rlo,rhi,
    range_v1p3_q8p8(mean[0],mean[1]),cov,vx>vy?vx:vy,vx>vy?vy:vx,
    density_recip_exact_lut_quant(n,span[0],span[1]),mean[2],span[2]>>2,lo[2],hi[2],mean[3],span[3]>>2,hi[3]};
  for(int j=0;j<21;j++){
    int shift=shifts[j];int64_t z=shift<0?out[j]*((int64_t)1<<(-shift)):r64(out[j],shift);
    output[j]=z>127?127:(z<-127?-127:(int8_t)z);
  }
}
