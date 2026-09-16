"""Full validation perturbations, real rejected observations and train views."""
import argparse
from collections import deque
import csv
import gzip
import time
import h5py
from common import *

def csv_rows(p):
    with Path(p).open() as f:return list(csv.DictReader(f))
def write_csv(p,rows):
    with Path(p).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def q8(points):return np.ascontiguousarray(np.clip(np.rint(np.asarray(points,dtype=np.float32)*256),-32768,32767),np.int16)
def sample_views(q,seq,packed,validation):
    n=len(q);views={}
    for rep in range(3 if validation else 1):
        key=seq+str(packed)+'perturb'+('' if rep==0 else ':rep'+str(rep))
        seed=int.from_bytes(hashlib.sha256(key.encode()).digest()[:8],'little')
        order=np.random.default_rng(seed).permutation(n)
        if validation:views['uniform_half_'+str(rep)]=q[np.sort(order[:(n+1)//2])]
        views['uniform_quarter_'+str(rep)]=q[np.sort(order[:(n+3)//4])]
    c=q[:,:2].astype(float);near=np.argsort(np.sum((c-c.mean(0))**2,axis=1),kind='stable')
    views['central_half']=q[np.sort(near[:(n+1)//2])]
    if validation:
        for fraction in [6,4]:
            z=q.copy();step=2**(8-fraction);z[:,:2]=np.clip(np.rint(z[:,:2].astype(float)/step)*step,-32768,32767).astype(np.int16)
            views['xy_fraction'+str(fraction)]=z
    return views
def sparse_shape(q):
    if len(q)<3:return 'undefined_low_support',None
    eig=np.linalg.eigvalsh(np.cov(q[:,:2].astype(float).T,bias=True))
    if eig[1]<=0:return 'undefined_zero_spread',None
    ratio=max(0,float(eig[0]))/float(eig[1]);return 'elongated' if ratio<=.1 else ('compact' if ratio>.5 else 'intermediate'),ratio

def main():
    a=argparse.ArgumentParser();a.add_argument('--split',choices=['train','val'],required=True);split=a.parse_args().split
    validation=split=='val';started=time.monotonic();native=Native();root=LOG/'raw';root.mkdir(exist_ok=True)
    out=root/split;out.mkdir(exist_ok=False)
    n=PLAN['data']['validation_rows' if validation else 'train_rows'];y=np.load(LOG/'data'/split/'labels.npy')
    meta=csv_rows(PREV/'data'/split/'metadata.csv');byid={int(r['packed_row']):i for i,r in enumerate(meta)}
    with gzip.open(pc.MANIFEST,'rt') as f:manifest=[r for r in csv.DictReader(f) if r['split']==split]
    byseq={}
    for r in manifest:byseq.setdefault(r['sequence_id'],[]).append(r)
    conditions=[c for c in PLAN['paired_diagnostics']['conditions'] if c!='clean'] if validation else ['uniform_quarter_0','central_half']
    arrays={};clean={m:np.load(LOG/'data'/split/(m+'.npy')) for m in MODES}
    for mode in MODES:
        d=out/mode;d.mkdir()
        for c in conditions:arrays[(mode,c)]=np.lib.format.open_memmap(d/(c+'.npy'),mode='w+',dtype=np.int8,shape=(n,21))
    precisions={}
    if validation:
        offsets=np.concatenate([[0],np.cumsum([int(r['n']) for r in meta])]).astype(np.int64)
        np.save(out/'offsets.npy',offsets)
        all_points=np.lib.format.open_memmap(out/'points_q8.npy',mode='w+',dtype=np.int16,shape=(int(offsets[-1]),4))
        for mb,vb in PLAN['precision']['configurations']:
            d=root/'precision'/('m%d_v%d'%(mb,vb));d.mkdir(parents=True)
            for c in PLAN['paired_diagnostics']['primary']:
                cd=d/c;cd.mkdir()
                for mode in MODES:precisions[(mb,vb,mode,c)]=np.lib.format.open_memmap(cd/(mode+'.npy'),mode='w+',dtype=np.int8,shape=(n,21))
    rejected={view:{m:[] for m in MODES} for view in ['sparse_single','sparse_context']};rejected_meta={v:[] for v in rejected}
    seen=np.zeros(n,bool);seqstats=[];hdf5=[];sources=[HERE/'prepare_views.py',HERE/'mechanism.c',HERE/'plan.json',LOG/'native/mechanism.c',LOG/'data/scales.json',pc.MANIFEST]
    def budget():
        prior=json.loads((root/'val_summary.json').read_text())['wall_seconds'] if split=='train' and (root/'val_summary.json').exists() else 0
        if time.monotonic()-started+prior>PLAN['budgets']['raw_preparation_seconds']:raise TimeoutError('Combined raw preparation budget')
    def retained(points,history,row):
        i=byid[int(row['packed_row'])];assert not seen[i];history.append(points);fused=q8(np.concatenate(list(history)));_,z=native(fused)
        assert len(fused)==int(meta[i]['n'])
        meta[i].update(raw_points=len(points),retained_history=len(history),frame_key=row['frame_key'],sensor=row['sensor_id'],track=row['track_id'])
        for flag,mode in enumerate(MODES):assert np.array_equal(z[flag],clean[mode][i]),(split,row['sequence_id'],i,mode)
        v=sample_views(fused,row['sequence_id'],row['packed_row'],validation)
        if validation:v['kept_single']=q8(points)
        for c,p in v.items():
            _,z=native(p)
            for flag,mode in enumerate(MODES):arrays[(mode,c)][i]=z[flag]
        if validation:
            all_points[offsets[i]:offsets[i+1]]=fused
            for c in PLAN['paired_diagnostics']['primary']:
                q=fused if c=='clean' else v[c]
                for mb,vb in PLAN['precision']['configurations']:
                    _,z=native(q,mb,vb)
                    for flag,mode in enumerate(MODES):precisions[(mb,vb,mode,c)][i]=z[flag]
        seen[i]=True
    for seq,rows in byseq.items():
        budget();base=pc.RAW/seq;scene_path=base/'scenes.json';scenes=json.loads(scene_path.read_text())['scenes'];sources.append(scene_path)
        h5=base/'radar_data.h5';st=h5.stat();hdf5.append(dict(sequence=seq,path=str(h5),bytes=st.st_size,mtime_ns=st.st_mtime_ns,sha256=sha(h5)))
        with h5py.File(h5,'r') as f:radar=f['radar_data'][:]
        if not validation:
            history=deque(maxlen=7);previous=None
            for k,row in enumerate(rows):
                if k%512==0:budget()
                key=(int(row['sensor_id']),row['track_id'])
                if key!=previous:history.clear();previous=key
                b,e=scenes[row['frame_key']]['radar_indices'];v=radar[b:e]
                v=v[(v['track_id']==row['track_id'].encode())&np.isin(v['label_id'],[0,1,2,3,7,8])]
                p=np.stack([v['x_cc'],v['y_cc'],v['vr_compensated'],v['rcs']],axis=1).astype(np.float32)
                retained(p,history,row)
            seqstats.append(dict(sequence=seq,retained=len(rows),rejected=None))
        else:
            lookup={(int(r['sensor_id']),r['track_id'].encode(),r['frame_key']):r for r in rows};observations=[]
            for frame,scene in scenes.items():
                b,e=scene['radar_indices'];v=radar[b:e];mask=np.isin(v['label_id'],[0,1,2,3,7,8])&(v['track_id']!=b'');ids=np.flatnonzero(mask)+b
                keys,inverse=np.unique(radar['track_id'][ids],return_inverse=True)
                for k,key in enumerate(keys):observations.append((int(scene['sensor_id']),key,frame,ids[inverse==k]))
            observations.sort(key=lambda r:(r[0],r[1],int(r[2])))
            history=deque(maxlen=7);previous=None;kept=0;small=0
            for oi,(sensor,track,frame,ids) in enumerate(observations):
                if oi%512==0:budget()
                key=(sensor,track)
                if key!=previous:history.clear();previous=key
                a=radar[ids];p=np.stack([a['x_cc'],a['y_cc'],a['vr_compensated'],a['rcs']],axis=1).astype(np.float32)
                label=int(np.bincount(a['label_id'].astype(int)).argmax());label=0 if label in [7,8] else 1
                if len(p)>=3:
                    row=lookup[(sensor,track,frame)];assert label==int(y[byid[int(row['packed_row'])]])
                    retained(p,history,row);kept+=1
                else:
                    context=q8(np.concatenate(list(history)[-6:]+[p]));single=q8(p)
                    for view,q in [('sparse_single',single),('sparse_context',context)]:
                        _,z=native(q);shape,ratio=sparse_shape(q)
                        for flag,mode in enumerate(MODES):rejected[view][mode].append(z[flag].copy())
                        rejected_meta[view].append(dict(sequence=seq,sensor=sensor,track=track.decode(),frame=frame,label=label,n=len(q),raw_points=len(p),
                            retained_history_used=0 if view=='sparse_single' else min(6,len(history)),shape_group=shape,shape_ratio=ratio,
                            current_centroid_range=float(np.hypot(single[:,0].mean(),single[:,1].mean())/256)))
                    small+=1
            assert kept==len(rows);seqstats.append(dict(sequence=seq,retained=kept,rejected=small))
        del radar
        print(json.dumps(dict(split=split,sequence=seq,retained_done=int(seen.sum()),seconds=round(time.monotonic()-started,2))),flush=True)
    assert seen.all()
    write_csv(out/'metadata.csv',meta)
    for v in arrays.values():v.flush()
    for v in precisions.values():v.flush()
    if validation:
        all_points.flush()
        assert len(rejected_meta['sparse_single'])==PLAN['sparse_audit']['expected_excluded_observations']
        for view in rejected:
            d=root/view;d.mkdir()
            for mode in MODES:np.save(d/(mode+'.npy'),np.asarray(rejected[view][mode],np.int8))
            np.save(d/'labels.npy',np.array([r['label'] for r in rejected_meta[view]],np.int64));write_csv(d/'metadata.csv',rejected_meta[view])
        # Verify the previously published replicate-0 subset is identical, preserving comparison continuity.
        dm=csv_rows(PREV/'data/diagnostic/metadata.csv');indices=np.array([int(r['validation_row']) for r in dm])
        for mode,oldmode in [('proxy','proxy_scaled'),('moment','moment24')]:
            for newc,oldc in [('uniform_half_0','uniform_half'),('uniform_quarter_0','uniform_quarter'),('central_half','central_half'),('xy_fraction6','xy_fraction6')]:
                assert np.array_equal(arrays[(mode,newc)][indices],np.load(PREV/'data/diagnostic'/(oldmode+'_'+oldc+'.npy')))
    report=dict(status='PASS',split=split,retained=n,primary_feature_reconstruction_mismatches=0,conditions=conditions,
        rejected_observations=len(rejected_meta['sparse_single']) if validation else 0,sequences=seqstats,raw_hdf5_metadata=hdf5,
        wall_seconds=time.monotonic()-started,source_sha256={str(p.relative_to(ROOT)) if ROOT in p.parents else str(p):sha(p) for p in sources},plan_sha256=sha(HERE/'plan.json'))
    dump(root/(split+'_summary.json'),report)
    if (root/'val_summary.json').exists() and (root/'train_summary.json').exists():
        dump(root/'summary.json',dict(status='PASS',splits={s:json.loads((root/(s+'_summary.json')).read_text()) for s in ['train','val']}))
    print(json.dumps({k:v for k,v in report.items() if k not in ['source_sha256','raw_hdf5_metadata','sequences']}),flush=True)

if __name__=='__main__':main()
