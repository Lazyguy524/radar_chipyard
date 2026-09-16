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
