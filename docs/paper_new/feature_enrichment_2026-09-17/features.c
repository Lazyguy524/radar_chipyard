/* Exact rational normalized distribution descriptors; shared single point scan. */
static int8_t fraction_i8(int64_t num,int64_t den){
  if(!den)return 0;int negative=num<0;uint64_t a=negative?(uint64_t)(-num):(uint64_t)num;
  uint64_t q=a/(uint64_t)den,r=a%(uint64_t)den;
  if(r>(uint64_t)den-r || (r==(uint64_t)den-r && (q&1)))q++;
  int64_t z=negative?-(int64_t)q:(int64_t)q;return z>127?127:(z<-127?-127:(int8_t)z);
}
void enrichment(const radar_feature21_golden_point_t *p,uint32_t n,int8_t *out){
  int64_t sums[4]={0},squares[4]={0},cross=0;int32_t lo[4]={0},hi[4]={0},span[4]={0},mean[4]={0},rlo=0,rhi=0;uint32_t nearzero=0;
  for(uint32_t i=0;i<n;i++){
    int32_t v[4]={p[i].x,p[i].y,p[i].doppler,p[i].rcs};
    for(int j=0;j<4;j++){
      sums[j]+=v[j];if(!i)lo[j]=hi[j]=v[j];else{if(v[j]<lo[j])lo[j]=v[j];if(v[j]>hi[j])hi[j]=v[j];}
#if WANT_GEOMETRY
      if(j<2)squares[j]+=(int64_t)v[j]*v[j];
#endif
#if WANT_DISTRIBUTION
      if(j>=2)squares[j]+=(int64_t)v[j]*v[j];
#endif
    }
#if WANT_GEOMETRY
    cross+=(int64_t)v[0]*v[1];
#endif
#if WANT_DISTRIBUTION
    nearzero+=(v[2]>=-128 && v[2]<=128);
#endif
    int32_t r=range_v1p3_q8p8(v[0],v[1]);if(!i)rlo=rhi=r;else{if(r<rlo)rlo=r;if(r>rhi)rhi=r;}
  }
  for(int j=0;j<4;j++){span[j]=hi[j]-lo[j];mean[j]=mean_shift_v1p3(sums[j],n);}
  int64_t raw[21]={0};raw[0]=(int64_t)n<<8;raw[1]=mean[0];raw[2]=mean[1];raw[5]=span[0];raw[6]=span[1];raw[7]=rlo;raw[8]=rhi;raw[9]=range_v1p3_q8p8(mean[0],mean[1]);raw[13]=density_recip_exact_lut_quant(n,span[0],span[1]);raw[14]=mean[2];raw[15]=span[2]>>2;raw[16]=lo[2];raw[17]=hi[2];raw[18]=mean[3];raw[19]=span[3]>>2;raw[20]=hi[3];
  for(int k=0;k<16;k++){int s=base_shifts[k];int64_t z=s<0?raw[base_columns[k]]*((int64_t)1<<(-s)):r64(raw[base_columns[k]],s);out[k]=z>127?127:(z<-127?-127:(int8_t)z);}
  for(int k=16;k<23;k++)out[k]=0;
  int64_t nn=(int64_t)n*n;
#if WANT_GEOMETRY
  for(int j=0;j<2;j++)out[16+j]=fraction_i8(508*((int64_t)n*squares[j]-sums[j]*sums[j]),nn*span[j]*span[j]);
  out[18]=fraction_i8(508*((int64_t)n*cross-sums[0]*sums[1]),nn*span[0]*span[1]);
#endif
#if WANT_DISTRIBUTION
  for(int j=2;j<4;j++)out[17+j]=fraction_i8(508*((int64_t)n*squares[j]-sums[j]*sums[j]),nn*span[j]*span[j]);
  out[21]=fraction_i8((int64_t)127*nearzero,n);
  out[22]=fraction_i8(127*(2*sums[3]-(int64_t)n*(lo[3]+hi[3])),(int64_t)n*span[3]);
#endif
}
