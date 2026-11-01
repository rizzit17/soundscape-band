"""Prepare a minimal Vercel upload without local reports, data, keys or builds."""
from pathlib import Path
import shutil
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'work/vercel-site'
for p in [OUT/'api',OUT/'public',OUT/'python/deda']:
    p.mkdir(parents=True,exist_ok=True)
for name in ['index.html','app.js','style.css','favicon.svg','ml.html','ml.js']:
    shutil.copyfile(ROOT/'simulator'/name,OUT/'public'/name)
for name in ['__init__.py','simulator.py','policy.py','doa.py']:
    shutil.copyfile(ROOT/'python/deda'/name,OUT/'python/deda'/name)
shutil.copytree(ROOT/'python/soundscape_ml',OUT/'python/soundscape_ml',dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__'))
if (ROOT/'models/esc50/model.npz').exists():
    shutil.copytree(ROOT/'models/esc50',OUT/'models/esc50',dirs_exist_ok=True)
    (OUT/'results/esc50').mkdir(parents=True,exist_ok=True)
    shutil.copyfile(ROOT/'results/esc50/evaluation.json',OUT/'results/esc50/evaluation.json')
shutil.copytree(ROOT/'python/deda/audio',OUT/'python/deda/audio',dirs_exist_ok=True)
shutil.copyfile(ROOT/'python/simulator_server.py',OUT/'python/simulator_server.py')
shutil.copyfile(ROOT/'deployment/api.py',OUT/'api/index.py')
shutil.copyfile(ROOT/'deployment/vercel.json',OUT/'vercel.json')
(OUT/'requirements.txt').write_text('numpy==2.3.5\n',encoding='utf-8')
(OUT/'.python-version').write_text('3.12\n',encoding='utf-8')
(OUT/'.vercelignore').write_text('__pycache__/\n*.pyc\n',encoding='utf-8')
print(OUT)
