"""Expanded, reproducible SYNTHETIC evaluation; no audio recordings or hardware.

Run from the project root: python python/final_simulation_study.py --workers 4
All settings are fixed before new test seeds. No data-driven threshold search.
Exports event outcomes and per-stream metrics; regenerate exact score/direction
streams with --export-stream SEED. The core policy and generator are unchanged.
"""
from __future__ import annotations
import argparse, csv, dataclasses, gzip, hashlib, json, math, os, platform, sys, time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from deda.synth import SynthParams, generate
from deda.policy import Config, DEDA, FixedThreshold, Window, DirObs, run, dir_valid, circ_dist, quadrant_of
from deda.metrics import evaluate
from deda.doa import triangle_positions, simulate_array, fractional_delay, estimate_direction

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/final_simulation_study'
BASE=Config(h_hi=(1.25,1.45,1.65,1.25),h_lo=(-.15,.05,.25,-.15),h_urgent=(2.25,2.25,2.45,2.25))
SEEDS=list(range(3001,3101))
STRESS_SEEDS=list(range(4001,4031))
BOOT=20000

class Fallback:
 def __init__(self):self.base=FixedThreshold(.7,True)
 def step(self,w):return self.base.step(Window(w.t_ms,w.probs,w.dir if dir_valid(w.dir,BASE) else None))
class Gate:
 def __init__(self):self.base=FixedThreshold(.7,True)
 def step(self,w):return self.base.step(w) if dir_valid(w.dir,BASE) else self.base.sup.step(w,updates_enabled=False)
def policies(full=True):
 d={'A':FixedThreshold(.7,False),'B':FixedThreshold(.7,True),'G':Gate(),'F':Fallback(),'DEDA':DEDA(BASE)}
 if full:
  for name,kw in [('No reliability',dict(use_dir_reliability=False)),('No closure',dict(closure_max=math.inf)),('No norm',dict(norm_lo=0,norm_hi=math.inf)),('No coherence',dict(rho_min=0,rho_strong=0)),('No sequential',dict(sequential=False)),('No direction wait',dict(wait_for_dir=False)),('No fallback',dict(fallback_nondir=False))]:d[name]=DEDA(dataclasses.replace(BASE,**kw))
 return d

def outcomes(alerts,events,T,seed,condition,policy):
 first=[];rows=[]
 for i,e in enumerate(events):
  a=next((a for a in alerts if a.kind!='UPDATE' and e.onset_ms<=a.t_ms<=e.offset_ms+500),None)
  first.append(a);lat=a.t_ms-e.onset_ms if a else None
  rows.append(dict(condition=condition,seed=seed,policy=policy,event_id=i,onset_ms=e.onset_ms,offset_ms=e.offset_ms,true_class=e.cls,true_angle=e.theta,detected=a is not None,alert_ms=a.t_ms if a else None,alert_class=a.cls if a else None,kind=a.kind if a else None,motors=a.motors if a else None,estimated_angle=a.theta if a else None,latency_ms=lat,late=a is not None and lat>300,wrong_direction=bool(a and a.kind=='DIR' and not a.motors & (1<<quadrant_of(e.theta))),correct_class=bool(a and a.cls==e.cls),evidence_k=a.k if a else None))
 angular=[circ_dist(a.theta,e.theta) for a,e in zip(first,events) if a and a.kind=='DIR' and a.theta is not None]
 m=evaluate(alerts,events,T)
 m.update(angular_mae=float(np.mean(angular)) if angular else None,
 correct_class_detection=sum(a is not None and a.cls==e.cls for a,e in zip(first,events))/len(events),
 timely_correct_class=sum(a is not None and a.cls==e.cls and a.t_ms-e.onset_ms<=300 for a,e in zip(first,events))/len(events),
 directional_coverage=sum(a is not None and a.kind=='DIR' for a in first)/len(events),
 notifications_per_total_hour=sum(a.kind!='UPDATE' for a in alerts)/(T/3.6e6),
 latency_p99_ms=float(np.percentile([r['latency_ms'] for r in rows if r['detected']],99)) if any(first) else None,
 latency_max_ms=max((r['latency_ms'] for r in rows if r['detected']),default=None))
 if policy=='DEDA':
  late=[r for r in rows if r['late']]
  m['late_events']=len(late)
  m['late_episode_open_after_deadline']=sum(r['latency_ms']-r['evidence_k']*64>300 for r in late)
  m['late_with_episode_wait']=sum(r['evidence_k']>0 for r in late)
 return m,rows

