# SoundScape on Vercel

Public simulation: **https://soundscape-simulation.vercel.app**

The webpage is served as static files and `/api/*` requests execute the same Python/NumPy GCC-PHAT and DEDA engine in Vercel Functions. The deployment contains no Android model, reports, study data, teacher feedback, local credentials or microphone recordings. No laptop server is needed to use the public URL.

## Redeploy

From the repository root:

```powershell
python deployment/prepare_vercel.py
cd work/vercel-site
vercel link --project soundscape-simulation
vercel deploy --prod
```

Authenticate with `vercel login` when needed. Select the project in the owner account. `work/vercel-site/.vercel` contains local project linkage and is ignored with the rest of `work/`; do not commit authentication tokens. This deployment uses a prepared folder, not automatic deployment on each GitHub push. Run the preparation command after changing the browser or engine source before redeploying.

`prepare_vercel.py` copies an explicit list of production files, writes a minimal NumPy-only dependency file and pins Python 3.12. The source API adapter and deployment configuration are kept in this directory. The original local server continues to work with its usual commands.

## Hosted behaviour

- Scenes, audible replay, presentation mode, event jumps, review cases and JSON/CSV exports use real Python calculations on synthetic inputs.
- Each API request is independent. Experiments run inside one bounded request; there are no in-memory background jobs shared between visitors or requests.
- Hosted experiments display indeterminate progress until the result returns. Cancellation, per-trial progress and recovery after reload remain features of the local server. Keep the hosted tab open until completion.
- Functions are configured for a 120-second maximum duration. The browser allows up to 150 seconds for the experiment response. Runtime availability and limits remain subject to the Vercel project settings.
- Audio stays browser-local after the computed signal is returned. The app does not request your microphone.
- The public demo is supplementary presentation software, not additional experimental evidence or validation of physical haptics.

## Checks

```powershell
$env:PYTHONPATH='python'
python -m pytest deployment/test_vercel.py python/tests/test_simulator.py -q -p no:cacheprovider
node simulator/app.test.cjs
```

The adapter tests cover independent scene requests, actual rewrite query routing, fallback, no-alert behaviour, complete quick-experiment exports and rejection of invalid/cross-origin submissions. The public deployment was checked without authentication for health, scene calculation, fallback and experiments.

Official platform references: [Python functions](https://vercel.com/docs/functions/runtimes/python), [configuration](https://vercel.com/docs/project-configuration/vercel-json).

The production full matrix with five seeds completed successfully: 965 trials, approximately 2.02 MB JSON including CSV, about 29 seconds for the verification request. This is a hosted software execution check, not physical timing evidence.
