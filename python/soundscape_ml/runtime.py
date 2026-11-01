"""NumPy-only features/inference and WAV parsing shared by training and serving."""
from pathlib import Path
import base64, io, json, wave, hashlib, time, dataclasses
import numpy as np
from deda.policy import Config, DEDA, FixedThreshold, Window

ROOT=Path(__file__).resolve().parents[2]
MODEL_DIR=ROOT/'models'/'esc50'
FEATURE_VERSION="logmel_causal_v1"
FS=16000
CONTEXT=16384  # 1024 ms of real audio, before the first prediction
HOP=4096       # fresh predictions every 256 ms; do not repeat them every 64 ms
WARNINGS={'dog':'Dog barking nearby','car_horn':'Vehicle horn nearby','siren':'Emergency siren sounding',
          'glass_breaking':'Glass breaking nearby','clock_alarm':'Alarm clock ringing',
          'door_wood_knock':'Someone knocking','crying_baby':'Baby crying','rain':'Rain in the surroundings (information)'}

def decode_wav(data):
    if len(data)>3_000_000: raise ValueError('WAV must be under 3 MB')
    try:
        with wave.open(io.BytesIO(data),'rb') as f:
            rate=f.getframerate();channels=f.getnchannels();width=f.getsampwidth();frames=f.getnframes()
            if not 8000<=rate<=96000 or channels not in (1,2) or width not in (1,2,3,4):
                raise ValueError('Use 8-96 kHz mono/stereo integer PCM WAV')
            if frames/rate>15 or frames/rate<.064: raise ValueError('Use a WAV between 64 ms and 15 seconds')
            raw=f.readframes(frames)
        if width==1:x=(np.frombuffer(raw,np.uint8).astype(float)-128)/128
        elif width==3:
            a=np.frombuffer(raw,np.uint8).reshape(-1,3).astype(np.int32)
            x=a[:,0]|(a[:,1]<<8)|(a[:,2]<<16);x=((x^0x800000)-0x800000)/8388608
        else:x=np.frombuffer(raw,'<i'+str(width)).astype(float)/(2**(width*8-1))
        x=x.reshape(-1,channels).mean(axis=1)
        if rate>FS:
            # Windowed-sinc anti-alias filter before downsampling.
            taps=np.arange(-64,65);cutoff=.45*FS/rate
            h=2*cutoff*np.sinc(2*cutoff*taps)*np.hamming(len(taps));h/=h.sum()
            x=np.convolve(x,h,mode='full')[:len(x)]  # causal filter, no future samples
        x=np.interp(np.arange(round(len(x)*FS/rate))*rate/FS,np.arange(len(x)),x)
        if not np.isfinite(x).all():raise ValueError('Nonfinite audio')
        return x.astype(np.float32)
    except (wave.Error,EOFError,IndexError) as e:raise ValueError('Invalid or unsupported PCM WAV') from e

def mel_bank():
    mel=lambda f:2595*np.log10(1+f/700)
    hz=lambda m:700*(10**(m/2595)-1)
    edges=hz(np.linspace(mel(50),mel(7800),66));f=np.fft.rfftfreq(512,1/FS)
    return np.maximum(0,np.minimum((f[None,:]-edges[:-2,None])/(edges[1:-1,None]-edges[:-2,None]),
                                  (edges[2:,None]-f[None,:])/(edges[2:,None]-edges[1:-1,None])))
BANK=mel_bank()

def features(x):
    # Same feature extractor in train, validation, test, uploaded and hosted inference.
    x=np.asarray(x,dtype=float)
    if len(x)<CONTEXT:raise ValueError('At least 1024 ms of audio is required')
    x=x[-CONTEXT:]
    frames=np.lib.stride_tricks.sliding_window_view(x,400)[::160]
    power=np.abs(np.fft.rfft(frames*np.hanning(400),n=512))**2
    lm=np.log(np.maximum(power@BANK.T,1e-10))
    delta=np.diff(lm,axis=0)
    return np.concatenate([lm.mean(0),lm.std(0),np.quantile(lm,.1,axis=0),np.quantile(lm,.9,axis=0),delta.std(0)])

def window_features(x):
    ends=list(range(CONTEXT,len(x)+1,HOP))
    if not ends:raise ValueError('At least 1024 ms of audio is required')
    return np.stack([features(x[e-CONTEXT:e]) for e in ends]),ends

def softmax(z):
    z=z-np.max(z,axis=-1,keepdims=True);e=np.exp(z);return e/e.sum(axis=-1,keepdims=True)

def load_model():
    path=MODEL_DIR/'model.npz'
    if not path.exists():raise ValueError('No trained model. Run the dataset training workflow first.')
    # No pickle/joblib execution in serving.
    with np.load(path,allow_pickle=False) as a:m={k:a[k] for k in a.files}
    if 'feature_version' not in m or str(m['feature_version'])!=FEATURE_VERSION:
        raise ValueError('Model feature version mismatch; retrain with the current pipeline')
    m['labels']=m['labels'].tolist()
    return m

def predict_features(x,m):
    return softmax(((x-m['mean'])/m['scale'])@m['weights'].T/m['temperature']+m['bias']/m['temperature'])