STRESS={'Check sensitivity 0%':dict(p_flag_bad=0.),'Check sensitivity 35%':dict(p_flag_bad=.35),'Check sensitivity 100%':dict(p_flag_bad=1.),'Short bursts':dict(ev_dur_s=(.064,.25)),'Correlated class scores':dict(noise_corr=.9),'Coherent 180 degree error':{},'Direction dropout 20%':dict(p_missing_dir=.2)}
def one(task):
 condition,seed=task;sp=SynthParams(duration_s=1200,**STRESS.get(condition,{}))
 w,e,T=generate(sp,seed)
 if condition=='Coherent 180 degree error':
  j=0;altered=[]
  for win in w:
   while j<len(e) and win.t_ms>e[j].offset_ms:j+=1
   obs=win.dir
   if j<len(e) and e[j].onset_ms<=win.t_ms<=e[j].offset_ms:obs=DirObs((e[j].theta+180)%360,0.,1.,.9)
   altered.append(Window(win.t_ms,win.probs,obs))
  w=altered
 selected=policies(condition=='Main') if condition in ('Main',*STRESS) else {f'D={d}':DEDA(dataclasses.replace(BASE,deadline_ms=d)) for d in (150,300,500)}
 result={};events=[]
 for name,p in selected.items():
  a=run(p,w);m,rows=outcomes(a,e,T,seed,condition,name)
  if condition=='Deadline sensitivity':m['miss_or_late_at_target']=evaluate(a,e,T,deadline_ms=int(name[2:]))['miss_or_late_rate']
  result[name]=m
  if condition=='Main':events.extend(rows)
 return dict(condition=condition,seed=seed,n_events=len(e),metrics=result,event_rows=events)

KEYS=['wrong_dir_per_event','wrong_dir_rate','miss_rate','miss_or_late_rate','false_alerts_per_hour','nondir_fraction','lat_p50_ms','lat_p95_ms','angular_mae','correct_class_detection','timely_correct_class','directional_coverage','notifications_per_total_hour','latency_p99_ms','latency_max_ms','miss_or_late_at_target']
def summarize(rows,seed):
 rng=np.random.default_rng(seed);idx=rng.integers(0,len(rows),(BOOT,len(rows)));s={}
 for name in rows[0]['metrics']:
  s[name]={}
  for k in KEYS:
   if k not in rows[0]['metrics'][name]:continue
   v=np.array([r['metrics'][name].get(k) for r in rows],dtype=float)
   if np.isnan(v).all():continue
   b=np.nanmean(v[idx],axis=1);s[name][k]=dict(mean=float(np.nanmean(v)),ci95=np.percentile(b,[2.5,97.5]).tolist(),valid_streams=int(np.isfinite(v).sum()))
 return s,idx
def paired(rows,idx):
 rng=np.random.default_rng(20261028);out={};allp=[]
 for name in ('B','G','F','No direction wait'):
  out[name]={}
  for key in ('wrong_dir_per_event','miss_or_late_rate','false_alerts_per_hour','nondir_fraction'):
   d=np.array([r['metrics']['DEDA'][key]-r['metrics'][name][key] for r in rows]);b=d[idx].mean(axis=1)
   signs=rng.choice(np.array([-1,1],dtype=np.int8),size=(100000,len(rows)))
   pv=float((1+np.count_nonzero(np.abs((signs*d).mean(axis=1))>=abs(d.mean())-1e-12))/100001)
   entry=dict(mean_difference=float(d.mean()),ci95=np.percentile(b,[2.5,97.5]).tolist(),signflip_p=pv);out[name][key]=entry;allp.append(entry)
 running=0
 for rank,entry in enumerate(sorted(allp,key=lambda e:e['signflip_p'])):
  running=max(running,min(1,(len(allp)-rank)*entry['signflip_p']));entry['holm_p']=running
 return out

