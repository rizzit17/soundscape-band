from pathlib import Path
import csv,json,hashlib
import pytest
from soundscape_ml.runtime import ROOT,MODEL_DIR,load_model,predict_features,decode_wav,window_features
from soundscape_ml.service import predict,examples

pytestmark=pytest.mark.skipif(not (MODEL_DIR/'model_card.json').exists(),reason='Train the public-data model before running bundle integration checks')

def test_exported_report_split_and_model_integrity():
    report=json.loads((ROOT/'results/esc50/evaluation.json').read_text())
    assert report['test_clips']==400 and report['train_clips']==1200 and report['validation_clips']==398 and report['excluded_clips']==2
    assert len(report['classes'])==50
    rows=list(csv.DictReader((ROOT/'results/esc50/split_manifest.csv').open()))
    sources={}
    for r in rows:
        if r['split']=='excluded_source_overlap':continue
        sources.setdefault(r['source_id'],set()).add(r['split'])
        assert r['split']==('train' if int(r['fold'])<=3 else 'validation' if r['fold']=='4' else 'test')
    assert all(len(s)==1 for s in sources.values())
    preds=list(csv.DictReader((ROOT/'results/esc50/test_predictions.csv').open()))
    assert len(preds)==400
    assert report['test_accuracy']==sum(r['correct']=='True' for r in preds)/400
    assert report['model_sha256']==hashlib.sha256((MODEL_DIR/'model.npz').read_bytes()).hexdigest()


def test_bundled_test_predictions_come_from_audio_not_truth():
    model=load_model()
    for item in examples():
        data=(MODEL_DIR/'examples'/item['id']).read_bytes()
        fx,_=window_features(decode_wav(data));probs=predict_features(fx,model).mean(0)
        r=predict(dict(example_id=item['id']))
        assert r['prediction']==model['labels'][int(probs.argmax())]
        assert r['truth']==item['label'] and r['example']['fold']==5
        assert r['correct']==(r['prediction']==r['truth'])
        assert r['windows'][0]['t_ms']==1024
        assert all(a['kind']=='NONDIR' and a['motors']==15 for a in r['alerts'])

def test_prediction_export_can_replay_the_same_multiclass_policy():
    from deda.policy import DEDA,Config,Window
    item=examples()[0];r=predict(dict(example_id=item['id']))
    policy=DEDA(Config(**r['policy_config']),critical=r['alert_classes'],n_classes=len(r['classes']))
    replay=[]
    for w in r['windows']:
        for a in policy.step(Window(w['t_ms'],w['probabilities'],None)):
            replay.append((a.t_ms,a.kind,r['classes'][a.cls],a.motors))
    assert replay==[(a['t_ms'],a['kind'],a['label'],a['motors']) for a in r['alerts']]
