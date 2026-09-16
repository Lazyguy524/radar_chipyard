"""One raw-data pass per sequence for statistics, paired inputs and filter audit."""
import csv
import gzip
import time
from collections import Counter,deque
import h5py
from kernel import *

BASE=ROOT/'logs/qmlp_int8_convergence_20260916'
PILOT=ROOT/'logs/feature_approximation_pilot_20260916'

def write_csv(p,rows):
    with p.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def audit_sequence(radar,scenes,split,seq):
    counts=Counter();kept=0;outside_points=0;missing_track_points=0
    for scene in scenes.values():
        b,e=scene['radar_indices'];v=radar[b:e];valid=np.isin(v['label_id'],[0,1,2,3,7,8])
        outside_points+=int(np.count_nonzero(~valid));v=v[valid]
        missing_track_points+=int(np.count_nonzero(v['track_id']==b''));v=v[v['track_id']!=b'']
        ids,inverse,numbers=np.unique(v['track_id'],return_inverse=True,return_counts=True)
        for i,n in enumerate(numbers):
            a=v[inverse==i];label=int(np.bincount(a['label_id'].astype(int)).argmax());y=0 if label in [7,8] else 1
            distance=float(np.hypot(a['x_cc'].mean(),a['y_cc'].mean()))
            group='1' if n==1 else ('2' if n==2 else '3_or_more')
            counts[(y,group,'near_le20' if distance<=20 else ('mid_le40' if distance<=40 else 'far_gt40'))]+=1
            kept+=int(n>=3)
    rows=[dict(split=split,sequence=seq,label=y,points_group=g,range_group=d,observations=n) for (y,g,d),n in sorted(counts.items())]
    return rows,dict(sequence=seq,split=split,eligible_ge3_observations=kept,outside_binary_label_points=outside_points,missing_track_target_points=missing_track_points)

