/* Single scan of required channels. Reference computation, no FPGA claim. */
static void subset_frontend(const radar_feature21_golden_point_t *p,uint32_t n,int8_t *output){
  int64_t sums[4]={0};int32_t lo[4]={0},hi[4]={0},span[4]={0},mean[4]={0},rlo=0,rhi=0;
  for(uint32_t i=0;i<n;i++){
    int32_t v[4]={p[i].x,p[i].y,p[i].doppler,0};
#if HAS_RCS
    v[3]=p[i].rcs;
#endif
    for(int j=0;j<ACTIVE_CHANNELS;j++){
      sums[j]+=v[j];if(!i)lo[j]=hi[j]=v[j];else{if(v[j]<lo[j])lo[j]=v[j];if(v[j]>hi[j])hi[j]=v[j];}
    }
    int32_t r=range_v1p3_q8p8(v[0],v[1]);if(!i)rlo=rhi=r;else{if(r<rlo)rlo=r;if(r>rhi)rhi=r;}
  }
  for(int j=0;j<ACTIVE_CHANNELS;j++){span[j]=hi[j]-lo[j];mean[j]=mean_shift_v1p3(sums[j],n);}
  int64_t raw[21]={0};raw[0]=(int64_t)n<<8;raw[1]=mean[0];raw[2]=mean[1];raw[5]=span[0];raw[6]=span[1];
  raw[7]=rlo;raw[8]=rhi;raw[9]=range_v1p3_q8p8(mean[0],mean[1]);
#if HAS_SHAPE_PROXY
  raw[3]=span[0]>>2;raw[4]=span[1]>>2;raw[11]=raw[3]>raw[4]?raw[3]:raw[4];raw[12]=raw[3]>raw[4]?raw[4]:raw[3];
#endif
#if HAS_DUPLICATE
  raw[10]=span[1];
#endif
  raw[13]=density_recip_exact_lut_quant(n,span[0],span[1]);raw[14]=mean[2];raw[15]=span[2]>>2;raw[16]=lo[2];raw[17]=hi[2];
#if HAS_RCS
  raw[18]=mean[3];raw[19]=span[3]>>2;raw[20]=hi[3];
#endif
  for(int k=0;k<RADAR_MLP_INPUT_DIM;k++){int j=selected_columns[k],shift=selected_shifts[k];int64_t z=shift<0?raw[j]*((int64_t)1<<(-shift)):r64(raw[j],shift);output[k]=z>127?127:(z<-127?-127:(int8_t)z);}
}
