/* Input: one K7-fused cluster, 1..511 points, four signed Q8.8 values per
 * point (x,y,compensated radial velocity,RCS), little endian, no header.
 * GT tracking and K7 fusion are upstream and are not implemented here. */
#include <stdio.h>

void candidate_infer(const radar_feature21_golden_point_t *p, uint32_t n,
                     int8_t *features, int8_t *h1, int8_t *h2, int32_t *logits) {
  shared_frontend(p,n,CANDIDATE_MODE,candidate_shifts,features);
  qmlp_infer(features,logits,h1,h2);
}

int main(int argc,char **argv) {
  if(argc!=2){fprintf(stderr,"usage: %s cluster.int16le\n",argv[0]);return 2;}
  FILE *f=fopen(argv[1],"rb");if(!f){perror("open cluster");return 2;}
  unsigned char bytes[511*8+1];size_t size=fread(bytes,1,sizeof(bytes),f);
  int bad=ferror(f);fclose(f);
  if(bad||!size||size%8||size>511*8){fprintf(stderr,"expected 1..511 points, 8 bytes per point\n");return 2;}
  radar_feature21_golden_point_t points[511];
  for(size_t i=0;i<size/8;i++){
    int16_t values[4];
    for(int j=0;j<4;j++){
      const unsigned char *b=bytes+8*i+2*j;
      int32_t u=(int32_t)b[0]+((int32_t)b[1]<<8);values[j]=(int16_t)(u>=32768?u-65536:u);
    }
    points[i]=(radar_feature21_golden_point_t){values[0],values[1],values[2],values[3]};
  }
  int8_t features[21],h1[64],h2[32];int32_t logits[2];
  candidate_infer(points,size/8,features,h1,h2,logits);
  printf("{\"points\":%zu,\"features\":[",size/8);
  for(int i=0;i<21;i++)printf("%s%d",i?",":"",(int)features[i]);
  printf("],\"logits\":[%d,%d],\"predicted_class\":%d}\n",logits[0],logits[1],logits[1]>logits[0]);
  return 0;
}
