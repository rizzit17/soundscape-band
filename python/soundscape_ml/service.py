"""HTTP helpers. Training is loopback-only; public serving accepts bounded WAVs."""
import base64,json,threading,subprocess,sys
from .runtime import ROOT,MODEL_DIR,model_status,classify_audio
LOCK=threading.Lock();JOB={'state':'idle','message':'Training has not been started in this server session.'}

def examples():
    p=MODEL_DIR/'examples.json'
    return json.loads(p.read_text()) if p.exists() else []

def example_data(id):
    item=next((e for e in examples() if e['id']==id),None)
    if item is None:raise ValueError('Unknown held-out example')
    return (MODEL_DIR/'examples'/item['id']).read_bytes(),item

def status():
    with LOCK:j=dict(JOB)
    return dict(**model_status(),job=j,examples=examples())

def predict(raw, *, include_scene=False):
    if not model_status()["ready"]:raise ValueError("No complete model/evaluation bundle is ready. Finish local training first.")
    if 'example_id' in raw:
        data,item=example_data(raw['example_id'])
        result=classify_audio(data,truth=item['label'],**dict(({'virtual':raw['virtual']} if 'virtual' in raw else {}),**({'include_scene':True} if include_scene else {})));result['example']=item
        result['audio_b64']=result.get('audio_b64') or base64.b64encode(data).decode()
        return result
    value=raw.get('audio_b64')
    if not isinstance(value,str) or len(value)>4_000_000:raise ValueError('Provide a PCM WAV under 3 MB')
    try:data=base64.b64decode(value,validate=True)
    except Exception as e:raise ValueError('Invalid base64 WAV') from e
    return classify_audio(data,**dict(({'virtual':raw['virtual']} if 'virtual' in raw else {}),**({'include_scene':True} if include_scene else {})))  # Never accept user-supplied truth as a prediction input.

def start_job(action):
    if action not in ('prepare','train','evaluate'):raise ValueError('Action must be prepare, train or evaluate')
    with LOCK:
        if JOB['state']=='running':raise ValueError('An ML job is already running')
        JOB.update(state='running',action=action,message='Starting '+action)
    def worker():
        try:
            proc=subprocess.Popen([sys.executable,'-u','-m','soundscape_ml.train',action],cwd=ROOT/'python',stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
            lines=[]
            for line in proc.stdout:
                lines.append(line.rstrip())
                with LOCK:JOB['message']='\n'.join(lines[-8:])
            code=proc.wait()
            with LOCK:JOB.update(state='complete' if code==0 else 'failed',exit_code=code)
        except Exception:
            with LOCK:JOB.update(state='failed',message='Could not start job. See local server terminal.')
    threading.Thread(target=worker,daemon=True).start()
    return dict(state='running',action=action)