def main():
    pre=json.loads((LOG/'preflight.json').read_text());assert pre['status']=='PASS' and pre['plan_sha256']==sha(HERE/'plan.json')
    for path,digest in pre['source_sha256'].items():assert sha(ROOT/path)==digest
    started=time.monotonic();out=LOG/'data';out.mkdir(exist_ok=False);k=Kernel(LOG/'native',False)
    with gzip.open(pc.MANIFEST,'rt') as f:manifest=[r for r in csv.DictReader(f) if r['split'] in ['train','val']]
    audits=[];audit_overview=[];raw_meta={};summaries={};diagnostics={m:{c:[] for c in PLAN['diagnostics']['paired_conditions']} for m in MODES+['legacy']}
    diagmeta=[];diagpoints=[];diagoffsets=[0];sources=[pc.MANIFEST,HERE/'plan.json',HERE/'kernel.py',HERE/'moments.c',HERE/'prepare.py']
    for split in ['train','val']:
        splitdir=out/split;splitdir.mkdir();byseq={}
        for row in manifest:
            if row['split']==split:byseq.setdefault(row['sequence_id'],[]).append(row)
        reference=BASE/'train' if split=='train' else PILOT/'full'
        base_name='features.npy' if split=='train' else 'deployment.npy'
        old=np.load(reference/base_name);ys=np.load(reference/'labels.npy')
        with gzip.open(reference/'metadata.csv.gz','rt') as f:oldmeta=list(csv.DictReader(f))
        sources.extend([reference/base_name,reference/'labels.npy',reference/'metadata.csv.gz'])
        byid={int(r['packed_row']):i for i,r in enumerate(oldmeta)}
        arrays={m:np.lib.format.open_memmap(splitdir/(m+'_raw.npy'),mode='w+',dtype=np.int64,shape=(len(ys),21)) for m in MODES}
        meta=[None]*len(ys);mismatches=0;negative=np.zeros(3,np.int64);seen=0;saturated=0
        for seq,rows in byseq.items():
            if time.monotonic()-started>PLAN['budget']['prepare_seconds']:raise TimeoutError('Raw preparation budget')
            h5=pc.RAW/seq/'radar_data.h5';stat=h5.stat();raw_meta[seq]=dict(bytes=stat.st_size,mtime_ns=stat.st_mtime_ns)
            scenes=json.loads((pc.RAW/seq/'scenes.json').read_text())['scenes']
            with h5py.File(h5,'r') as f:radar=f['radar_data'][:]
            ar,ao=audit_sequence(radar,scenes,split,seq);audits.extend(ar);ao['manifest_observations']=len(rows);audit_overview.append(ao)
            seed=int.from_bytes(hashlib.sha256((seq+str(PLAN['data']['seed'])).encode()).digest()[:8],'little')
            chosen=set(np.random.default_rng(seed).choice(len(rows),min(len(rows),PLAN['data']['diagnostic_rows_per_validation_sequence']),replace=False)) if split=='val' else set()
            history=deque(maxlen=7);previous=None
            for j,row in enumerate(rows):
                key=(int(row['sensor_id']),row['track_id'])
                if key!=previous:history.clear();previous=key
                b,e=scenes[row['frame_key']]['radar_indices'];v=radar[b:e]
                a=v[(v['track_id']==row['track_id'].encode())&np.isin(v['label_id'],[0,1,2,3,7,8])]
                points=np.stack([a['x_cc'],a['y_cc'],a['vr_compensated'],a['rcs']],axis=1).astype(np.float32)
                history.append(points);fused=np.concatenate(list(history));n=len(fused)
                saturated+=int(np.count_nonzero((fused*256<-32768)|(fused*256>32767)))
                q=np.ascontiguousarray(np.clip(np.rint(fused*256),-32768,32767),np.int16)
                raw,legacy,neg=k(q);negative+=neg
                idx=byid[int(row['packed_row'])];mismatches+=int(not np.array_equal(legacy,old[idx]))
                truth=int(np.bincount(a['label_id'].astype(int)).argmax());assert int(ys[idx])==(0 if truth in [7,8] else 1)
                for m,values in zip(MODES,raw):arrays[m][idx]=values
                # Shape groups use high-precision population covariance of identical Q8.8 input.
                cov=np.cov(q[:,:2].astype(float).T,bias=True) if n>1 else np.zeros((2,2))
                ev=np.linalg.eigvalsh(cov);ratio=max(float(ev[0]),0)/max(float(ev[1]),1e-12)
                meta[idx]=dict(packed_row=int(row['packed_row']),sequence=seq,label=int(ys[idx]),n=n,shape_ratio=ratio,
                    shape_group='elongated' if ratio<=.1 else ('compact' if ratio>.5 else 'intermediate'),
                    point_group='1-4' if n<=4 else ('5-16' if n<=16 else ('17-64' if n<=64 else '65-511')),
                    centroid_range=float(np.hypot(q[:,0].mean(),q[:,1].mean())/256))
                if j in chosen:
                    ds=int.from_bytes(hashlib.sha256((seq+str(row['packed_row'])+'perturb').encode()).digest()[:8],'little')
                    order=np.random.default_rng(ds).permutation(n)
                    center=np.mean(q[:,:2].astype(float),axis=0)
                    near=np.argsort(np.sum((q[:,:2]-center)**2,axis=1),kind='stable')
                    coarse=q.copy();coarse[:,:2]=np.clip(np.rint(q[:,:2].astype(float)/4)*4,-32768,32767).astype(np.int16)
                    conditions={'clean':q,'uniform_half':q[np.sort(order[:max(1,(n+1)//2)])],
                        'uniform_quarter':q[np.sort(order[:max(1,(n+3)//4)])],
                        'central_half':q[np.sort(near[:max(1,(n+1)//2)])],'xy_fraction6':coarse}
                    dmeta=meta[idx].copy();dmeta['validation_row']=idx;diagmeta.append(dmeta);diagpoints.append(q);diagoffsets.append(diagoffsets[-1]+n)
                    for condition,p in conditions.items():
                        rr,ll,_=k(p)
                        for m,z in zip(MODES,rr):diagnostics[m][condition].append(z)
                        diagnostics['legacy'][condition].append(ll)
                seen+=1
            del radar
            print(json.dumps(dict(split=split,sequence=seq,rows=seen,wall_seconds=round(time.monotonic()-started,2))),flush=True)
        assert seen==len(ys) and not mismatches and all(m is not None for m in meta)
        for a in arrays.values():a.flush()
        np.save(splitdir/'labels.npy',ys);write_csv(splitdir/'metadata.csv',meta)
        summaries[split]=dict(samples=seen,sequences=len(byseq),legacy_feature_mismatches=mismatches,negative_diagonal_counts=negative.tolist(),input_saturated_elements=saturated)
    exps={m:fit_scale(np.load(out/'train'/(m+'_raw.npy'),mmap_mode='r'),m).tolist() for m in ['proxy_scaled','moment24']}
    exps['moment16']=exps['moment24'];exps['uncentered16']=exps['moment24'];dump(out/'output_scale_exponents.json',exps)
    quant_profiles=[]
    for split in ['train','val']:
        for mode in MODES:
            raw=np.load(out/split/(mode+'_raw.npy'),mmap_mode='r');q=quantize(raw,exps[mode],mode);np.save(out/split/(mode+'.npy'),q)
            quant_profiles.append(dict(split=split,mode=mode,zero_fraction=np.mean(q==0,axis=0).tolist(),at_limit_fraction=np.mean(np.abs(q)==127,axis=0).tolist()))
    diag=out/'diagnostic';diag.mkdir();write_csv(diag/'metadata.csv',diagmeta)
    np.save(diag/'labels.npy',np.asarray([r['label'] for r in diagmeta],np.int64))
    np.save(diag/'points_q8.npy',np.concatenate(diagpoints));np.save(diag/'offsets.npy',np.asarray(diagoffsets,np.int64))
    for m,conditions in diagnostics.items():
        for c,rows in conditions.items():
            a=np.asarray(rows,dtype=np.int8 if m=='legacy' else np.int64)
            np.save(diag/(m+'_'+c+'.npy'),a if m=='legacy' else quantize(a,exps[m],m))
    write_csv(out/'filter_observations.csv',audits);write_csv(out/'filter_overview.csv',audit_overview)
    audit_matches=all(r['eligible_ge3_observations']==r['manifest_observations'] for r in audit_overview)
    # A mismatch is reported separately; legacy-feature identity still gates all model inputs.
    report=dict(status='PASS',splits=summaries,diagnostic_samples=len(diagmeta),filter_eligible_matches_manifest=audit_matches,
        filter_totals={split:{group:sum(r['observations'] for r in audits if r['split']==split and r['points_group']==group) for group in ['1','2','3_or_more']} for split in ['train','val']},
        wall_seconds=time.monotonic()-started,raw_hdf5_metadata=raw_meta,output_quantization_profiles=quant_profiles,
        source_sha256={str(p.relative_to(ROOT)):sha(p) for p in sources},plan_sha256=sha(HERE/'plan.json'))
    dump(out/'summary.json',report);print(json.dumps({k:v for k,v in report.items() if k not in ['source_sha256','raw_hdf5_metadata','output_quantization_profiles']}))

if __name__=='__main__':main()
