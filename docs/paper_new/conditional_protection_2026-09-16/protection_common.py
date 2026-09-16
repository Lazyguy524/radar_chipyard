"""Frozen protection study. No changes to prior experiment modules or outputs."""
import importlib.util
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
spec=importlib.util.spec_from_file_location('protection_mechanism',ROOT/'docs/paper_new/mechanism_convergence_2026-09-16/common.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
# Imported evaluation helpers must reuse the initialized common/Torch module.
sys.modules['common']=base
qc=base.qc;pc=base.pc;np=base.np;torch=qc.torch;F=qc.F
json=base.json;hashlib=base.hashlib;ctypes=base.ctypes;subprocess=base.subprocess
sha=base.sha;dump=base.dump
LOG=ROOT/'logs/conditional_protection_20260916';MECH=base.LOG
PLAN=json.loads((HERE/'plan.json').read_text())
def native_model(path):
    obj=qc.CTrace.__new__(qc.CTrace);obj.lib=ctypes.CDLL(str(path/'inference_trace.so'))
    obj.lib.trace_batch.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p];return obj
def buffer_hash(net):
    return hashlib.sha256(b''.join(v.numpy().tobytes() for _,v in net.named_buffers())).hexdigest()
def prediction(net,x,integer=False):
    values=[];net.eval()
    with torch.inference_mode():
        for begin in range(0,len(x),4096):
            z=x[begin:begin+4096];values.append((net(z,trace=True)[-1] if integer else net(z)).numpy())
    return np.concatenate(values)
def objective(logits,labels,class_weights,teacher_logits,view,group,q,method):
    weights=class_weights[labels].to(logits.dtype)
    ce=F.cross_entropy(logits,labels,reduction='none');weighted=ce*weights
    ordinary=weighted.sum()/weights.sum()
    group_num=torch.zeros(18,dtype=logits.dtype).scatter_add_(0,group,weighted)
    group_den=torch.zeros(18,dtype=logits.dtype).scatter_add_(0,group,weights)
    present=group_den>0;group_ce=group_num/group_den.clamp_min(1e-30)
    task=ordinary
    if method=='group_guard':
        qq=q.to(logits.dtype);robust=(qq[present]*group_ce[present]).sum()/qq[present].sum()
        task=.5*ordinary+.5*robust
    teacher=teacher_logits.to(logits.dtype);correct=teacher.argmax(1)==labels
    mask=(view==0)&correct
    tp=F.softmax(teacher/2,dim=1)
    kl=(tp*(F.log_softmax(teacher/2,dim=1)-F.log_softmax(logits/2,dim=1))).sum(1)*4
    guard=(weights*mask*kl).sum()/weights.sum()
    return task+guard,dict(ordinary=ordinary,guard=guard,group_num=group_num,group_den=group_den)
