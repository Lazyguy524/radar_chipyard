"""Build only the current hardware feature mirror for the full training split."""
import csv
import gzip
import time
from collections import deque
from common import *
import h5py

def main():
    pre=json.loads((LOG/'preflight.json').read_text());assert pre['status']=='PASS' and pre['plan_sha256']==sha(HERE/'plan.json')
    out=LOG/'train';out.mkdir(exist_ok=False);started=time.monotonic()
    native=pc.Native(LOG/'native')
    fm=pc.module('int8_training_reference',pc.REC/'src/radar_cluster_rocc/features.py')
    byseq={}
    with gzip.open(pc.MANIFEST,'rt') as f:
        for r in csv.DictReader(f):
            if r['split']=='train':byseq.setdefault(r['sequence_id'],[]).append(r)
    expected=np.load(pc.PACKED/'train_feat.npy',mmap_mode='r');labels=np.load(pc.PACKED/'train_label.npy',mmap_mode='r')
    arrays=[];ys=[];metadata=[];raw={};mismatch=dict(software_features=0,label=0,count=0,pilot_subset=0)
    previous={}
    with gzip.open(PILOT/'train_subset/metadata.csv.gz','rt') as f:
        for j,r in enumerate(csv.DictReader(f)):previous[int(r['packed_row'])]=j
    old=np.load(PILOT/'train_subset/deployment.npy');saturation=0
    for seq,rows in byseq.items():
        if time.monotonic()-started>PLAN['budgets']['prepare_timeout_seconds']:raise TimeoutError('Preparation budget')
        scenes=json.loads((pc.RAW/seq/'scenes.json').read_text())['scenes']
        h5=pc.RAW/seq/'radar_data.h5';stat=h5.stat();raw[seq]=dict(bytes=stat.st_size,mtime_ns=stat.st_mtime_ns)
        with h5py.File(h5,'r') as f:radar=f['radar_data'][:]
        history=deque(maxlen=7);key_before=None
        for row in rows:
            sensor=int(row['sensor_id']);key=(sensor,row['track_id'])
            if key!=key_before:history.clear();key_before=key
            scene=scenes[row['frame_key']];assert int(scene['sensor_id'])==sensor
            begin,end=scene['radar_indices'];v=radar[begin:end]
            selected=v[(v['track_id']==row['track_id'].encode())&np.isin(v['label_id'],[0,1,2,3,7,8])]
            assert len(selected)
            points=np.stack([selected['x_cc'],selected['y_cc'],selected['vr_compensated'],selected['rcs']],axis=1).astype(np.float32)
            history.append(points);fused=np.concatenate(list(history),axis=0);n=len(fused);assert 0<n<=511
            idx=int(row['packed_row']);y=int(labels[idx])
            truth=int(np.bincount(selected['label_id'].astype(int)).argmax())
            mismatch['label']+=int(y!=(0 if truth in [7,8] else 1));mismatch['count']+=int(n!=expected[idx,0])
            exact=fm.extract_cluster_features(fused,'rcs21')
            mismatch['software_features']+=int(not np.allclose(exact,expected[idx],rtol=1e-5,atol=1e-5))
            saturation+=int(np.count_nonzero((fused*256<-32768)|(fused*256>32767)))
            qp=np.ascontiguousarray(np.clip(np.rint(fused*256),-32768,32767),dtype=np.int16)
            feat=np.empty(21,np.int8);unused=np.empty(21,np.int8)
            native.lib.features_pair(qp.ctypes.data,n,feat.ctypes.data,unused.ctypes.data)
            if idx in previous:mismatch['pilot_subset']+=int(not np.array_equal(feat,old[previous[idx]]))
            arrays.append(feat);ys.append(y);metadata.append(dict(packed_row=idx,sequence_id=seq,track_id=row['track_id'],sensor_id=sensor))
        del radar
        print(json.dumps(dict(sequence=seq,samples=len(ys),wall_seconds=round(time.monotonic()-started,2))),flush=True)
    assert not any(mismatch.values()),mismatch
    assert len(ys)==PLAN['data']['train_rows'] and len(byseq)==PLAN['data']['train_sequences']
    assert len({r['packed_row'] for r in metadata})==len(ys)
    with gzip.open(PILOT/'full/metadata.csv.gz','rt') as f:val_seq={r['sequence_id'] for r in csv.DictReader(f)}
    assert not set(byseq)&val_seq
    np.save(out/'features.npy',np.asarray(arrays,np.int8));np.save(out/'labels.npy',np.asarray(ys,np.int64))
    with gzip.open(out/'metadata.csv.gz','wt',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(metadata[0]));w.writeheader();w.writerows(metadata)
    sources=[HERE/'plan.json',HERE/'prepare.py',HERE/'common.py',pc.HERE/'pilot_common.py',pc.MANIFEST,
        pc.PACKED/'train_feat.npy',pc.PACKED/'train_label.npy',pc.REC/'src/radar_cluster_rocc/features.py',
        PILOT/'full/deployment.npy',PILOT/'full/labels.npy',PILOT/'full/metadata.csv.gz']
    summary=dict(status='PASS',samples=len(ys),sequences=len(byseq),checks=mismatch,pilot_subset_checked=len(previous),
        input_saturated_elements=saturation,train_validation_sequence_overlap=0,wall_seconds=time.monotonic()-started,
        raw_hdf5_metadata=raw,source_sha256={str(p.relative_to(ROOT)):sha(p) for p in sources}|native.inputs)
    dump(out/'summary.json',summary);print(json.dumps({k:v for k,v in summary.items() if k not in ['raw_hdf5_metadata','source_sha256']}))

if __name__=='__main__':main()
