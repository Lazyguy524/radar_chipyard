"""Identity and label availability only; no model scoring of possible reserves."""
import csv
import gzip
from collections import Counter,defaultdict
import time
from protection_common import *

def main():
    start=time.monotonic();splits=defaultdict(set)
    with gzip.open(pc.MANIFEST,'rt') as f:
        for r in csv.DictReader(f):splits[r['split']].add(r['sequence_id'])
    catalog=pc.RAW/'sequences.json';allseq=json.loads(catalog.read_text())['sequences'];unused=sorted(set(allseq)-set.union(*splits.values()))
    assert unused==['sequence_150','sequence_53','sequence_54','sequence_55','sequence_59']
    rows=[]
    for seq in unused:
        p=pc.RAW/seq/'radar_data.h5';scene=pc.RAW/seq/'scenes.json'
        row=dict(sequence=seq,official_metadata=allseq[seq],hdf5_present=p.exists(),scenes_present=scene.exists())
        if p.exists():
            with pc.h5py.File(p,'r') as f:r=f['radar_data'][:]
            labels=dict(Counter(map(int,r['label_id'])));valid=np.isin(r['label_id'],[0,1,2,3,7,8])&(r['track_id']!=b'')
            row.update(label_counts=labels,target_track_points=int(valid.sum()),raw_rows=len(r),hdf5_sha256=sha(p),bytes=p.stat().st_size)
        rows.append(row)
    report=dict(status='PASS_METADATA_AUDIT_ONLY',split_sequences={k:sorted(v) for k,v in splits.items()},unused_in_binary_manifest=rows,
        model_scoring_runs=0,confirmation_status='NOT_ESTABLISHED: absent binary-manifest membership is not proof of no prior use; check annotation suitability and other historical pipelines',
        source_sha256={str(pc.MANIFEST.relative_to(ROOT)):sha(pc.MANIFEST),str(catalog):sha(catalog),str(HERE.relative_to(ROOT))+'/audit_reserve.py':sha(HERE/'audit_reserve.py')},wall_seconds=time.monotonic()-start)
    dump(LOG/'reserve_audit.json',report);print(json.dumps(dict(status=report['status'],unused=[{k:r.get(k) for k in ['sequence','target_track_points','label_counts','hdf5_present']} for r in rows]),ensure_ascii=False))
if __name__=='__main__':main()
