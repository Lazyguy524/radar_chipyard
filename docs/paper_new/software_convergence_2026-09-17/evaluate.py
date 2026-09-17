"""Frozen 13-condition paired sequence evaluation, gates and precision checks."""
import argparse
from sw_common import *

CONDITIONS=PLAN['evaluation']['conditions']
NEW=[m+'_'+c for m in MODES for c in PLAN['training']['coverage']]
def macro(cm):
    den=cm.sum(-1)+cm.sum(-2);diag=np.diagonal(cm,axis1=-2,axis2=-1)
    return np.divide(2*diag,den,out=np.zeros_like(diag,dtype=float),where=den>0).mean(-1)
def composite(values):
    return (values['clean']+sum(values['uniform_quarter_'+str(i)] for i in range(3))/3+
            values['central_half']+values['sparse_single']+values['sparse_context'])/5
def export_path(tag,seed):
    if tag in ('A','B'):return MECH/('factorial_v2' if tag=='A' else 'augmentation_v2')/('proxy_seed'+str(seed))/'epoch60/export'
    if tag=='C':return PROT/'training'/('clean_guard_seed'+str(seed))/'epoch60/export'
    return LOG/'training'/(tag+'_seed'+str(seed))/'epoch60/export'

class Evaluation:
    def __init__(self,out):
        self.start=time.monotonic();self.out=out;out.mkdir(exist_ok=False)
        self.labels={};self.meta={};self.seq={};self.groups={};self.arrays={};self.pred={};self.metrics={};self.boot={};self.groupstats={}
        self.metricrows=[];self.grouprows=[];self.pairrows=[];self.bootrows=[];self.cases=[]
        # All views retain a common complete-sequence identity and paired draw.
        names=None
        for c in CONDITIONS:
            x,y,meta=validation(c);self.arrays[(c,'proxy',24)]=x;self.labels[c]=y;self.meta[c]=meta
            seq=np.array([r['sequence'] for r in meta]);self.seq[c]=seq
            current=sorted(set(seq))
            if names is None:names=current
            assert current==names
            ids=np.searchsorted(names,seq)
            self.groups[c]=[(a,g,mask,dict(samples=int(mask.sum()),sequences=len(set(seq[mask])),supported=bool(ev.support(y,seq,mask)))) for a,g,mask in allgroups(meta,c)]
            self.seq[c]=ids
        self.names=names
        rng=np.random.default_rng(20260917);draw=rng.integers(len(names),size=(2000,len(names)))
        self.counts=np.array([np.bincount(row,minlength=len(names)) for row in draw])
    def budget(self):
        if time.monotonic()-self.start>PLAN['budgets']['evaluation_seconds']:raise TimeoutError('Evaluation stage budget; retain partial evidence')
    def features(self,c,mode,bits):
        key=(c,mode,bits)
        if key not in self.arrays:self.arrays[key]=validation(c,mode,bits)[0]
        return self.arrays[key]
    def add(self,tag,seed,c,p):
        self.budget();y=self.labels[c];p=p.astype(np.int8);key=(tag,seed,c)
        self.pred[key]=p;np.save(self.out/(tag+'_seed%d_%s_prediction.npy'%(seed,c)),p)
        cm=pc.cm(y,p);m=pc.metrics(cm);self.metrics[key]=m
        self.metricrows.append(dict(tag=tag,seed=seed,condition=c,**m))
        sc=np.bincount(self.seq[c]*4+y*2+p,minlength=len(self.names)*4).reshape(len(self.names),2,2)
        assert np.array_equal(sc.sum(0),cm)
        self.boot[key]=macro(np.einsum('bs,sij->bij',self.counts,sc));groupresult={}
        for axis,g,mask,support in self.groups[c]:
            acc=float(np.mean(p[mask]==y[mask])) if support['samples'] else None
            groupresult[(axis,g)]=acc
            self.grouprows.append(dict(tag=tag,seed=seed,condition=c,axis=axis,group=g,**support,accuracy=acc,
                macro_f1=float(macro(pc.cm(y[mask],p[mask]))) if support['samples'] and len(np.unique(y[mask]))==2 else None))
        self.groupstats[key]=groupresult
    def evaluate(self,tag,seed,bits=24,alias=None):
        model=native_model(export_path(tag,seed));mode='mean' if tag.startswith('mean') else 'proxy';alias=alias or tag
        for c in CONDITIONS:
            if tag in ('A','B'):
                p=old_prediction('factorial' if tag=='A' else 'augmentation',seed,c)
            elif tag=='C':p=np.load(PROT/'evaluation'/('clean_guard_seed%d_%s_prediction.npy'%(seed,c)))
            else:p=model(self.features(c,mode,bits))[-1].argmax(1)
            self.add(alias,seed,c,p)
        print(json.dumps(dict(stage='evaluate',tag=alias,seed=seed,seconds=round(time.monotonic()-self.start,1))),flush=True)
    def score(self,tag,seed,bootstrap=False):
        values={c:self.boot[(tag,seed,c)] if bootstrap else self.metrics[(tag,seed,c)]['macro_f1'] for c in CONDITIONS}
        return composite(values)
    def paired(self,tag,ref):
        for c in CONDITIONS+['composite']:
            point=[];boot=[]
            for seed in SEEDS:
                if c=='composite':delta=self.score(tag,seed)-self.score(ref,seed);bs=self.score(tag,seed,True)-self.score(ref,seed,True)
                else:
                    delta=self.metrics[(tag,seed,c)]['macro_f1']-self.metrics[(ref,seed,c)]['macro_f1'];bs=self.boot[(tag,seed,c)]-self.boot[(ref,seed,c)]
                    p=self.pred[(tag,seed,c)];r=self.pred[(ref,seed,c)];y=self.labels[c]
                    self.pairrows.append(dict(tag=tag,reference=ref,seed=seed,condition=c,delta_macro_f1=delta,
                        new_errors=int(np.sum((r==y)&(p!=y))),repaired_errors=int(np.sum((r!=y)&(p==y)))))
                    # Fixed first identities, not selected for dramatic examples.
                    if seed==7:
                        for kind,mask in [('new_error',(r==y)&(p!=y)),('repair',(r!=y)&(p==y))]:
                            for ix in np.flatnonzero(mask)[:3]:
                                row=self.meta[c][ix];self.cases.append(dict(tag=tag,reference=ref,seed=seed,condition=c,kind=kind,row=int(ix),label=int(y[ix]),prediction=int(p[ix]),reference_prediction=int(r[ix]),metadata=row))
                point.append(float(delta));boot.append(bs)
                self.bootrows.append(dict(tag=tag,reference=ref,condition=c,seed=str(seed),delta=float(delta),low=float(np.quantile(bs,.025)),high=float(np.quantile(bs,.975))))
            bs=np.mean(boot,axis=0)
            self.bootrows.append(dict(tag=tag,reference=ref,condition=c,seed='mean3',delta=float(np.mean(point)),low=float(np.quantile(bs,.025)),high=float(np.quantile(bs,.975))))
    def gate(self,tag):
        failures=[];difficult={};groupfails=[];clean=[]
        for seed in SEEDS:
            d=self.metrics[(tag,seed,'clean')]['macro_f1']-self.metrics[('A',seed,'clean')]['macro_f1'];clean.append(d)
            if d < -.002-1e-12:failures.append('clean_seed'+str(seed))
        for c in ['quarter_mean','central_half','sparse_single','sparse_context']:
            cs=['uniform_quarter_'+str(i) for i in range(3)] if c=='quarter_mean' else [c]
            d=float(np.mean([self.metrics[(tag,s,v)]['macro_f1']-self.metrics[('B',s,v)]['macro_f1'] for s in SEEDS for v in cs]));difficult[c]=d
            if d<-.003-1e-12:failures.append(c)
        for c in CONDITIONS:
            for axis,g,mask,support in self.groups[c]:
                if support['supported']:
                    ds=[self.groupstats[(tag,s,c)][(axis,g)]-self.groupstats[('A',s,c)][(axis,g)] for s in SEEDS]
                    if all(d<0 for d in ds) and np.mean(ds)<-.01-1e-12:groupfails.append(dict(condition=c,axis=axis,group=g,per_seed=ds,mean=float(np.mean(ds)),**support))
        if groupfails:failures.append('supported_group_regression')
        ds=[float(self.score(tag,s)-self.score('B',s)) for s in SEEDS]
        if np.mean(ds)<.001-1e-12 or not all(d>0 for d in ds):failures.append('composite_gain')
        return dict(tag=tag,accepted=not failures,failures=failures,clean_vs_A=clean,difficult_vs_B=difficult,
            composite_per_seed=[float(self.score(tag,s)) for s in SEEDS],composite_vs_B=ds,composite_mean=float(np.mean([self.score(tag,s) for s in SEEDS])),group_failures=groupfails)
    def precision(self,tag,bits):
        alias=tag+'_q'+str(bits);fails=[];worst_f1=0.;worst_group=0.
        for s in SEEDS:
            for c in CONDITIONS:
                d=self.metrics[(alias,s,c)]['macro_f1']-self.metrics[(tag,s,c)]['macro_f1'];worst_f1=min(worst_f1,d)
                if d<-.001-1e-12:fails.append(dict(seed=s,condition=c,axis='global',group='all',delta=d))
                for axis,g,mask,support in self.groups[c]:
                    if support['supported']:
                        d=self.groupstats[(alias,s,c)][(axis,g)]-self.groupstats[(tag,s,c)][(axis,g)];worst_group=min(worst_group,d)
                        if d<-.005-1e-12:fails.append(dict(seed=s,condition=c,axis=axis,group=g,delta=d))
        return dict(tag=tag,bits=bits,accepted=not fails,failures=fails,worst_f1_delta=worst_f1,worst_group_accuracy_delta=worst_group)
    def save(self,summary):
        dump(self.out/'metrics.json',self.metricrows);writecsv(self.out/'conditional_groups.csv',self.grouprows)
        if self.pairrows:writecsv(self.out/'paired_errors.csv',self.pairrows);writecsv(self.out/'paired_sequence_intervals.csv',self.bootrows)
        dump(self.out/'error_cases.json',self.cases)
        summary.update(status='PASS',wall_seconds=time.monotonic()-self.start,sequence_names=self.names,bootstrap_repetitions=2000,
            bootstrap_scope='Paired full-sequence draws shared across conditions/models; same three trained seeds held fixed, reported individually and mean; exploratory reused development set, no independent significance claim',output_bytes=size_guard())
        dump(self.out/'summary.json',summary)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--baseline',action='store_true');a=parser.parse_args()
    assert json.loads((LOG/'preparation.json').read_text())['status']=='PASS'
    if not a.baseline:assert json.loads((LOG/'training/summary.json').read_text())['status']=='PASS'
    e=Evaluation(LOG/('baseline_review' if a.baseline else 'evaluation'))
    for tag in ['A','B','C']+(NEW if not a.baseline else []):
        for seed in SEEDS:e.evaluate(tag,seed)
    for tag in ['B','C']+(NEW if not a.baseline else []):
        for ref in (['A'] if tag=='B' else ['A','B']):e.paired(tag,ref)
    if a.baseline:e.save(dict(stage='baseline_review',scope='A/B/C errors before new training; factual numerical reconstruction PASS; distribution coverage is a hypothesis'));return
    # Paired factorial contrasts isolate representation within coverage and coverage within representation.
    for tag,ref in [('proxy_natural','proxy_synthetic'),('mean_natural','mean_synthetic'),('mean_synthetic','proxy_synthetic'),('mean_natural','proxy_natural')]:e.paired(tag,ref)
    gates=[e.gate(t) for t in NEW];precision=[];selected_bits={}
    for tag in [t for t in NEW if t.startswith('mean')]:
        for bits in (12,16):
            for seed in SEEDS:e.evaluate(tag,seed,bits,tag+'_q'+str(bits))
            precision.append(e.precision(tag,bits));e.paired(tag+'_q'+str(bits),tag)
        passing=[p['bits'] for p in precision if p['tag']==tag and p['accepted']];selected_bits[tag]=min(passing) if passing else 24
    finalgates=[]
    for tag in NEW:
        bits=selected_bits.get(tag,24);alias=tag if bits==24 else tag+'_q'+str(bits);g=e.gate(alias);g.update(model_tag=tag,mean_bits=bits);finalgates.append(g)
        if alias!=tag:
            e.paired(alias,'A');e.paired(alias,'B')
    passing=[g for g in finalgates if g['accepted']]
    if passing:
        high=max(g['composite_mean'] for g in passing);near=[g for g in passing if g['composite_mean']>=high-.001-1e-12]
        near.sort(key=lambda g:(not g['model_tag'].startswith('proxy'),-g['composite_mean'],g['model_tag']))
        chosen=near[0];decision=dict(main=chosen['model_tag'],mean_bits=chosen['mean_bits'],evaluation_tag=chosen['tag'],alternative='B',reason='Passed every frozen gate; simplicity tie rule among candidates within 0.1 percentage points of highest')
    else:decision=dict(main='A',mean_bits=24,evaluation_tag='A',alternative='B',reason='No new candidate passed every frozen gate; retain main A and difficult-condition alternative B')
    e.save(dict(stage='final_evaluation',q24_gates=gates,precision=precision,selected_mean_bits=selected_bits,final_gates=finalgates,decision=decision,plan_sha256=sha(HERE/'plan.json')))
    print(json.dumps(decision),flush=True)
if __name__=='__main__':main()
