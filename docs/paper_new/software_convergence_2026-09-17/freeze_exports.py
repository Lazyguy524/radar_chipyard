"""Complete portable model files using the actual historical export filename."""
import shutil
from sw_common import *

def main():
    rows=[]
    for d in sorted((LOG/'package').glob('*_seed*')):
        contract=json.loads((d/'contract.json').read_text());source=ROOT/contract['source_export']
        # Export helper calls this integer_params.npz, not optional params.npz.
        shutil.copyfile(source/'integer_params.npz',d/'integer_params.npz')
        assert sha(source/'integer_params.npz')==sha(d/'integer_params.npz')
        params=json.loads((d/'params.json').read_text());old=params.pop('input',None)
        params['training_input_contract']=old
        params['input']=dict(feature_flags=contract['feature_flags'],reciprocal_bits=contract['mean_reciprocal_bits'],feature_shifts=contract['feature_shifts'],runtime_normalization=False)
        params['source_export']=contract['source_export'];dump(d/'params.json',params)
        rows.append(dict(directory=d.name,integer_params_sha256=sha(d/'integer_params.npz'),params_header_sha256=sha(d/'params.h'),deployment_contract_sha256=sha(d/'contract.json')))
    assert len(rows)==6;dump(LOG/'package/export_binding.json',dict(status='PASS',models=rows,scope='Portable integer model plus matched frontend; no weight changes'))
if __name__=='__main__':main()
