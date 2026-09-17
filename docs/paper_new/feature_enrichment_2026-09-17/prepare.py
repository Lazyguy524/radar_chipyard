"""Reconstruct identical causal observations; add descriptors, preserve old inputs."""
from collections import deque
import csv,h5py
from ex_common import *

def main():
    assert json.loads((LOG/'synthetic_preflight.json').read_text())['status']=='PASS';start=time.monotonic();out=LOG/'data';out.mkdir(exist_ok=False);native=Native();reports=[];rawhash=json.loads((OLD/'preparation.json').read_text())['raw_hdf5_sha256'];source={}
    def budget():
        if time.monotonic()-start>PLAN['budget']['preparation_seconds']:raise TimeoutError('Preparation budget; preserve evidence, no training')
    for split in ['train','val']:
        d=out/split;d.mkdir();n=357780 if split=='train' else 80450;small=474582 if split=='train' else 97734
        names=['clean','uniform_quarter_0','central_half','synthetic','natural'] if split=='train' else PLAN['evaluation']['conditions']
        arrays={name:np.lib.format.open_memmap(d/(name+'.npy'),mode='w+',dtype=np.int8,shape=((n*2 if name=='synthetic' else small if name=='natural' or name.startswith('sparse_') else n),7)) for name in names}
        if split=='train':oldarrays=ab.pools.Pools('proxy').arrays;oldmap=dict(zip(names,oldarrays))
        else:oldmap={c:sw.validation(c)[0] for c in names}
        kept=readcsv(OLD/'data'/split/'kept_metadata.csv');labels=np.load(MECH/'data'/split/'labels.npy');slabels=np.load(OLD/'data'/split/'natural_labels.npy');seen=np.zeros(n,bool);si=0;seqcount=0;byseq={}
        observations=OLD/'data'/split/'observations.csv';source[str(observations.relative_to(ROOT))]=sha(observations)
        with observations.open() as f:
            for row in csv.DictReader(f):byseq.setdefault(row['sequence'],[]).append(row)
        for seq,rows in byseq.items():
            budget();directory=pc.RAW/seq;hp=directory/'radar_data.h5';assert sha(hp)==rawhash[str(hp)],hp;source[str(hp)]=rawhash[str(hp)]
            sp=directory/'scenes.json';source[str(sp)]=sha(sp);scenes=json.loads(sp.read_text())['scenes']
            with h5py.File(hp,'r') as f:radar=f['radar_data'][:]
            history=deque(maxlen=7);last=None
            for j,row in enumerate(rows):
                if j%512==0:budget()
                sensor,track,frame=int(row['sensor']),row['track'],row['frame'];key=(sensor,track)
                if key!=last:history.clear();last=key
                scene=scenes[frame];assert int(scene['sensor_id'])==sensor;b,e=scene['radar_indices'];a=radar[b:e];a=a[(a['track_id']==track.encode())&np.isin(a['label_id'],[0,1,2,3,7,8])]
                p=np.stack([a['x_cc'],a['y_cc'],a['vr_compensated'],a['rcs']],axis=1).astype(np.float32)
                assert len(p)==int(row['raw_points']) and len(p)>0
                lid=int(np.bincount(a['label_id'].astype(int)).argmax());label=0 if lid in [7,8] else 1;assert label==int(row['label'])
                prior=list(history)[-6:];assert len(prior)==int(row['prior_history']) and all(t<int(frame) for _,t in prior)
                age=int(frame)-prior[0][1] if prior else 0;assert age==int(row['history_span_raw'])
                q=sw.views.q8(np.concatenate([h[0] for h in prior]+[p]));assert len(q)==int(row['n'])
                if len(p)>=3:
                    i=int(row['kept_row']);assert not seen[i] and labels[i]==label;seen[i]=True;meta=kept[i]
                    assert (meta['sequence'],int(meta['sensor']),meta['track'],meta['frame_key'])==(seq,sensor,track,frame)
                    variants={'clean':q,**sw.views.sample_views(q,seq,meta['packed_row'],split=='val')}
                    if split=='val':variants['kept_single']=sw.views.q8(p)
                    for name,z in variants.items():
                        x=native(z);assert np.array_equal(x[:16],oldmap[name][i,COLS]),(split,name,i);arrays[name][i]=x[16:]
                    if split=='train':
                        seed=int.from_bytes(hashlib.sha256((seq+':'+str(sensor)+':'+track+':'+frame+':sw_sparse').encode()).digest()[:8],'little');order=np.random.default_rng(seed).permutation(len(p))
                        for k in [1,2]:
                            sq=sw.views.q8(np.concatenate([h[0] for h in prior]+[p[np.sort(order[:k])]]));x=native(sq);ix=2*i+k-1
                            assert np.array_equal(x[:16],oldmap['synthetic'][ix,COLS]);arrays['synthetic'][ix]=x[16:]
                    history.append((p,int(frame)))
                else:
                    assert int(row['kept_row'])==-1 and slabels[si]==label
                    variants={'natural':q} if split=='train' else {'sparse_single':sw.views.q8(p),'sparse_context':q}
                    for name,z in variants.items():
                        x=native(z);assert np.array_equal(x[:16],oldmap[name][si,COLS]),(split,name,si);arrays[name][si]=x[16:]
                    si+=1
            seqcount+=1;print(json.dumps(dict(split=split,sequence=seq,kept=int(seen.sum()),sparse=si,seconds=time.monotonic()-start)),flush=True)
        assert seen.all() and si==small and seqcount==(113 if split=='train' else 27)
        for a in arrays.values():a.flush()
        reports.append(dict(split=split,sequences=seqcount,kept=n,sparse=si,views=names,feature_rows=sum(len(a) for a in arrays.values()),base16_mismatches=0,label_mismatches=0,future_history_violations=0))
    assert time.monotonic()-start<1800;dump(LOG/'preparation.json',dict(status='PASS',splits=reports,wall_seconds=time.monotonic()-start,source_sha256=source,scope='Same causal train/development observations; no new test data; all base16 features checked, new7 descriptors computed from point data',output_bytes=size_guard()))
    print('PREPARATION_PASS',time.monotonic()-start,flush=True)
if __name__=='__main__':main()
