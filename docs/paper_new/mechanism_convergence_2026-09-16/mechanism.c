/* One pass: shared first moments, extrema and optional spatial second moments.
 * Diagnostic family returns all four factor cells. Per-mode deploy cost differs. */
static int64_t mechanism_inv(uint32_t n,int r) {
  /* Reference integer division computes the exact rounded LUT entry for r=8/12.
   * This is not a hardware division/latency claim. Q16/Q24 use frozen LUTs. */
  if(r==24)return recip24[n];if(r==16)return recip16[n];
  return round_div_even_u64((uint64_t)1<<r,n);
}
void family(const radar_feature21_golden_point_t *p,uint32_t n,int mb,int vb,
            const int32_t *shifts,int64_t *raw,int8_t *quant) {
  int32_t origin[4]={p[0].x,p[0].y,p[0].doppler,p[0].rcs},lo[4],hi[4],rlo=0,rhi=0;
  int64_t s[4]={0},xx=0,yy=0,xy=0;
  for(uint32_t i=0;i<n;i++){
    int32_t v[4]={p[i].x,p[i].y,p[i].doppler,p[i].rcs};int64_t d[4];
    for(int j=0;j<4;j++){
      if(!i)lo[j]=hi[j]=v[j];else{if(v[j]<lo[j])lo[j]=v[j];if(v[j]>hi[j])hi[j]=v[j];}
      d[j]=(int64_t)v[j]-origin[j];s[j]+=d[j];
    }
    xx+=d[0]*d[0];yy+=d[1]*d[1];xy+=d[0]*d[1];
    int32_t r=range_v1p3_q8p8(v[0],v[1]);if(!i)rlo=rhi=r;else{if(r<rlo)rlo=r;if(r>rhi)rhi=r;}
  }
  int32_t span[4],old[4],mean[4];int64_t im=mechanism_inv(n,mb),iv=mechanism_inv(n,vb),u[2];
  for(int j=0;j<4;j++){
    span[j]=hi[j]-lo[j];old[j]=mean_shift_v1p3(s[j]+(int64_t)n*origin[j],n);
    mean[j]=clip16(origin[j]+r64(r64(s[j]*im,mb-4),4));
    if(j<2)u[j]=r64(s[j]*iv,vb-4);
  }
  int64_t vx=r64(xx*iv,vb)-r64(u[0]*u[0],8),vy=r64(yy*iv,vb)-r64(u[1]*u[1],8),cov=r64(xy*iv,vb)-r64(u[0]*u[1],8);
  if(vx<0)vx=0;if(vy<0)vy=0;
  int64_t base[21]={(int64_t)n<<8,old[0],old[1],span[0]>>2,span[1]>>2,span[0],span[1],rlo,rhi,
    range_v1p3_q8p8(old[0],old[1]),span[1],0,0,density_recip_exact_lut_quant(n,span[0],span[1]),old[2],span[2]>>2,lo[2],hi[2],old[3],span[3]>>2,hi[3]};
  base[11]=base[3]>base[4]?base[3]:base[4];base[12]=base[3]>base[4]?base[4]:base[3];
  for(int flag=0;flag<4;flag++){
    int64_t *out=raw+flag*21;for(int j=0;j<21;j++)out[j]=base[j];
    if(flag&1){out[1]=mean[0];out[2]=mean[1];out[9]=range_v1p3_q8p8(mean[0],mean[1]);out[14]=mean[2];out[18]=mean[3];}
    if(flag&2){out[3]=vx;out[4]=vy;out[10]=cov;out[11]=vx>vy?vx:vy;out[12]=vx>vy?vy:vx;}
    for(int j=0;j<21;j++){
      int shift=shifts[flag*21+j];int64_t v=shift<0?out[j]*((int64_t)1<<(-shift)):r64(out[j],shift);
      quant[flag*21+j]=v>127?127:(v<-127?-127:(int8_t)v);
    }
  }
}
