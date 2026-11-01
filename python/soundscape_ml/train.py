"""Reproducible ESC-50 baseline: fixed folds, train-only scaling, held-out evaluation."""
import argparse,csv,json,hashlib,zipfile,sys,time,platform
from pathlib import Path
import numpy as np
from .runtime import ROOT,MODEL_DIR,decode_wav,window_features,predict_features,softmax,FEATURE_VERSION

DATA=ROOT/'data/raw/esc50/ESC-50-master'

def prepare():
    archive=ROOT/'data/raw/esc50/archive.zip'
    if not archive.exists():
        import urllib.request
        archive.parent.mkdir(parents=True,exist_ok=True)
        print('Downloading ESC-50 (~600 MB). Keep raw audio out of Git.',flush=True)
        part=archive.with_suffix('.part')
        with urllib.request.urlopen('https://github.com/karolpiczak/ESC-50/archive/refs/heads/master.zip',timeout=120) as r,part.open('wb') as f:
            while True:
                b=r.read(1024*1024)
                if not b:break
                f.write(b)
        part.replace(archive)
    with zipfile.ZipFile(archive) as z:
        for member in z.infolist():
            dst=(archive.parent/member.filename).resolve()
            if not dst.is_relative_to(archive.parent.resolve()):raise ValueError('Unsafe archive path')
        z.extractall(archive.parent)
    print('Dataset prepared:',DATA,flush=True)

def metadata():
    if not (DATA/'meta/esc50.csv').exists():raise ValueError('Run prepare first')
    rows=list(csv.DictReader((DATA/'meta/esc50.csv').open()))
    if len(rows)!=2000 or len({r['category'] for r in rows})!=50:raise ValueError('Expected the complete 2000-clip, 50-category ESC-50 release')
    priority={'train':0,'validation':1,'test':2}
    destinations={}
    for r in rows:
        r['split']='train' if int(r['fold'])<=3 else 'validation' if r['fold']=='4' else 'test'
        src=r['src_file']
        destinations[src]=max(destinations.get(src,0),priority[r['split']])
    for r in rows:
        if priority[r['split']]<destinations[r['src_file']]:r['split']='excluded_source_overlap'
    return rows

