"""Python synthetic gate before new real-data training."""
from common import *

def main():
    LOG.mkdir(exist_ok=False)
    torch.manual_seed(20260916);rng=np.random.default_rng(20260916)
    x=rng.integers(-127,128,(1024,21),dtype=np.int16).astype(np.int8)
    mean=x.mean(0);std=x.std(0);net=model().double()
    folded=fold(net,mean,std)
    with torch.no_grad():
        a=net(torch.tensor((x-mean)/std,dtype=torch.float64));b=folded(torch.tensor(x,dtype=torch.float64))
    error=float((a-b).abs().max());assert error<1e-10
    qat=FrozenQAT(folded,torch.tensor(x));bundle=qat.export()
    out=LOG/'synthetic_export';write_export(out,bundle);c=CTrace(out)
    with torch.no_grad():tt=[z.numpy() for z in qat(torch.tensor(x),trace=True)]
    nt=integer_trace(x,bundle);ct=c(x)
    assert all(np.array_equal(a,b) and np.array_equal(a,d) for a,b,d in zip(tt,nt,ct))
    values=np.asarray([sign*(q*65536+r) for sign in [-1,1] for q in [0,1,2,3,127,1024] for r in [0,32767,32768,32769,65535]],dtype=np.int64)
    result=np.empty(len(values),np.int32);c.lib.test_round(values.ctypes.data,len(values),result.ctypes.data)
    assert np.array_equal(result,round_shift(values,1))
    qat.train();loss=F.cross_entropy(qat(torch.tensor(x)),torch.tensor(rng.integers(0,2,len(x))))
    loss.backward();assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in qat.parameters())
    state={k:v.clone() for k,v in qat.state_dict().items()};qat.eval()
    with torch.no_grad():
        one=qat(torch.tensor(x),trace=True)[-1]
        chunks=torch.cat([qat(torch.tensor(x[i:i+17]),trace=True)[-1] for i in range(0,len(x),17)])
    assert torch.equal(one,chunks)
    assert all(torch.equal(state[k],v) for k,v in qat.state_dict().items())
    report=dict(status='PASS',synthetic_samples=len(x),fold_max_error=error,integer_three_way_equal=True,
        signed_rounding_cases=len(values),finite_gradients=True,frozen_batch_invariance=True,
        plan_sha256=sha(HERE/'plan.json'),source_sha256={str(p.relative_to(ROOT)):sha(p) for p in [HERE/'common.py',HERE/'preflight.py']})
    dump(LOG/'preflight.json',report);print(json.dumps(report))

if __name__=='__main__':main()
