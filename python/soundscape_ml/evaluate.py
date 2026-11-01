"""Re-evaluate a saved model on fold 5 without fitting or calibration."""
import json,hashlib,time
import numpy as np
from sklearn.metrics import accuracy_score,f1_score
from .runtime import ROOT,MODEL_DIR,load_model,decode_wav,window_features,predict_features
from .train import metadata,DATA

def evaluate():
    m=load_model();truth=[];pred=[];labels=m['labels']
    rows=[r for r in metadata() if r['split']=='test']
    for i,r in enumerate(rows):
        fx,_=window_features(decode_wav((DATA/'audio'/r['filename']).read_bytes()))
        pred.append(int(predict_features(fx,m).mean(0).argmax()));truth.append(labels.index(r['category']))
        if i%100==0:print('Re-evaluating',i,'/',len(rows),flush=True)
    result=dict(model_sha256=hashlib.sha256((MODEL_DIR/'model.npz').read_bytes()).hexdigest(),test_clips=len(rows),test_accuracy=float(accuracy_score(truth,pred)),test_macro_f1=float(f1_score(truth,pred,average='macro')),scope='Saved-model inference only; no fitting, calibration or threshold changes',created_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()))
    reference=json.loads((ROOT/'results/esc50/evaluation.json').read_text())
    result['matches_training_evaluation']=all(abs(result[k]-reference[k])<1e-12 for k in ['test_accuracy','test_macro_f1']) and result['model_sha256']==reference['model_sha256']
    (ROOT/'results/esc50/verification.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2),flush=True)
    if not result['matches_training_evaluation']:raise RuntimeError('Saved-model evaluation does not match; do not publish')

if __name__=='__main__':evaluate()