def train():
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import accuracy_score,f1_score,classification_report,confusion_matrix,log_loss
    from sklearn.exceptions import ConvergenceWarning
    from threadpoolctl import threadpool_limits
    import sklearn, warnings
    rows=metadata();labels=sorted({r['category'] for r in rows});indices={l:i for i,l in enumerate(labels)}
    cache=ROOT/'data/raw/esc50/features.npz'
    signature=hashlib.sha256((DATA/'meta/esc50.csv').read_bytes()+Path(__file__).with_name('runtime.py').read_bytes()).hexdigest()
    if cache.exists():
        with np.load(cache,allow_pickle=False) as a:
            valid=str(a['signature'])==signature
            if valid:X=a['X'];owners=a['owners']
    else:valid=False
    if not valid:
        X=[];owners=[]
        for i,r in enumerate(rows):
            x=decode_wav((DATA/'audio'/r['filename']).read_bytes());f,_=window_features(x)
            X.extend(f);owners.extend([i]*len(f))
            if i%100==0:print('Features',i,'/',len(rows),flush=True)
        X=np.asarray(X);owners=np.asarray(owners)
        np.savez_compressed(cache,X=X,owners=owners,signature=signature)
    folds=np.array([int(r['fold']) for r in rows]);yclip=np.array([indices[r['category']] for r in rows]);y=yclip[owners]
    splits=np.array([r['split'] for r in rows]);train=splits[owners]=='train';val=splits=='validation';test=splits=='test'
    scaler=StandardScaler().fit(X[train]);z=scaler.transform(X)
    print('Training 50-class log-mel logistic regression; folds 1-3 only.',flush=True)
    model=LogisticRegression(C=1.,max_iter=4000,tol=1e-3,random_state=7,solver='lbfgs')
    # Each source clip contributes equal total training weight.
    weights=1/np.bincount(owners)[owners[train]];weights*=len(weights)/weights.sum()
    with threadpool_limits(limits=4),warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always',ConvergenceWarning);model.fit(z[train],y[train],sample_weight=weights)
    if any(issubclass(w.category,ConvergenceWarning) for w in caught):raise RuntimeError('Training did not converge; no model published')
    logits=z@model.coef_.T+model.intercept_
    def clip_probs(temp):
        pp=softmax(logits/temp)
        return np.stack([pp[owners==i].mean(0) for i in range(len(rows))])
    # Temperature selection uses only fold 4. Test labels are not consulted.
    candidates=np.geomspace(.5,4,25)
    temp=float(min(candidates,key=lambda t:log_loss(yclip[val],clip_probs(t)[val],labels=np.arange(len(labels)))))
    probs=clip_probs(temp);pred=probs.argmax(1)
    MODEL_DIR.mkdir(parents=True,exist_ok=True)
    dest=MODEL_DIR/'model.npz';part=MODEL_DIR/'model.pending.npz'
    np.savez_compressed(part,mean=scaler.mean_,scale=scaler.scale_,weights=model.coef_,bias=model.intercept_,temperature=temp,labels=np.array(labels),feature_version=FEATURE_VERSION)
    part.replace(dest)
    # Export parity: serving is NumPy-only and must match training probabilities.
    from .runtime import load_model
    np.testing.assert_allclose(predict_features(X[:10],load_model()),softmax(logits[:10]/temp),rtol=1e-10,atol=1e-10)
    test_ids=np.flatnonzero(test);rng=np.random.default_rng(7001)
    # Bootstrap original recording groups, not correlated windows.
    groups=sorted({rows[i]['src_file'] for i in test_ids});groupids=[np.array([i for i in test_ids if rows[i]['src_file']==g]) for g in groups]
    boots=[]
    for _ in range(2000):
        ids=np.concatenate([groupids[j] for j in rng.integers(0,len(groups),len(groups))]);boots.append(float(np.mean(pred[ids]==yclip[ids])))
    report=dict(dataset='ESC-50',protocol='Single holdout, NOT five-fold CV. Train folds 1-3; validation 4 with source-overlap exclusions; test 5 intact.',
                train_clips=int(sum(splits=='train')),validation_clips=int(sum(val)),test_clips=int(sum(test)),excluded_clips=int(sum(splits=='excluded_source_overlap')),source_overlap_policy='Any source shared across splits is kept only in the later-priority split: test > validation > train. Earlier clips are excluded, not moved.',classes=labels,
                test_accuracy=float(accuracy_score(yclip[test],pred[test])),test_macro_f1=float(f1_score(yclip[test],pred[test],average='macro')),
                validation_accuracy=float(accuracy_score(yclip[val],pred[val])),test_accuracy_95ci=np.quantile(boots,[.025,.975]).tolist(),
                majority_baseline_accuracy=float(max(np.bincount(yclip[test]))/sum(test)),
                confusion_matrix=confusion_matrix(yclip[test],pred[test],labels=np.arange(len(labels))).tolist(),
                per_class=classification_report(yclip[test],pred[test],labels=np.arange(len(labels)),target_names=labels,output_dict=True,zero_division=0),
                temperature=temp,feature_windows=len(X),test_window_accuracy=float(np.mean(logits[splits[owners]=='test'].argmax(1)==y[splits[owners]=='test'])),
                model_sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),metadata_sha256=hashlib.sha256((DATA/'meta/esc50.csv').read_bytes()).hexdigest(),
                limitations=['Clip-level labels, no verified event onsets or real directional ground truth.','No physical wearable or user validation.','ESC-50 is small; this is a compact baseline, not state of the art.','Confidence scores do not provide open-set correctness guarantees.','Single holdout is not a published five-fold ESC-50 benchmark.'],
                created_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),python=platform.python_version(),numpy=np.__version__,sklearn=sklearn.__version__)
    out=ROOT/'results/esc50';out.mkdir(parents=True,exist_ok=True)
    (out/'evaluation.json').write_text(json.dumps(report,indent=2))
    with (out/'split_manifest.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['filename','source_id','fold','split','category','sha256'])
        for r in rows:w.writerow([r['filename'],r['src_file'],r['fold'],r['split'],r['category'],hashlib.sha256((DATA/'audio'/r['filename']).read_bytes()).hexdigest()])
    with (out/'test_predictions.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['filename','source_id','truth','prediction','confidence','correct'])
        for i in test_ids:w.writerow([rows[i]['filename'],rows[i]['src_file'],rows[i]['category'],labels[pred[i]],float(probs[i,pred[i]]),bool(pred[i]==yclip[i])])
    card=dict(name='ESC-50 log-mel logistic baseline',feature_version=FEATURE_VERSION,classes=labels,context_ms=1024,hop_ms=256,features='64 log-mel bands: mean/std/10th/90th percentile and delta std; 320 values',
              learning='Supervised training from scratch; not YAMNet or a deep neural network.',protocol=report['protocol'],temperature=temp,
              sha256=report['model_sha256'],license='ESC-50 CC BY-NC 3.0; preserve per-clip credits; noncommercial educational use.',
              warning_policy='Reference Python DEDA generalized to explicit dataset indices; only named configured events alert; all cues non-directional for mono input.',
              scope='Real dataset recognition; historical paper benchmark and Wokwi unchanged.')
    (MODEL_DIR/'model_card.json').write_text(json.dumps(card,indent=2))
    # Bundle only untouched fold-5 examples, with original dataset license and provenance.
    ex=MODEL_DIR/'examples';ex.mkdir(exist_ok=True)
    from .runtime import WARNINGS,FS
    import wave
    examples=[]
    for name in dict.fromkeys(list(WARNINGS)+['rain','chirping_birds','vacuum_cleaner']):
        r=next(r for r in rows if r['fold']=='5' and r['category']==name)
        x=decode_wav((DATA/'audio'/r['filename']).read_bytes())
        with wave.open(str(ex/r['filename']),'wb') as f:
            f.setnchannels(1);f.setsampwidth(2);f.setframerate(FS);f.writeframes(np.round(np.clip(x,-1,1)*32767).astype('<i2').tobytes())
        examples.append(dict(id=r['filename'],label=name,source_id=r['src_file'],fold=5,source='https://freesound.org/s/'+r['src_file']+'/',changes='Mono 16 kHz resampling only; full clip, no energy crop.'))
    (MODEL_DIR/'examples.json').write_text(json.dumps(examples,indent=2))
    (MODEL_DIR/'ESC50_LICENSE.txt').write_bytes((DATA/'LICENSE').read_bytes())
    print(json.dumps({k:report[k] for k in ['test_accuracy','test_macro_f1','test_accuracy_95ci','test_clips']},indent=2),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=['prepare','train','evaluate']);args=ap.parse_args()
    if args.command=='prepare':prepare()
    elif args.command=='train':train()
    else:
        from .evaluate import evaluate
        evaluate()
