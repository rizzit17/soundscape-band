"""Additional output-specificity audit and seed-cluster acoustic intervals.

Run after final_simulation_study.py. This adds a single-motor DEDA ablation
without changing thresholds, primary comparisons, seeds, or policy code.
"""
from concurrent.futures import ProcessPoolExecutor
import csv, dataclasses, gzip, hashlib, json
from pathlib import Path
import numpy as np
from final_simulation_study import ROOT, OUT, BASE, SEEDS, BOOT, outcomes, summarize
from deda.synth import SynthParams, generate
from deda.policy import DEDA, run

def one(seed):
 w,e,T=generate(SynthParams(duration_s=1200),seed)
 m,rows=outcomes(run(DEDA(dataclasses.replace(BASE,beta_min=0)),w),e,T,seed,'Main','Single motor DEDA')
 return seed,m,rows

def main():
 path=OUT/'study_results.json';r=json.loads(path.read_text())
 rows=r['per_stream']['Main'];lookup={x['seed']:x for x in rows}
 # Rewrite rather than append, so repeating this supplement is idempotent.
 with gzip.open(OUT/'event_outcomes.csv.gz','rt',encoding='utf-8',newline='') as f:
  records=[x for x in csv.DictReader(f) if x['policy']!='Single motor DEDA'];fields=list(records[0])
 with ProcessPoolExecutor(max_workers=4) as pool:
  for i,(seed,m,events) in enumerate(pool.map(one,SEEDS),1):
   lookup[seed]['metrics']['Single motor DEDA']=m;records.extend(events)
   if i%25==0:print('Single motor audit',i,'/ 100',flush=True)
 with gzip.open(OUT/'event_outcomes.csv.gz','wt',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(records)
 r['summary']['Main'],_=summarize(rows,20261027)
 r['source_sha256']['python/supplement_simulation_study.py']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
 r['acoustic_cluster_intervals']=[];r['acoustic_paired']=[]
 with (OUT/'acoustic_trials.csv').open(encoding='utf-8',newline='') as f:ac=list(csv.DictReader(f))
 rng=np.random.default_rng(20261029);seeds=list(range(6001,6051));idx=rng.integers(0,50,(BOOT,50))
 for condition in dict.fromkeys(x['condition'] for x in ac):
  vectors={}
  for af in (1.,.25):
   subset=[x for x in ac if x['condition']==condition and float(x['bins'])==af]
   metrics={}
   for key,col,fn in [('wrong_quadrant_pct','wrong_quadrant',lambda x:100*(x=='True')),('mae_deg','angular_error',float),('gate_coverage_pct','gate_valid',lambda x:100*(x=='True'))]:
    v=np.array([np.mean([fn(x[col]) for x in subset if int(x['seed'])==seed]) for seed in seeds]);vectors[(af,key)]=v
    b=v[idx].mean(axis=1);metrics[key]=dict(mean=float(v.mean()),ci95=np.percentile(b,[2.5,97.5]).tolist())
   r['acoustic_cluster_intervals'].append(dict(condition=condition,bins=af,n_scenes=len(subset),n_seed_clusters=50,metrics=metrics))
  pair={}
  for key in ('wrong_quadrant_pct','mae_deg'):
   d=vectors[(.25,key)]-vectors[(1.,key)];pair[key]=dict(mean_difference=float(d.mean()),ci95=np.percentile(d[idx].mean(axis=1),[2.5,97.5]).tolist())
  r['acoustic_paired'].append(dict(condition=condition,contrast='strongest 25% minus all bins',metrics=pair))
 path.write_text(json.dumps(r,indent=2,allow_nan=False),encoding='utf-8')
 files=[OUT/'event_outcomes.csv.gz',OUT/'acoustic_trials.csv',path]
 (OUT/'SHA256SUMS.txt').write_text('\n'.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name for p in files)+'\n')
 print('Supplement saved. Event-policy outcome rows',len(records))

if __name__=='__main__':main()
