"""ML correctness tests use fixtures, never count fixture accuracy as dataset results."""
import io,wave,json,hashlib
from pathlib import Path
import numpy as np
import pytest
from deda.policy import DEDA,Config,Window
from soundscape_ml.runtime import decode_wav,features,window_features,softmax,predict_features,CONTEXT,FS


def wav(x,rate=16000,channels=1):
    stream=io.BytesIO()
    with wave.open(stream,'wb') as f:
        f.setnchannels(channels);f.setsampwidth(2);f.setframerate(rate);f.writeframes(np.asarray(x,dtype='<i2').tobytes())
    return stream.getvalue()


def test_wav_decode_resamples_and_downmixes_without_using_filename():
    x=np.tile([1000,3000],16000)
    y=decode_wav(wav(x,16000,2))
    assert len(y)==16000
    np.testing.assert_allclose(y,2000/32768)
    y=decode_wav(wav(np.ones(8000)*1000,8000))
    assert len(y)==16000


@pytest.mark.parametrize('data',[b'notwav',b'',wav(np.zeros(16000*16))],ids=['invalid','empty','too-long'])
def test_invalid_or_unbounded_audio_rejected(data):
    with pytest.raises(ValueError):decode_wav(data)


def test_feature_windows_are_causal_and_require_full_context():
    rng=np.random.default_rng(8);a=rng.normal(0,.1,CONTEXT+4096*3);b=a.copy();b[CONTEXT:]=0
    fa,ends=window_features(a);fb,_=window_features(b)
    assert ends[0]==16384 and len(fa)==4
    np.testing.assert_array_equal(fa[0],fb[0])
    assert not np.allclose(fa[-1],fb[-1])
    with pytest.raises(ValueError):features(a[:500])
    assert fa.shape==(4,320) and np.isfinite(fa).all()


def test_model_scores_are_finite_normalized_and_use_waveform_features():
    rng=np.random.default_rng(10);m=dict(mean=np.zeros(320),scale=np.ones(320),weights=rng.normal(0,.01,(5,320)),bias=np.zeros(5),temperature=1.)
    x=np.sin(2*np.pi*440*np.arange(CONTEXT)/FS);y=np.sin(2*np.pi*3000*np.arange(CONTEXT)/FS)
    p=predict_features(np.stack([features(x),features(y)]),m)
    np.testing.assert_allclose(p.sum(1),1)
    assert np.isfinite(p).all() and not np.allclose(p[0],p[1])


def test_multiclass_deda_preserves_explicit_dataset_indices_and_unknown_rejection():
    n=50;cfg=Config(hop_ms=256,proc_ms=0,h_hi=(2.,)*n,h_lo=(1.6,)*n,h_urgent=(3.,)*n)
    policy=DEDA(cfg,critical=(17,43),n_classes=n)
    probs=np.full(n,.01/(n-1));probs[43]=.99
    alerts=policy.step(Window(1024,probs.tolist(),None))
    assert len(alerts)==1 and alerts[0].cls==43 and alerts[0].motors==15
    policy=DEDA(cfg,critical=(17,43),n_classes=n);probs[:]=.01/(n-1);probs[2]=.99
    assert policy.step(Window(1024,probs.tolist(),None))==[]


def test_example_ids_cannot_read_arbitrary_files(monkeypatch):
    from soundscape_ml import service
    monkeypatch.setattr(service,'examples',lambda:[dict(id='safe.wav',label='dog')])
    with pytest.raises(ValueError):service.example_data('../../private.wav')


def test_upload_truth_is_never_forwarded_to_recognizer(monkeypatch):
    from soundscape_ml import service
    import base64
    monkeypatch.setattr(service,'model_status',lambda:dict(ready=True))
    calls=[]
    monkeypatch.setattr(service,'classify_audio',lambda data,**kwargs:calls.append((data,kwargs)) or {})
    service.predict(dict(audio_b64=base64.b64encode(b'x').decode(),truth='dog',filename='dog.wav'))
    assert calls==[(b'x',{})]


def test_downsampling_does_not_leak_future_samples_into_first_prediction():
    rate=44100;rng=np.random.default_rng(19)
    a=rng.integers(-10000,10000,rate*2,dtype=np.int16);b=a.copy();b[int(1.024*rate)+1:]=0
    da=decode_wav(wav(a,rate));db=decode_wav(wav(b,rate))
    np.testing.assert_array_equal(da[:CONTEXT],db[:CONTEXT])
