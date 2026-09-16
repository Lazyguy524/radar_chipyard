#!/usr/bin/env python3
"""Post-hoc descriptive profile of cached feature arrays; no new models or modes."""
import csv
import hashlib
import json
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
LOG=ROOT/'logs/feature_approximation_pilot_20260916/full'
NAMES=['count','mean_x','mean_y','std_x','std_y','span_x','span_y','range_min','range_max','centroid_range','azimuth_span','eig_major','eig_minor','density','doppler_mean','doppler_std','doppler_min','doppler_max','rcs_mean','rcs_std','rcs_max']


def main():
    a=np.load(LOG/'deployment.npy');b=np.load(LOG/'exact_stats_hardware_quantizer.npy')
    rows=[]
    for i,name in enumerate(NAMES):
        rows.append(dict(slot=i,name=name,current_unique_values=len(np.unique(a[:,i])),
            exact_unique_values=len(np.unique(b[:,i])),current_zero_fraction=float(np.mean(a[:,i]==0)),
            exact_zero_fraction=float(np.mean(b[:,i]==0)),changed_fraction=float(np.mean(a[:,i]!=b[:,i]))))
    with (HERE/'quantized_input_profile.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    result=dict(status='POST_HOC_DESCRIPTIVE_PROFILE',samples=len(a),new_training=False,
        source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [LOG/'deployment.npy',LOG/'exact_stats_hardware_quantizer.npy']},
        observations={r['name']:r for r in rows if r['slot'] in [4,10,11,12]},
        limitations=['Post-hoc follow-up of completed pilot, not predeclared confirmatory evidence.',
            'A mostly-zero feature may be unnecessary for this task; zero fraction alone does not establish classification damage.',
            'Training standardization was applied AFTER this quantization and cannot recover distinctions already lost.',
            'Per-feature scaling/mixed precision are established methods, not a new method by themselves.'])
    (HERE/'quantized_input_profile.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':main()
