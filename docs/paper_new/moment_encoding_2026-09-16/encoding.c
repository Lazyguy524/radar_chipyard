static int64_t encoding_root(int64_t value) {
  uint64_t a=value<0?(uint64_t)(-value):(uint64_t)value,rem=a,root=0,bit=(uint64_t)1<<62;
  while(bit>rem)bit>>=2;
  while(bit){if(rem>=root+bit){rem-=root+bit;root=(root>>1)+bit;}else root>>=1;bit>>=2;}
  if(a-root*root>root)root++;
  return value<0?-(int64_t)root:(int64_t)root;
}
static void encoding_root_row(const int64_t *in,int64_t *out) {
  for(int j=0;j<21;j++)out[j]=in[j];
  int64_t x=encoding_root(in[3]),y=encoding_root(in[4]);
  out[3]=x;out[4]=y;out[10]=encoding_root(in[10]);out[11]=x>y?x:y;out[12]=x>y?y:x;
}
void encode_raw_rows(const int64_t *in,uint32_t n,int64_t *out) {
  for(uint32_t i=0;i<n;i++)encoding_root_row(in+i*21,out+i*21);
}
void encoding_features(const radar_feature21_golden_point_t *p,uint32_t n,int mb,int vb,const int32_t *shift,int8_t *out) {
  int32_t zero[84]={0};int64_t raw[84],root[21];int8_t scratch[84];
  family(p,n,mb,vb,zero,raw,scratch);encoding_root_row(raw+63,root);
  for(int mode=0;mode<2;mode++)for(int j=0;j<21;j++){
    int64_t value=mode?root[j]:raw[63+j];int s=shift[mode*21+j];value=s<0?value*((int64_t)1<<(-s)):r64(value,s);
    out[mode*21+j]=value>127?127:(value<-127?-127:(int8_t)value);
  }
}
