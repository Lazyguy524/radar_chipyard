"""Calibrate on train, prove integer roots, reconstruct all fixed input views."""
import bisect
import csv
import gzip
import math
import shutil
import time
import h5py
from common_encoding import *
sys.path.insert(0,str(ROOT/'docs/paper_new/mechanism_convergence_2026-09-16'))
views=base.module('encoding_prepare_views',ROOT/'docs/paper_new/mechanism_convergence_2026-09-16/prepare_views.py')

def read_rows(p):
    with Path(p).open() as f:return list(csv.DictReader(f))
def main():
    started=time.monotonic();LOG.mkdir(exist_ok=False);native=Native(True);rng=np.random.default_rng(20260916)
    synthetic=rng.integers(-(2**40),2**40,size=(4096,21),dtype=np.int64);synthetic[:,[3,4]]=np.abs(synthetic[:,[3,4]])
    synthetic[:,11]=np.maximum(synthetic[:,3],synthetic[:,4]);synthetic[:,12]=np.minimum(synthetic[:,3],synthetic[:,4])
    expected=transform(synthetic,'root');got=native.raw_root(synthetic);assert np.array_equal(expected,got)
    for j in SHAPES:
        for x,r in zip(synthetic[:,j],expected[:,j]):
            a=abs(int(x));q=math.isqrt(a);q+=int(a-q*q>q);assert int(r)==(-q if x<0 else q)
    data=LOG/'data';data.mkdir();exps={};stats=[];source=[HERE/'plan.json',HERE/'prepare.py',HERE/'common_encoding.py',HERE/'encoding.c',PREV/'data/output_scale_exponents.json']
    old_ex=np.array(json.loads((PREV/'data/output_scale_exponents.json').read_text())['moment24'])
    train=np.load(PREV/'data/train/moment24_raw.npy');source.append(PREV/'data/train/moment24_raw.npy')
    for mode in MODES:
        raw=transform(train,mode);ex=old_ex.copy();percentile=99 if mode=='linear_fine' else 99.99
        threshold=np.percentile(np.abs(raw[:,SHAPES].astype(float))/np.exp2(fractions(mode)[SHAPES]),percentile,axis=0)/127
        ex[SHAPES]=np.ceil(np.log2(np.maximum(threshold,2**-16))).astype(int);exps[mode]=ex.tolist()
    dump(data/'scales.json',dict(modes=MODES,exponents=exps,shifts=[(np.array(exps[m])+fractions(m)).tolist() for m in MODES]))
    native=Native(False)
    for split in ['train','val']:
        out=data/split;out.mkdir();path=PREV/'data'/split/'moment24_raw.npy';a=np.load(path);source.append(path)
        root=transform(a,'root');assert np.array_equal(root,native.raw_root(a))
        for mode in MODES:
            raw=root if mode=='root' else a;q=quantize(raw,mode,exps[mode]);np.save(out/(mode+'.npy'),q)
            shift=np.array(exps[mode])+fractions(mode)
            before=np.rint(raw.astype(float)/np.exp2(shift))
            stats.append(dict(split=split,mode=mode,zero_fraction=(q==0).mean(0).tolist(),nonzero_mapped_zero=((raw!=0)&(q==0)).mean(0).tolist(),
                actual_clipped_fraction=(np.abs(before)>127).mean(0).tolist(),note='Clipping counts compare unbounded rounded integer to 127; boundary values alone are not called clipping.'))
        label=MECH/'data'/split/'labels.npy';source.append(label);shutil.copyfile(label,out/'labels.npy')
    rawout=LOG/'raw';rawout.mkdir();conditions=PLAN['diagnostics']['conditions'];n=PLAN['data']['validation_rows'];arrays={}
    for mode in MODES:
        d=rawout/'val'/mode;d.mkdir(parents=True)
        for c in conditions:
            if c!='clean':arrays[(mode,c)]=np.lib.format.open_memmap(d/(c+'.npy'),mode='w+',dtype=np.int8,shape=(n,21))
    precision={}
    for mb,vb in PLAN['diagnostics']['precision']:
        for c in PLAN['diagnostics']['primary']:
            d=rawout/'precision'/('m%d_v%d'%(mb,vb))/c;d.mkdir(parents=True)
            for mode in MODES:precision[(mb,vb,c,mode)]=np.lib.format.open_memmap(d/(mode+'.npy'),mode='w+',dtype=np.int8,shape=(n,21))
    points=np.load(MECH/'raw/val/points_q8.npy',mmap_mode='r');offset=np.load(MECH/'raw/val/offsets.npy');meta=read_rows(MECH/'raw/val/metadata.csv')
    clean={m:np.load(data/'val'/(m+'.npy')) for m in MODES};seen=0
    def budget():
        if time.monotonic()-started>PLAN['budgets']['prepare_seconds']:raise TimeoutError('Encoding preparation budget')
    for i,row in enumerate(meta):
        if i%1024==0:budget()
        q=np.ascontiguousarray(points[offset[i]:offset[i+1]],np.int16);z=native(q)
        for k,m in enumerate(MODES):assert np.array_equal(z[k],clean[m][i])
        vv=views.sample_views(q,row['sequence'],row['packed_row'],True)
        # Fusion appends the current observation last, preserving its original point order.
        vv['kept_single']=q[-int(row['raw_points']):]
        for c,p in vv.items():
            z=native(p)
            for k,m in enumerate(MODES):arrays[(m,c)][i]=z[k]
        for c in PLAN['diagnostics']['primary']:
            p=q if c=='clean' else vv[c]
            for mb,vb in PLAN['diagnostics']['precision']:
                z=native(p,mb,vb)
                for k,m in enumerate(MODES):precision[(mb,vb,c,m)][i]=z[k]
        seen+=1
        if seen%10000==0:print(json.dumps(dict(validation_rows=seen,seconds=round(time.monotonic()-started,2))),flush=True)
    for a in arrays.values():a.flush()
    for a in precision.values():a.flush()
    with gzip.open(pc.MANIFEST,'rt') as f:manifest=[r for r in csv.DictReader(f) if r['split']=='val']
    kept={}
    for r in manifest:kept.setdefault((r['sequence_id'],int(r['sensor_id']),r['track_id']),[]).append(int(r['frame_key']))
    for v in kept.values():v.sort()
    smeta=read_rows(MECH/'raw/sparse_context/metadata.csv');sparse={};byseq={}
    for i,r in enumerate(smeta):byseq.setdefault(r['sequence'],[]).append((i,r))
    for view in PLAN['diagnostics']['sparse_views']:
        d=rawout/view;d.mkdir()
        for mode in MODES:sparse[(view,mode)]=np.lib.format.open_memmap(d/(mode+'.npy'),mode='w+',dtype=np.int8,shape=(len(smeta),21))
        for name in ['metadata.csv','labels.npy']:shutil.copyfile(MECH/'raw'/view/name,d/name)
    h5meta=json.loads((MECH/'raw/val_summary.json').read_text())['raw_hdf5_metadata'];hashes={r['sequence']:r['sha256'] for r in h5meta}
    for seq,items in byseq.items():
        budget();path=pc.RAW/seq/'radar_data.h5';assert sha(path)==hashes[seq]
        scenes=json.loads((pc.RAW/seq/'scenes.json').read_text())['scenes']
        with h5py.File(path,'r') as f:radar=f['radar_data'][:]
        cache={}
        def observation(frame,track):
            key=(frame,track)
            if key not in cache:
                b,e=scenes[str(frame)]['radar_indices'];a=radar[b:e];a=a[(a['track_id']==track.encode())&np.isin(a['label_id'],[0,1,2,3,7,8])]
                cache[key]=np.stack([a['x_cc'],a['y_cc'],a['vr_compensated'],a['rcs']],axis=1).astype(np.float32)
            return cache[key]
        for i,r in items:
            frame=int(r['frame']);track=r['track'];frames=kept.get((seq,int(r['sensor']),track),[]);at=bisect.bisect_left(frames,frame);prior=frames[max(0,at-6):at]
            current=observation(frame,track);assert len(current)==int(r['raw_points']) and len(prior)==int(r['retained_history_used'])
            context=views.q8(np.concatenate([observation(t,track) for t in prior]+[current]));single=views.q8(current);assert len(context)==int(r['n'])
            for view,p in [('sparse_single',single),('sparse_context',context)]:
                z=native(p)
                for k,m in enumerate(MODES):sparse[(view,m)][i]=z[k]
        del radar
    for a in sparse.values():a.flush()
    source.extend([MECH/'raw/val_summary.json',MECH/'raw/val/metadata.csv',MECH/'raw/val/points_q8.npy',MECH/'raw/val/offsets.npy'])
    report=dict(status='PASS',python_c_integer_root_rows=4096,full_train_validation_root_rows=438230,complete_primary_frontend_rows=80450,natural_rejected_rows=len(smeta),
        output_profiles=stats,wall_seconds=time.monotonic()-started,source_sha256={str(p.relative_to(ROOT)):sha(p) for p in source},plan_sha256=sha(HERE/'plan.json'))
    dump(LOG/'preflight.json',report);print(json.dumps(dict(status='PASS',seconds=report['wall_seconds'],natural_rejected_rows=len(smeta))),flush=True)

if __name__=='__main__':main()