def acoustic(task):
 condition,side,snr,seed,sound=task;fs=16000;n=1024;rng=np.random.default_rng(seed)
 theta=float((seed%4)*90+rng.uniform(-20,20))%360
 t=np.arange(n)/fs;src=rng.normal(size=n) if sound=='broadband' else sum(np.sin(2*np.pi*420*h*t+rng.uniform(0,2*np.pi))/h for h in range(1,12))
 src/=max(float(np.sqrt(np.mean(src**2))),1e-12);pos=triangle_positions(side)
 kw=dict(mic_offsets=(0.,0.,3.) if condition=='Clock offset' else (0.,0.,0.))
 x=simulate_array(src,theta,pos,fs,200,rng,**kw)
 if condition=='Competing source':x+=simulate_array(rng.normal(size=n),(theta+135)%360,pos,fs,200,rng)
 if condition=='Reflection surrogate':x+=.7*simulate_array(np.r_[np.zeros(192),src[:-192]],(theta+120)%360,pos,fs,200,rng)
 if condition=='Gain mismatch':x*=np.array([1.,.5,.25])[:,None]
 if condition=='Moving surrogate':
  centres=np.linspace(0,n-1,5);weights=np.maximum(0,1-np.abs(np.arange(n)[None,:]-centres[:,None])/(n/4));weights/=weights.sum(axis=0)
  x=sum(weights[j]*simulate_array(src,(theta+off)%360,pos,fs,200,rng) for j,off in enumerate((-30,-15,0,15,30)))
 noise=rng.normal(size=x.shape)
 if condition=='Correlated microphone noise':noise=np.sqrt(.8)*rng.normal(size=n)[None,:]+np.sqrt(.2)*noise
 x+=10**(-snr/20)*noise
 result=[]
 for af in (1.,.25):
  d,_=estimate_direction(x,fs,pos,active_frac=af)
  valid=dir_valid(d,BASE);wrong=quadrant_of(d.theta_deg)!=quadrant_of(theta)
  result.append(dict(condition=condition,side_mm=side*1000,snr_db=snr,seed=seed,sound=sound,angle=theta,bins=af,estimated_angle=d.theta_deg,wrong_quadrant=wrong,angular_error=circ_dist(d.theta_deg,theta),gate_valid=valid,closure=d.closure,norm=d.norm,coherence=d.coherence))
 return result

