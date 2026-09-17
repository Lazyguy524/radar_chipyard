#include "VCandidateTop.h"
#include "verilated.h"
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

template<class T> std::vector<T> load(const std::string &p) {
  std::ifstream f(p, std::ios::binary | std::ios::ate);
  if (!f) throw std::runtime_error("open " + p);
  auto n=f.tellg();
  if (n < 0 || size_t(n)%sizeof(T)) throw std::runtime_error("size " + p);
  std::vector<T> x(size_t(n)/sizeof(T)); f.seekg(0);
  f.read(reinterpret_cast<char*>(x.data()),n);
  if (!f) throw std::runtime_error("read " + p);
  return x;
}
void require(bool b,const std::string &m) { if (!b) throw std::runtime_error(m); }
void tick(VCandidateTop &d) { d.clock=0;d.eval();d.clock=1;d.eval(); }
void reset(VCandidateTop &d) {
  d.io_in_valid=0;d.io_out_ready=1;d.io_abort=0;d.reset=1;
  for(int i=0;i<5;i++)tick(d);
  d.reset=0;tick(d);
}
void send(VCandidateTop &d,uint64_t data,bool last) {
  d.io_in_valid=1;d.io_in_bits_data=data;d.io_in_bits_keep=255;d.io_in_bits_last=last;
  for(int i=0;i<2000;i++) {
    d.clock=0;d.eval();bool ready=d.io_in_ready;d.clock=1;d.eval();
    if(ready){d.io_in_valid=0;return;}
  }
  throw std::runtime_error("send timeout");
}
int main(int argc,char **argv) { try {
  Verilated::commandArgs(argc,argv);require(argc==3,"vectors model");
  uint16_t endian=1;require(*reinterpret_cast<uint8_t*>(&endian)==1,"little-endian host required");
  const std::string dir=argv[1],model=argv[2];
  auto points=load<uint64_t>(dir+"/points.bin");
  auto offsets=load<uint64_t>(dir+"/offsets.bin");
  auto features=load<uint8_t>(dir+"/features.bin");
  auto logits=load<int32_t>(dir+"/"+model+"_logits.bin");
  const size_t rows=offsets.size()-1;
  require(features.size()==rows*21 && logits.size()==rows*2 && offsets.back()==points.size(),"vector sizes");
  VCandidateTop d;reset(d);
  // Abort a partial point frame, then abort a classifier that already received
  // a completed feature frame; neither is allowed to leak a stale output.
  send(d,5,false);send(d,0,false);d.io_abort=1;tick(d);d.io_abort=0;
  for(int i=0;i<40;i++){tick(d);require(!d.io_out_valid,"partial abort leaked result");}
  send(d,1,false);send(d,0,true);
  for(int i=0;i<130;i++){tick(d);require(!d.io_out_valid,"unexpected early logit");}
  d.io_abort=1;tick(d);d.io_abort=0;
  for(int i=0;i<2000;i++){tick(d);require(!d.io_out_valid,"classifier abort leaked result");}
  // Deliberately invalid oversized header with TLAST must set the sticky bit.
  send(d,512,true);tick(d);require(d.io_featureStatus & (1u<<11),"malformed header not flagged");
  reset(d);
  uint64_t cycles=0, input_stalls=0, output_stalls=0, feature_beats=0;
  size_t inrow=0, inbeat=0, frow=0, fbeat=0, outrow=0;
  bool pending=false,prev_stalled=false;uint64_t stalled_data=0;uint8_t stalled_keep=0,stalled_last=0;
  auto last_row=[&](size_t row){return row%7==6 || row+1==rows;};
  while(outrow<rows) {
    require(cycles < rows*5000ull+20000,"cycle timeout");
    // Hold an offered beat until accepted. Gaps and long output stalls exercise
    // two-context overlap, backpressure propagation and payload stability.
    if(!pending && inrow<rows && cycles%11!=3) {
      size_t count=offsets[inrow+1]-offsets[inrow];
      d.io_in_bits_data=inbeat==0?count:points[offsets[inrow]+inbeat-1];
      d.io_in_bits_keep=255;d.io_in_bits_last=inbeat==count && last_row(inrow);
      pending=true;
    }
    d.io_in_valid=pending;
    d.io_out_ready=cycles%13!=5 && cycles%4096>=200;
    d.clock=0;d.eval();
    if(prev_stalled)require(d.io_out_valid && d.io_out_bits_data==stalled_data &&
        d.io_out_bits_keep==stalled_keep && d.io_out_bits_last==stalled_last,"unstable stalled output");
    prev_stalled=d.io_out_valid && !d.io_out_ready;
    if(prev_stalled){stalled_data=d.io_out_bits_data;stalled_keep=d.io_out_bits_keep;stalled_last=d.io_out_bits_last;output_stalls++;}
    require(!(d.io_featureStatus&(1u<<11)) && !(d.io_qmlpStatus&(1u<<8)),"unexpected protocol error");
    if(d.io_featureFire) {
      require(frow<rows,"extra feature frame");
      require(d.io_featureKeep==255 && bool(d.io_featureLast)==(fbeat==3 && last_row(frow)),"feature framing");
      for(size_t lane=0;lane<8;lane++) {
        size_t j=fbeat*8+lane;uint8_t expected=j<21?features[frow*21+j]:0;
        uint8_t got=(d.io_featureData>>(lane*8))&255;
        require(got==expected,"feature mismatch row="+std::to_string(frow)+" slot="+std::to_string(j)+
          " got="+std::to_string(got)+" expected="+std::to_string(expected));
      }
      feature_beats++; if(++fbeat==4){fbeat=0;frow++;}
    }
    if(d.io_out_valid && d.io_out_ready) {
      require(outrow<rows,"extra logit");
      int32_t a=int32_t(d.io_out_bits_data),b=int32_t(d.io_out_bits_data>>32);
      require(a==logits[outrow*2] && b==logits[outrow*2+1],"logit mismatch row="+std::to_string(outrow)+
          " got="+std::to_string(a)+","+std::to_string(b)+" expected="+std::to_string(logits[outrow*2])+","+std::to_string(logits[outrow*2+1]));
      require(d.io_out_bits_keep==255 && bool(d.io_out_bits_last)==last_row(outrow),"logit framing");outrow++;
    }
    if(pending && d.io_in_ready) {
      pending=false;
      if(++inbeat > offsets[inrow+1]-offsets[inrow]){inbeat=0;inrow++;}
    } else if(pending) input_stalls++;
    d.clock=1;d.eval();cycles++;
  }
  require(inrow==rows && frow==rows && fbeat==0,"incomplete transaction counts");
  d.io_in_valid=0;d.io_out_ready=1;
  for(int i=0;i<2000;i++){tick(d);require(!d.io_out_valid,"trailing duplicate result");}
  require(output_stalls>0 && input_stalls>0,"backpressure not exercised");
  std::ofstream f("rtl_result.json");
  f<<"{\n  \"status\":\"PASS\",\n  \"rows\":"<<rows<<",\n  \"feature_bytes_checked\":"<<rows*32
   <<",\n  \"logits_checked\":"<<rows*2<<",\n  \"cycles_with_testbench_stalls\":"<<cycles
   <<",\n  \"input_stall_cycles\":"<<input_stalls<<",\n  \"output_stall_cycles\":"<<output_stalls
   <<",\n  \"abort_recovery\":true,\n  \"malformed_header_flag\":true,\n  \"scope\":\"Standalone RTL correctness; injected stalls, not a board performance measurement\"\n}\n";
  std::cout<<"PASS "<<model<<" rows="<<rows<<" feature_beats="<<feature_beats<<"\n";
  d.final();return 0;
} catch(const std::exception &e){std::cerr<<"FAIL "<<e.what()<<"\n";return 1;} }
