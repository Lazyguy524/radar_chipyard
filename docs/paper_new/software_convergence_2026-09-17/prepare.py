"""Rebuild true sparse train support and matched synthetic pools before training."""
from collections import deque
import gzip
import h5py
from sw_common import *

def main():
    LOG.mkdir(exist_ok=False);start=time.monotonic();out=LOG/'data';out.mkdir()
    def budget():
        if time.monotonic()-start>PLAN['budgets']['preparation_seconds']:raise TimeoutError('Preparation budget')
    native=base.Native();kernel=base.module('sw_integer_python',ROOT/'docs/paper_new/conditional_statistics_2026-09-16/kernel.py')
    rng=np.random.default_rng(20260917);cases=0
    ex,fr=base.scales()
    for n in (1,2,3,7,8,9,31,32,33,255,256,257,511):
        for kind in range(4):
            q=rng.integers(-32768,32768,(n,4),dtype=np.int16)
            if kind==1:q[:]=q[0]
            if kind==2:q[:,1]=q[:,0]
            if kind==3:q[:,:2]//=64;q[:,:2]+=25000
            for bits in (12,16,24):
                raw,z=native(q,bits,24);means,_,_=kernel.python_moments(q,bits)
                assert np.array_equal(raw[1,[1,2,14,18]],means)
                quant=np.clip(np.rint(raw[:2].astype(float)/np.exp2((ex+fr)[:2])),-127,127).astype(np.int8)
                assert np.array_equal(quant,z[:2]);cases+=1
    dump(LOG/'synthetic_preflight.json',dict(status='PASS',integer_cases=cases,training_started=False))
    with gzip.open(pc.MANIFEST,'rt') as f:manifest=list(csv.DictReader(f))
    seqsets={s:set(r['sequence_id'] for r in manifest if r['split']==s) for s in ('train','val','test')}
    assert len(seqsets['train'])==113 and len(seqsets['val'])==27
    assert all(not seqsets[a]&seqsets[b] for a,b in (('train','val'),('train','test'),('val','test')))
    prior_hashes={}
    for split in ('train','val'):
        for r in json.loads((MECH/'raw'/(split+'_summary.json')).read_text())['raw_hdf5_metadata']:prior_hashes[r['path']]=r['sha256']
    sources=[HERE/'plan.json',HERE/'prepare.py',HERE/'sw_common.py',pc.MANIFEST,MECH/'native/mechanism.c',MECH/'native/mechanism.so',base.PREV/'data/output_scale_exponents.json']
    reports=[];alltrack={};val_sparse_points={'sparse_single':[],'sparse_context':[]};val_sparse_offsets={v:[0] for v in val_sparse_points}
    precision={}
    for bits in (12,16):
        d=out/'precision'/str(bits);d.mkdir(parents=True)
        for c in PLAN['evaluation']['conditions']:
            n=PLAN['data']['val_sparse' if c.startswith('sparse_') else 'val_kept']
            precision[(bits,c)]=np.lib.format.open_memmap(d/(c+'.npy'),mode='w+',dtype=np.int8,shape=(n,21))
    for split in ('train','val'):
        d=out/split;d.mkdir();kept_n=PLAN['data'][split+'_kept'];sparse_n=PLAN['data'][split+'_sparse']
        oldmeta=readcsv(MECH/'raw'/split/'metadata.csv');rowindex={int(r['packed_row']):i for i,r in enumerate(oldmeta)}
        clean={m:np.load(MECH/'data'/split/(m+'.npy')) for m in MODES};labels=np.load(MECH/'data'/split/'labels.npy')
        natural={m:np.lib.format.open_memmap(d/('natural_'+m+'.npy'),mode='w+',dtype=np.int8,shape=(sparse_n,21)) for m in MODES}
        ngroup=np.empty(sparse_n,np.int8);ny=np.empty(sparse_n,np.int64)
        if split=='train':
            synthetic={m:np.lib.format.open_memmap(d/('synthetic_'+m+'.npy'),mode='w+',dtype=np.int8,shape=(kept_n*2,21)) for m in MODES};sgroup=np.empty(kept_n*2,np.int8)
        else:
            old_sparse={v:{m:np.load(MECH/'raw'/v/(m+'.npy')) for m in MODES} for v in val_sparse_points}
            old_sparse_meta=readcsv(MECH/'raw/sparse_context/metadata.csv')
        seen=np.zeros(kept_n,bool);si=0;tracks=set();histages=[];drifts=[];mix_count=0;seqstats=[]
        fields=['sequence','sensor','track','frame','label','raw_points','n','prior_history','history_span_raw','centroid_displacement','current_range','group','kept_row']
        metadata_file=(d/'observations.csv').open('w',newline='');writer=csv.DictWriter(metadata_file,fieldnames=fields);writer.writeheader()
        byseq={}
        for r in manifest:
            if r['split']==split:byseq.setdefault(r['sequence_id'],[]).append(r)
        for seq,rows in byseq.items():
            budget();directory=pc.RAW/seq;scene_path=directory/'scenes.json';h5=directory/'radar_data.h5'
            assert sha(h5)==prior_hashes[str(h5)],h5
            sources.append(scene_path);scenes=json.loads(scene_path.read_text())['scenes']
            with h5py.File(h5,'r') as f:radar=f['radar_data'][:]
            lookup={(int(r['sensor_id']),r['track_id'].encode(),r['frame_key']):r for r in rows}
            assert len(lookup)==len(rows)
            observations=[]
            for frame,scene in scenes.items():
                b,e=scene['radar_indices'];v=radar[b:e]
                ids=np.flatnonzero(np.isin(v['label_id'],[0,1,2,3,7,8])&(v['track_id']!=b''))+b
                keys,inverse=np.unique(radar['track_id'][ids],return_inverse=True)
                for k,key in enumerate(keys):observations.append((int(scene['sensor_id']),key,frame,ids[inverse==k]))
            observations.sort(key=lambda x:(x[0],x[1],int(x[2])));history=deque(maxlen=7);previous=None;kept=0;small=0
            for oi,(sensor,track,frame,ids) in enumerate(observations):
                if oi%512==0:budget()
                key=(sensor,track)
                if key!=previous:history.clear();previous=key
                tracks.add(track.decode());a=radar[ids];p=np.stack([a['x_cc'],a['y_cc'],a['vr_compensated'],a['rcs']],axis=1).astype(np.float32)
                label_id=int(np.bincount(a['label_id'].astype(int)).argmax());label=0 if label_id in (7,8) else 1
                mix_count+=int(len(np.unique(np.isin(a['label_id'],[7,8])))>1)
                prior=list(history)[-6:];assert all(h[1]<int(frame) for h in prior)
                joined=np.concatenate([h[0] for h in prior]+[p]);q=views.q8(joined);assert 1<=len(q)<=511
                age=int(frame)-prior[0][1] if prior else 0
                drift=float(np.linalg.norm(p[:,:2].mean(0)-prior[0][0][:,:2].mean(0))) if prior else 0.
                dist=float(np.hypot(*views.q8(p)[:,:2].mean(0))/256)
                histages.append(age);drifts.append(drift)
                row=dict(sequence=seq,sensor=sensor,track=track.decode(),frame=frame,label=label,raw_points=len(p),n=len(q),prior_history=len(prior),history_span_raw=age,centroid_displacement=drift,current_range=dist,group=-1,kept_row=-1)
                _,z=native(q)
                if len(p)>=3:
                    r=lookup[(sensor,track,frame)];i=rowindex[int(r['packed_row'])];assert not seen[i] and labels[i]==label
                    assert len(q)==int(oldmeta[i]['n'])
                    for j,m in enumerate(MODES):assert np.array_equal(z[j],clean[m][i]),(split,seq,i,m)
                    oldmeta[i].update(prior_history=len(prior),current_range=dist,history_span_raw=age,centroid_displacement=drift)
                    seen[i]=True;row['kept_row']=i
                    if split=='train':
                        seed=int.from_bytes(hashlib.sha256((seq+':'+str(sensor)+':'+track.decode()+':'+frame+':sw_sparse').encode()).digest()[:8],'little')
                        order=np.random.default_rng(seed).permutation(len(p))
                        for k in (1,2):
                            sq=views.q8(np.concatenate([h[0] for h in prior]+[p[np.sort(order[:k])]]));_,sz=native(sq)
                            ix=i*2+k-1
                            for j,m in enumerate(MODES):synthetic[m][ix]=sz[j]
                            sgroup[ix]=stratum(label,k,len(prior))
                    else:
                        conditions={'clean':q,**views.sample_views(q,seq,r['packed_row'],True),'kept_single':views.q8(p)}
                        for c,points in conditions.items():
                            for bits in (12,16):precision[(bits,c)][i]=native(points,bits,24)[1][1]
                    history.append((p,int(frame)));kept+=1
                else:
                    assert si<sparse_n;ngroup[si]=stratum(label,len(p),len(prior));ny[si]=label;row['group']=int(ngroup[si])
                    for j,m in enumerate(MODES):natural[m][si]=z[j]
                    if split=='val':
                        old=old_sparse_meta[si];assert (old['sequence'],int(old['sensor']),old['track'],old['frame'],int(old['label']))==(seq,sensor,track.decode(),frame,label)
                        for v,points in [('sparse_single',views.q8(p)),('sparse_context',q)]:
                            expected=native(points)[1]
                            for j,m in enumerate(MODES):assert np.array_equal(expected[j],old_sparse[v][m][si])
                            for bits in (12,16):precision[(bits,v)][si]=native(points,bits,24)[1][1]
                            val_sparse_points[v].append(points);val_sparse_offsets[v].append(val_sparse_offsets[v][-1]+len(points))
                    si+=1;small+=1
                writer.writerow(row)
            assert kept==len(rows);seqstats.append(dict(sequence=seq,kept=kept,sparse=small))
            print(json.dumps(dict(stage='prepare',split=split,sequence=seq,kept=int(seen.sum()),sparse=si,seconds=round(time.monotonic()-start,1))),flush=True)
        metadata_file.close();assert seen.all() and si==sparse_n
        np.save(d/'natural_labels.npy',ny);np.save(d/'natural_groups.npy',ngroup)
        for a in natural.values():a.flush()
        if split=='train':
            for a in synthetic.values():a.flush()
            np.save(d/'synthetic_groups.npy',sgroup);np.save(d/'synthetic_labels.npy',np.repeat(labels,2))
        writecsv(d/'kept_metadata.csv',oldmeta);alltrack[split]=tracks
        reports.append(dict(split=split,kept=int(seen.sum()),sparse=si,sequences=seqstats,binary_mixed_label_observations=mix_count,
            history_span_raw_quantiles=np.quantile(histages,[0,.5,.9,.99,1]).tolist(),centroid_displacement_quantiles=np.quantile(drifts,[0,.5,.9,.99,1]).tolist(),future_history_violations=0,primary_feature_mismatches=0))
    # A global track UUID shared across splits requires investigation, not silence.
    overlap=sorted(alltrack['train']&alltrack['val']);assert not overlap,('Cross-split track IDs',overlap[:10])
    for a in precision.values():a.flush()
    for v,p in val_sparse_points.items():
        d=out/v;d.mkdir();np.save(d/'points.npy',np.concatenate(p));np.save(d/'offsets.npy',np.array(val_sparse_offsets[v],np.uint64))
    sg=np.load(out/'train/synthetic_groups.npy');ng=np.load(out/'train/natural_groups.npy')
    sc=np.bincount(sg,minlength=12);nc=np.bincount(ng,minlength=12);common=(sc>0)&(nc>0);probs=nc*common;probs=probs/probs.sum()
    dump(out/'matching.json',dict(synthetic_counts=sc.tolist(),natural_counts=nc.tolist(),common_groups=np.flatnonzero(common).tolist(),probabilities=probs.tolist(),excluded_natural=int(nc[~common].sum()),excluded_synthetic=int(sc[~common].sum()),definition='label*6+(current_points-1)*3+history_bin'))
    result=dict(status='PASS',integer_cases=cases,splits=reports,cross_split_track_overlap=0,source_sha256={str(p.relative_to(ROOT)) if ROOT in p.parents else str(p):sha(p) for p in sources},
        raw_hdf5_sha256=prior_hashes,wall_seconds=time.monotonic()-start,output_bytes=size_guard(),scope='Train/validation reconstruction only, no historical-test records loaded beyond split identity manifest; no training yet')
    dump(LOG/'preparation.json',result);print(json.dumps(dict(status='PASS',seconds=result['wall_seconds'],output_bytes=result['output_bytes'])),flush=True)
if __name__=='__main__':main()