def export_stream(seed):
 w,e,T=generate(SynthParams(duration_s=1200),seed);OUT.mkdir(exist_ok=True,parents=True)
 with gzip.open(OUT/f'stream-{seed}.jsonl.gz','wt',encoding='utf-8') as f:
  for win in w:f.write(json.dumps(dataclasses.asdict(win),separators=(',',':'))+'\n')
 (OUT/f'events-{seed}.json').write_text(json.dumps([dataclasses.asdict(ev) for ev in e],indent=2))

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--workers',type=int,default=4);ap.add_argument('--export-stream',type=int);ap.add_argument('--pilot',action='store_true');args=ap.parse_args()
 OUT.mkdir(parents=True,exist_ok=True)
 if args.export_stream is not None:export_stream(args.export_stream);return
 started=time.perf_counter()
 if args.pilot:
  r=one(('Main',3001));print('Pilot events',r['n_events'],'seconds',time.perf_counter()-started);return
 groups={};eventfile=OUT/'event_outcomes.csv.gz'
 tasks=[('Main',s) for s in SEEDS]+[(c,s) for c in STRESS for s in STRESS_SEEDS]+[('Deadline sensitivity',s) for s in range(5001,5031)]
 with gzip.open(eventfile,'wt',encoding='utf-8',newline='') as f,ProcessPoolExecutor(max_workers=args.workers) as pool:
  writer=None
  for i,r in enumerate(pool.map(one,tasks),1):
   event_rows=r.pop('event_rows')
   if event_rows:
    if writer is None:writer=csv.DictWriter(f,fieldnames=list(event_rows[0]));writer.writeheader()
    writer.writerows(event_rows)
   groups.setdefault(r['condition'],[]).append(r)
   if i%10==0:print('Decision streams',i,'/',len(tasks),'elapsed seconds',round(time.perf_counter()-started),flush=True)
 summaries={};main_idx=None
 for i,(name,rows) in enumerate(groups.items()):
  summaries[name],idx=summarize(rows,20261027+i)
  if name=='Main':main_idx=idx
 conditions=['Clean','Competing source','Reflection surrogate','Clock offset','Correlated microphone noise','Gain mismatch','Moving surrogate']
 atasks=[(c,side,snr,s,sound) for c in conditions for side in (.025,.035,.050) for snr in (20,0) for s in range(6001,6051) for sound in ('broadband','harmonic')]
 acoustic_rows=[]
 with ProcessPoolExecutor(max_workers=args.workers) as pool:
  for i,rows in enumerate(pool.map(acoustic,atasks),1):
   acoustic_rows.extend(rows)
   if i%300==0:print('Acoustic scenes',i,'/',len(atasks),flush=True)
 with (OUT/'acoustic_trials.csv').open('w',encoding='utf-8',newline='') as f:
  writer=csv.DictWriter(f,fieldnames=list(acoustic_rows[0]));writer.writeheader();writer.writerows(acoustic_rows)
 acsum=[]
 for c in conditions:
  for af in (1.,.25):
   rows=[r for r in acoustic_rows if r['condition']==c and r['bins']==af];valid=[r for r in rows if r['gate_valid']]
   acsum.append(dict(condition=c,bins=af,n=len(rows),wrong_quadrant_pct=100*np.mean([r['wrong_quadrant'] for r in rows]),mae_deg=np.mean([r['angular_error'] for r in rows]),gate_coverage_pct=100*len(valid)/len(rows),wrong_among_valid_pct=100*np.mean([r['wrong_quadrant'] for r in valid]) if valid else None))
 deps={str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'python/deda/synth.py',ROOT/'python/deda/policy.py',ROOT/'python/deda/metrics.py',ROOT/'python/deda/doa.py']}
 result=dict(scope='SYNTHETIC ONLY. No hardware, recordings, trained classifier, or participant validation.',protocol_version=1,seed_design=dict(main=SEEDS,stress=STRESS_SEEDS,deadline=list(range(5001,5031)),acoustic=list(range(6001,6051))),duration_s=1200,main_events=sum(r['n_events'] for r in groups['Main']),total_decision_stream_realizations=len(tasks),total_decision_events=sum(r['n_events'] for rows in groups.values() for r in rows),base_config=dataclasses.asdict(BASE),generator=dataclasses.asdict(SynthParams(duration_s=1200)),stress_changes=STRESS,per_stream=groups,summary=summaries,paired=paired(groups['Main'],main_idx),acoustic_summary=acsum,acoustic_scenes=len(atasks),acoustic_estimates=len(acoustic_rows),bootstrap_replicates=BOOT,bootstrap_seed_base=20261027,signflip_replicates=100000,paired_test_family=16,source_sha256=deps,python=platform.python_version(),numpy=np.__version__,elapsed_host_seconds=time.perf_counter()-started)
 # None is retained for undefined conditional metrics. NaN is not valid JSON.
 def clean(x):
  if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
  if isinstance(x,list):return [clean(v) for v in x]
  if isinstance(x,float) and not math.isfinite(x):return None
  return x
 target=OUT/'study_results.json';target.write_text(json.dumps(clean(result),indent=2,allow_nan=False),encoding='utf-8')
 files=[eventfile,OUT/'acoustic_trials.csv',target]
 (OUT/'SHA256SUMS.txt').write_text('\n'.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name for p in files)+'\n')
 print('SAVED',target,'main events',result['main_events'],'elapsed',round(time.perf_counter()-started),flush=True)

if __name__=='__main__':main()
