"""Adapt real model + computed virtual-array observations to the main replay UI."""
from .service import predict
from .runtime import WARNINGS
from deda.policy import quadrant_of

def recording_scene(raw):
    virtual={k:raw[k] for k in ('angle','snr_db','seed','condition','active_frac') if k in raw}
    req={'virtual':virtual}
    if raw.get('example_id'):req['example_id']=raw['example_id']
    elif raw.get('audio_b64'):req['audio_b64']=raw['audio_b64']
    else:raise ValueError('Choose a dataset recording or upload a WAV')
    r=predict(req,include_scene=True)
    frames=r.pop('scene_frames');audio=r.pop('scene_audio');labels=r['classes'];angle=r['virtual_geometry']['angle']
    alerts=[a for f in frames for a in f['alerts']];baseline=[a for f in frames for a in f['baseline_alerts']]
    def outcome(aa):
        first=next((a for a in aa if a['kind']!='UPDATE'),None)
        return dict(critical=True,detected=first is not None,correct_class=(first['sound']==r['truth']) if first and r['truth'] is not None else None,
                    missed=None,missed_or_late=None,wrong_direction=bool(first and first['kind']=='DIR' and not first['motors']&(1<<quadrant_of(angle))),
                    nondirectional=bool(first and first['kind']=='NONDIR'),latency_ms=first['t_ms'] if first else None,false_alerts=None,first_alert=first)
    avg=[sum(f['probs'][i] for f in frames)/len(frames) for i in range(len(labels))]
    evidence=sorted(r['alert_classes'],key=lambda i:avg[i],reverse=True)[:4]
    return dict(mode='trained_recording_scene',audio=audio,class_names=labels,evidence_indices=evidence,critical_indices=r['alert_classes'],
        model_info=dict(prediction=r['prediction'],confidence=r['confidence'],truth=r['truth'],correct=r['correct'],context_ms=r['context_ms'],model_sha256=r['model_sha256'],input_sha256=r['input_sha256'],example=r.get('example'),
                        note='Audio drives the learned classifier and virtual GCC-PHAT localization. Source angle is virtual ground truth; no recorded spatial ground truth or verified event onset.'),
        options=dict(sound='recording',recognition='model',example_id=raw.get('example_id',''),upload_key=raw.get('upload_key',''),angle=angle,snr_db=r['virtual_geometry']['snr_db'],condition=r['virtual_geometry']['condition'],seed=r['virtual_geometry']['seed'],active_frac=r['virtual_geometry']['active_frac'],confidence=r['confidence'],event_ms=raw.get('event_ms',1024)),
        scenario=dict(sound='recording',audio_source='Held-out recording or uploaded WAV; actual model scores; ideal virtual array',demo_event_lane=False,warning=None),
        schema_version=2,note=r['note'],sample_rate=16000,hop_ms=256,onset_ms=0,offset_ms=r['duration_ms'],duration_ms=r['duration_ms'],processing_allowance_ms=0,runtime_ms=r['runtime_ms'],config=r['policy_config'],
        alerts=alerts,baseline_alerts=baseline,deda=outcome(alerts),baseline=outcome(baseline),frames=frames)