def model_status():
    card=MODEL_DIR/'model_card.json';report=ROOT/'results/esc50/evaluation.json'
    m=json.loads(card.read_text()) if card.exists() else None
    r=json.loads(report.read_text()) if report.exists() else None
    path=MODEL_DIR/'model.npz'
    ready=path.exists() and m is not None and r is not None and m.get('feature_version')==FEATURE_VERSION
    if ready: ready=hashlib.sha256(path.read_bytes()).hexdigest()==m['sha256']==r['model_sha256']
    return dict(ready=ready,model=m,evaluation=r,
                dataset_ready=(ROOT/'data/raw/esc50/ESC-50-master/meta/esc50.csv').exists())

def classify_audio(data, *, truth=None, virtual=None):
    started=time.perf_counter();x=decode_wav(data);m=load_model()
    channels=None;geometry=None
    if virtual is not None:
        if not isinstance(virtual,dict):raise ValueError('Virtual geometry must be an object')
        from deda.simulator import number
        from deda.doa import simulate_array,triangle_positions
        angle=number(virtual.get('angle',180),'virtual angle',0,359)
        snr=number(virtual.get('snr_db',20),'virtual SNR',-10,30)
        rng=np.random.default_rng(7);pos=triangle_positions(.035)
        channels=simulate_array(x,angle,pos,FS,200,rng)
        rms=max(float(np.sqrt(np.mean(x*x))),1e-6)
        channels+=rng.normal(0,rms*10**(-snr/20),channels.shape)
        x=channels[0].astype(np.float32)
        geometry=dict(angle=angle,snr_db=snr,side_mm=35,seed=7,scope='Ideal virtual propagation, not recorded three-mic audio')
    fx,ends=window_features(x);pr=predict_features(fx,m)
    labels=m['labels'];alert_classes=tuple(i for i,l in enumerate(labels) if l in WARNINGS)
    n=len(labels);cfg=Config(hop_ms=256,deadline_ms=300,proc_ms=0,h_hi=(2.,)*n,h_lo=(1.6,)*n,h_urgent=(3.,)*n)
    policy=DEDA(cfg,critical=alert_classes,n_classes=n)
    baseline=FixedThreshold(.7,channels is not None,critical=alert_classes)
    rows=[];alerts=[];ba=[]
    def serialize(a):
        label=labels[a.cls]
        return dict(t_ms=a.t_ms,kind=a.kind,label=label,message=WARNINGS.get(label,label),motors=a.motors,theta=a.theta)
    for probs,end in zip(pr,ends):
        tm=end*1000/FS;direction=None
        if channels is not None:
            from deda.doa import estimate_direction
            from deda.policy import DirObs,dir_valid
            obs,_=estimate_direction(channels[:,end-1024:end],FS,pos,active_frac=.25)
            direction=DirObs(obs.theta_deg,obs.closure,obs.norm,obs.coherence)
        w=Window(tm,probs.tolist(),direction)
        aa=policy.step(w);bb=baseline.step(w);alerts.extend(map(serialize,aa));ba.extend(map(serialize,bb))
        top=np.argsort(probs)[-3:][::-1]
        rows.append(dict(t_ms=tm,prediction=labels[top[0]],confidence=float(probs[top[0]]),probabilities=probs.tolist(),direction_observation=dataclasses.asdict(direction) if direction else None,direction_deg=direction.theta_deg if direction else None,direction_reliable=dir_valid(direction,cfg) if direction else False,
                         top3=[dict(label=labels[i],confidence=float(probs[i])) for i in top],
                         alerts=[serialize(a) for a in aa]))
    avg=pr.mean(0);top=int(np.argmax(avg));name=labels[top]
    audio_b64=None
    if channels is not None:
        stream=io.BytesIO()
        with wave.open(stream,'wb') as f:
            f.setnchannels(1);f.setsampwidth(2);f.setframerate(FS);f.writeframes(np.round(np.clip(x,-1,1)*32767).astype('<i2').tobytes())
        audio_b64=base64.b64encode(stream.getvalue()).decode()
    return dict(audio_b64=audio_b64,mode='trained_real_audio',classes=labels,policy_config=dataclasses.asdict(cfg),alert_classes=list(alert_classes),input_sha256=hashlib.sha256(data).hexdigest(),prediction=name,confidence=float(avg[top]),truth=truth,
                correct=name==truth if truth is not None else None,windows=rows,alerts=alerts,baseline_alerts=ba,
                waveform=x[::max(1,len(x)//600)].tolist(),duration_ms=len(x)*1000/FS,
                context_ms=1024,hop_ms=256,model_sha256=hashlib.sha256((MODEL_DIR/'model.npz').read_bytes()).hexdigest(),
                runtime_ms=round((time.perf_counter()-started)*1000,2),virtual_geometry=geometry,direction='synthetic virtual-array estimate' if channels is not None else 'unavailable - mono recording; all commands are general',
                note='Predictions come only from audio. Truth label is used after inference for display, never as a model input. First prediction needs 1024 ms; no 300 ms onset guarantee. Clip labels do not provide exact sound onset. Scores are not guaranteed correctness probabilities.')
