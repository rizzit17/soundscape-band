"""Check Vercel requests independently of any persistent server state."""
import importlib.util
import json
import threading
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.request import Request,urlopen
from urllib.error import HTTPError
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('vercel_adapter',ROOT/'deployment/api.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

@pytest.fixture
def hosted_url():
    server=ThreadingHTTPServer(('127.0.0.1',0),m.handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    yield 'http://127.0.0.1:'+str(server.server_port)
    server.shutdown();server.server_close();thread.join()

def request(url,data=None,origin=None):
    headers={'Content-Type':'application/json'}
    if origin:headers['Origin']=origin
    req=Request(url,data=None if data is None else json.dumps(data).encode(),headers=headers)
    with urlopen(req,timeout=20) as response:return json.load(response)

def test_health_rewrite_and_fresh_scene_requests(hosted_url):
    assert request(hosted_url+'/api/index?route=health')['execution']=='serverless'
    a=request(hosted_url+'/api/index?route=simulate',{},hosted_url)
    b=request(hosted_url+'/api/simulate',{},hosted_url)
    assert a['alerts']==b['alerts']
    assert a['deda']['first_alert']['motors']==4
    assert a['audio']['sample_rate']==16000
    assert 'csv' in a

def test_fallback_and_no_alert(hosted_url):
    assert request(hosted_url+'/api/simulate',dict(condition='dropout'))['deda']['first_alert']['motors']==15
    assert request(hosted_url+'/api/simulate',dict(confidence=.30))['alerts']==[]

def test_hosted_experiment_has_all_trials_and_exports(hosted_url):
    r=request(hosted_url+'/api/experiment',dict(suite='quick',seeds=1))
    assert len(r['trials'])==33
    assert r['policies']['deda']['events']==32
    assert len(r['csv'].splitlines())==67

def test_invalid_and_cross_origin_requests_rejected(hosted_url):
    for data,origin,code in [([],None,400),({'seed':-1},None,400),({},'https://unrelated.example',403)]:
        with pytest.raises(HTTPError) as err:request(hosted_url+'/api/simulate',data,origin)
        assert err.value.code==code
    with pytest.raises(HTTPError) as err:request(hosted_url+'/api/experiment/start',{})
    assert err.value.code==404

@pytest.mark.skipif(not (ROOT/'models/esc50/model.npz').exists(),reason='Train real-data model first')
def test_hosted_ml_status_prediction_and_upload_boundary(hosted_url):
    import base64
    status=request(hosted_url+'/api/index?route=ml/status')
    assert status['ready'] and status['training_allowed'] is False
    item=status['examples'][0]
    r=request(hosted_url+'/api/index?route=ml/predict',dict(example_id=item['id']))
    assert r['mode']=='trained_real_audio' and r['truth']==item['label']
    assert len(r['classes'])==50 and len(r['windows'][0]['probabilities'])==50
    data=(ROOT/'models/esc50/examples'/item['id']).read_bytes()
    upload=request(hosted_url+'/api/ml/predict',dict(audio_b64=base64.b64encode(data).decode(),truth='invented'))
    assert upload['truth'] is None
    assert upload['prediction']==r['prediction']
    assert upload['confidence']==r['confidence']
    for route,data,code in [('ml/train',{'action':'prepare'},404),('ml/predict',{'example_id':'../../private'},400),('ml/predict',{'example_id':item['id'],'virtual':{'angle':400}},400)]:
        with pytest.raises(HTTPError) as err:request(hosted_url+'/api/'+route,data)
        assert err.value.code==code
