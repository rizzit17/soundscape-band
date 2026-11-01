"use strict";
(()=>{
 const $=id=>document.getElementById(id);let state=null,last=null,busy=false,upload=null,audioUrl=null;
 const pct=n=>(100*n).toFixed(1)+"%";
 async function api(path,body){const response=await fetch(path,body===undefined?{}:{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});const r=await response.json();if(!response.ok)throw Error(r.error||"Request failed");return r;}
 function download(data,name){const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:"application/json"}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
 function cells(row,values){values.forEach(value=>{const td=document.createElement('td');td.textContent=value;row.append(td);});}
 function controls(){const running=state?.job?.state==='running';$('predict-example').disabled=busy||!state?.ready;$('predict-upload').disabled=busy||!state?.ready||!upload;$('prepare-data').disabled=busy||running;$('train-model').disabled=busy||running||!state?.dataset_ready;$('evaluate-model').disabled=busy||running||!state?.ready||!state?.dataset_ready;}
 function renderStatus(){
  $('ml-status').textContent=state.ready?'Trained model ready / '+state.model.name:'No model yet. Prepare the public dataset and train locally.';
  $('local-training').hidden=!state.training_allowed;$('hosted-training').hidden=state.training_allowed;
  $('training-log').textContent=state.job.message||state.job.state;
  const selected=$('test-example').value;$('test-example').replaceChildren();(state.examples||[]).forEach(e=>{const op=document.createElement('option');op.value=e.id;op.textContent=e.label.replaceAll('_',' ')+' / '+e.id+' / test fold 5';$('test-example').append(op);});if((state.examples||[]).some(e=>e.id===selected))$('test-example').value=selected;$('test-example').disabled=!state.ready;
  const r=state.evaluation;$('ml-metrics').replaceChildren();$('class-report').replaceChildren();
  if(r){[['Test accuracy',r.test_accuracy],['Macro F1',r.test_macro_f1],['Majority baseline',r.majority_baseline_accuracy]].forEach(([name,n])=>{const div=document.createElement('div'),strong=document.createElement('strong');strong.textContent=pct(n);div.textContent=name;div.append(strong);$('ml-metrics').append(div);});
   $('metric-scope').textContent=`${r.test_clips} untouched fold-5 clips / ${r.train_clips} training / ${r.validation_clips} validation. Accuracy 95% source-group bootstrap interval: ${r.test_accuracy_95ci.map(pct).join(' to ')}. Clip predictions average causal window scores. Not onset-detection accuracy.`;
   for(const label of r.classes){const m=r.per_class[label],row=document.createElement('tr');cells(row,[label,pct(m.precision),pct(m.recall),pct(m['f1-score']),m.support]);$('class-report').append(row);}
  }$('download-report').disabled=!r;controls();
 }
 async function refresh(){try{state=await api('/api/ml/status');renderStatus();}catch(e){$('ml-status').textContent=e.message;}}
 async function train(action){try{await api('/api/ml/train',{action});await refresh();}catch(e){$('ml-status').textContent=e.message;}}
 async function predict(body){busy=true;controls();$('prediction-status').textContent='Computing model predictions from the waveform…';try{
  if($('virtual-array').checked)body.virtual={angle:Number($('virtual-angle').value),snr_db:Number($('virtual-snr').value)};
  last=await api('/api/ml/predict',body);$('prediction-summary').hidden=false;$('prediction-summary').replaceChildren();
  const heading=document.createElement('strong');heading.textContent='Model: '+last.prediction.replaceAll('_',' ')+' / '+pct(last.confidence)+' clip-average score';$('prediction-summary').append(heading);
  const truth=document.createElement('p');truth.textContent=last.truth?`Dataset truth: ${last.truth}. ${last.correct?'Prediction matched.':'Prediction did NOT match.'}`:'Uploaded audio: no verified ground-truth label.';$('prediction-summary').append(truth);$('prediction-summary').classList.toggle('bad',last.correct===false);
  const cues=document.createElement('p');cues.textContent=last.alerts.length?last.alerts.map(a=>`${a.message} / ${a.kind==='NONDIR'?'general four-output cue':'virtual direction, motor mask '+a.motors} at ${a.t_ms} ms from clip start`).join('; '):'No DEDA warning accepted. Recognition and warning acceptance are separate.';$('prediction-summary').append(cues);
  const note=document.createElement('p');note.textContent=last.note;$('prediction-summary').append(note);
  $('prediction-windows').replaceChildren();last.windows.forEach(w=>{const row=document.createElement('tr');cells(row,[w.t_ms+' ms',w.prediction,pct(w.confidence),w.direction_deg==null?'Unavailable':Math.round(w.direction_deg)+' deg / '+(w.direction_reliable?'checks pass':'checks fail'),w.alerts.map(a=>a.message+' / '+a.kind).join('; ')||'No new command']);$('prediction-windows').append(row);});
  if(last.audio_b64)$('test-audio').src='data:audio/wav;base64,'+last.audio_b64;else if(audioUrl)$('test-audio').src=audioUrl;
  const canvas=$('test-waveform'),ctx=canvas.getContext('2d');ctx.clearRect(0,0,canvas.width,canvas.height);ctx.strokeStyle='#19775d';ctx.beginPath();last.waveform.forEach((v,i)=>{const x=i/(last.waveform.length-1)*canvas.width,y=45-v*40;i?ctx.lineTo(x,y):ctx.moveTo(x,y);});ctx.stroke();
  $('prediction-status').textContent=`${last.windows.length} real model predictions / ${last.runtime_ms} ms server computation / first prediction after ${last.context_ms} ms of audio. ${last.virtual_geometry?"Direction is synthetic virtual-array evidence.":"No inferred direction."}`;$('download-prediction').disabled=false;
 }catch(e){$('prediction-status').textContent=e.message;}finally{busy=false;controls();}}
 $('prepare-data').addEventListener('click',()=>train('prepare'));$('train-model').addEventListener('click',()=>train('train'));$('evaluate-model').addEventListener('click',()=>train('evaluate'));
 $('predict-example').addEventListener('click',()=>predict({example_id:$('test-example').value}));
 $('test-upload').addEventListener('change',()=>{upload=$('test-upload').files[0]||null;if(upload){if(upload.size>3_000_000){$('prediction-status').textContent='Choose a WAV under 3 MB';upload=null;}else{if(audioUrl)URL.revokeObjectURL(audioUrl);audioUrl=URL.createObjectURL(upload);$('test-audio').src=audioUrl;}}controls();});
 $('predict-upload').addEventListener('click',async()=>{if(!upload)return;const data=await upload.arrayBuffer();let binary='';new Uint8Array(data).forEach(b=>binary+=String.fromCharCode(b));predict({audio_b64:btoa(binary)});});
 $('download-report').addEventListener('click',()=>download(state.evaluation,'soundscape-esc50-evaluation.json'));$('download-prediction').addEventListener('click',()=>download(last,'soundscape-model-prediction.json'));
 refresh();setInterval(()=>{if(state?.job?.state==='running')refresh();},3000);
})();
