# ESC-50 real-audio recognition result

This is a separate experiment from the paper's synthetic decision-stream study.

- Model: supervised 50-class log-mel logistic-regression baseline, trained from scratch (not YAMNet).
- Train: 1,200 clips in predefined folds 1-3.
- Validation: 398 clips from fold 4. Two clips sharing original source IDs with test fold 5 were excluded, not moved.
- Test: all 400 clips in fold 5, unchanged. No original source spans the retained train/validation/test splits. Exact-file duplicate audit found no cross-split duplicate group.
- Clip accuracy: **42.75%** (171/400).
- Macro F1: **40.68%**.
- Accuracy 95% source-group bootstrap interval: **37.29%-48.46%** (2,000 resamples).
- Majority-class baseline: 2.0%.
- This is one holdout, not five-fold cross-validation or a state-of-the-art result.

The saved model was independently re-evaluated without training or calibration; `verification.json` confirms matching accuracy and macro F1. `evaluation.json` includes all 50 per-class results and a confusion matrix; `test_predictions.csv` records each mistake; `split_manifest.csv` contains source IDs, fold assignments, exclusions and original file checksums.

Performance is uneven. For example, siren recall is 12.5% (1/8) and dog recall is 62.5% (5/8) on this small test fold. This model is a baseline for further work, not a reliable warning product. Do not tune on these test results and continue calling this test set unseen.

No physical direction, onset-to-vibration timing, user benefit or safety performance is measured. Public recordings plus a virtual microphone array are not actual wearable recordings. The model needs 1,024 ms of audio context before its first prediction; it does not satisfy a 300 ms sound-onset target.

Reproduce with the steps in [the real-audio guide](../../docs/REAL_AUDIO_ML_GUIDE.md). Exact training environment: Python 3.13.7, NumPy 2.4.3, scikit-learn 1.8.0; see `requirements-ml-lock.txt`. Model/metadata hashes are in the JSON. Dataset sources and creator licensing are retained in `models/esc50/ESC50_LICENSE.txt` and `examples.json`.
