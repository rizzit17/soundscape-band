"use strict";
(() => {
  // Pure projections shared by the browser and the small Node verification suite.
  function frameIndex(frames, time) {
    let low = 0, high = frames.length;
    while (low < high) { const mid = (low + high) >> 1; if (frames[mid].t_ms <= time) low = mid + 1; else high = mid; }
    return low - 1;
  }
  function outcomeText(m) {
    if (!m.critical) return m.false_alerts ? "Unexpected alert" : "No critical event";
    if (!m.detected) return "No accepted warning";
    if (m.nondirectional) return "General warning";
    return m.wrong_direction ? "Wrong direction" : "Direction matched";
  }
  function reviewMatches(kind, r) {
    const m = r.deda;
    if (kind === "ambient") return !m.critical && r.alerts.length === 0;
    if (kind === "weak") return m.critical && !m.detected && r.alerts.length === 0;
    if (kind === "dropout") return m.detected && m.nondirectional && m.first_alert.motors === 15;
    return m.detected && !m.nondirectional && !m.wrong_direction && m.correct_class;
  }
  if (typeof module !== "undefined" && module.exports) { module.exports = {frameIndex, outcomeText, reviewMatches}; return; }

  const $ = id => document.getElementById(id);
  const soundNames = {horn:"Vehicle horn", siren:"Siren", shout:"Shout-like noise", beep:"Reversing beep", ambient:"Ambient noise"};
  const conditionNames = {clean:"Single source", interference:"Competing sources", reflection:"Reflection surrogate", clock_fault:"Timing fault", dropout:"Direction dropout"};
  const motorNames = ["Front", "Right", "Back", "Left"];
  const fmt = (n, digits = 1) => n == null || !Number.isFinite(Number(n)) ? "—" : Number(n).toFixed(digits);
  const angleName = a => motorNames[Math.floor(((a % 360) + 360) / 90 + .5) % 4];
  const defaults = {sound:"horn", angle:180, snr_db:20, condition:"clean", confidence:.95, seed:7, active_frac:.25, event_ms:1024};
  const presets = {
    horn:{...defaults}, siren:{...defaults,sound:"siren",angle:270}, dropout:{...defaults,condition:"dropout"},
    weak:{...defaults,confidence:.30}, ambient:{...defaults,sound:"ambient",angle:0,snr_db:0},
    interference:{...defaults,condition:"interference",snr_db:0,angle:90}
  };
  const cases = [
    {key:"horn",name:"Horn behind",expected:"Directional warning towards Back"},
    {key:"siren",name:"Siren left",expected:"Directional warning towards Left"},
    {key:"dropout",name:"Direction unavailable",expected:"Accepted class → all four motors"},
    {key:"weak",name:"Uncertain class",expected:"No accepted warning at score 0.30"},
    {key:"ambient",name:"Ambient control",expected:"No warning with the scripted ambient input"}
  ];
  let result = null, experimentResult = null, reviewResults = [], busy = "", connected = false;
  let playing = false, replayTime = 0, lastTick = 0, lastIndex = -2, animationId = null;
  let jobId = null, pollTimer = null, pollInFlight = false;
  let history = [];
  try { history = JSON.parse(localStorage.getItem("soundscape-scenes-v2") || "[]"); } catch (_) { /* Private storage can be unavailable. */ }
  if (!Array.isArray(history)) history = [];
  history = history.filter(h => h && h.options && soundNames[h.options.sound] && conditionNames[h.options.condition] && h.deda && h.baseline).slice(0,6);
  try { const saved = sessionStorage.getItem("soundscape-job"); if (/^[a-f0-9]{32}$/.test(saved || "")) jobId = saved; } catch (_) { /* Optional recovery only. */ }

  function text(id, value) { $(id).textContent = value; }
  function settings() {
    return {sound:$("sound").value,angle:Number($("angle").value),snr_db:Number($("snr").value),condition:$("condition").value,
      confidence:Number($("confidence").value)/100,seed:Number($("seed").value),active_frac:Number($("bins").value),event_ms:Number($("duration").value)};
  }
  function signature(o) { return JSON.stringify(Object.keys(defaults).map(k => o[k])); }
  function applySettings(o) {
    const ids = {sound:"sound",angle:"angle",snr_db:"snr",condition:"condition",seed:"seed",active_frac:"bins",event_ms:"duration"};
    Object.entries(ids).forEach(([key,id]) => $(id).value = o[key]);
    $("confidence").value = Math.round(o.confidence*100); labels();
  }
  function labels() {
    const ambient = $("sound").value === "ambient";
    text("angle-value",ambient ? "Not applicable" : `${$("angle").value}° · ${angleName(+$("angle").value)}`);
    text("snr-value",ambient ? "Not used" : `${$("snr").value} dB`);
    text("confidence-value",ambient ? "96% ambient" : `${$("confidence").value}%`);
    ["angle","snr","confidence"].forEach(id => $(id).disabled = ambient);
    document.querySelectorAll("[data-angle]").forEach(b => b.disabled = ambient || Boolean(busy));
    $("stale").hidden = !result || signature(settings()) === signature(result.options);
    document.querySelectorAll("[data-preset]").forEach(b => b.classList.toggle("selected",signature(settings()) === signature(presets[b.dataset.preset])));
  }
  function setBusy(kind = "") {
    busy = kind;
    $("scene-fields").disabled = Boolean(kind) || !connected;
    ["run","reset","run-experiment","run-review","suite","seeds"].forEach(id => $(id).disabled = Boolean(kind) || !connected);
    document.querySelectorAll("[data-preset],[data-restore]").forEach(b => b.disabled = Boolean(kind) || !connected);
    document.body.classList.toggle("computing",kind === "scene");
    labels();
  }
  async function request(path, payload) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(),20000);
    try {
      const response = await fetch(path, {signal:controller.signal,...(payload === undefined ? {} : {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)})});
      const data = await response.json();
      if (!response.ok) { const e = new Error(data.error || "Request failed"); e.status = response.status; throw e; }
      return data;
    } catch (error) {
      if (error.name === "AbortError") throw new Error("The engine did not respond in time. Check the Python server and reconnect.");
      if (error instanceof TypeError) throw new Error("Cannot reach Python. Start the simulator server and reconnect.");
      throw error;
    } finally { clearTimeout(timeout); }
  }
  function status(id, message, error = false) { text(id,message); $(id).classList.toggle("error",error); }
  function download(data, filename, type) {
    const url = URL.createObjectURL(new Blob([data],{type})); const a = document.createElement("a");
    a.href=url; a.download=filename; document.body.append(a); a.click(); a.remove(); setTimeout(()=>URL.revokeObjectURL(url),3000);
  }
  function exportData(data, format, prefix) {
    if (!data) return;
    const stamp = new Date().toISOString().replace(/[:.]/g,"-");
    if (format === "csv") download(data.csv,`${prefix}-${stamp}.csv`,"text/csv;charset=utf-8");
    else { const {csv,...rest}=data; download(JSON.stringify(rest,null,2),`${prefix}-${stamp}.json`,"application/json"); }
  }
  function cells(row, values) { values.forEach(v => {const td=document.createElement("td");td.textContent=v;row.append(td);}); }
  function stopReplay() {
    playing=false; if(animationId!==null) cancelAnimationFrame(animationId); animationId=null; lastTick=0;
    text("play","Play"); $("play").setAttribute("aria-label","Play replay");
  }
  function seek(time) { if (!result) return; stopReplay(); replayTime=Math.max(0,Math.min(result.duration_ms,time)); renderReplay(); }
  function badge(id,label,mode) { text(id,label); $(id).classList.toggle("good",mode === "good"); $(id).classList.toggle("fail",mode === "fail"); }
  function waveforms(frame) {
    const canvas=$("waveforms"),ctx=canvas.getContext("2d"),w=canvas.width,h=canvas.height;
    ctx.clearRect(0,0,w,h);
    const rows=frame ? frame.waveform : [[],[],[]],peak=Math.max(1e-6,...rows.flat().map(Math.abs));
    rows.forEach((values,i)=>{
      const y=h*(i+.5)/3;ctx.strokeStyle="#e4e9e2";ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(w,y);ctx.stroke();
      ctx.strokeStyle=["#176b50","#36949b","#8b9b68"][i];ctx.lineWidth=1.7;ctx.beginPath();
      values.forEach((v,k)=>{const x=k*w/Math.max(1,values.length-1),yy=y-v/peak*24;k?ctx.lineTo(x,yy):ctx.moveTo(x,yy);});ctx.stroke();
    });
  }
  function renderReplay() {
    if (!result) return;
    $("timeline").value=replayTime; text("time-value",`${Math.round(replayTime)} / ${result.duration_ms} ms`);
    const index=frameIndex(result.frames,replayTime);
    $("previous").disabled=replayTime<=0; $("next").disabled=replayTime>=result.duration_ms;
    if(index===lastIndex) return; lastIndex=index;
    const latest = alerts => alerts.filter(a=>a.t_ms<=replayTime).at(-1);
    const a=latest(result.alerts),b=latest(result.baseline_alerts);
    [1,2,4,8].forEach(bit=>$("motor-"+bit).classList.toggle("on",Boolean(a && a.motors & bit)));
    text("motor-readout",a ? a.motor_names.join(" + ") : "No alert yet");
    badge("alert-badge",a ? a.kind==="NONDIR"?"General warning":a.kind==="UPDATE"?"Direction update":"Directional warning" : "No alert yet",a?"good":"");
    text("baseline-decision",b ? `${b.motor_names.join(" + ")} · ${b.t_ms} ms` : "No alert yet");
    document.querySelectorAll("#log tr.current").forEach(r=>r.classList.remove("current"));
    if(index>=0 && $("log").children[index]) $("log").children[index].classList.add("current");
    const f=result.frames[index];
    if(!f) {
      text("estimated-value","—");badge("reliability-value","Before first window","");$("estimated-direction").style.display="none";
      text("decision","Waiting for the first analysis window");text("reason","Source onset is 192 ms on the simulated clock.");
      text("source-active","Not yet");text("current-class","—");waveforms(null);
    } else {
      const d=f.direction,available=f.direction_available;
      text("estimated-value",available?`${fmt(d.theta_deg,0)}°`:"Unavailable");
      badge("reliability-value",available?(f.reliable?"Checks pass":"Checks fail"):"No direction",f.reliable?"good":"fail");
      $("estimated-direction").style.display=available?"":"none";$("estimated-direction").setAttribute("transform",`rotate(${d.theta_deg} 200 200)`);
      text("decision",f.decision);
      let reasons=f.reasons.join(". ");
      if(Math.max(...f.probs.slice(0,4))<result.config.p_open) reasons += ". Critical-class score is below the episode-opening threshold.";
      text("reason",reasons);text("source-active",f.source_active?"Yes":"No");
      const top=Math.max(...f.probs),cls=f.probs.indexOf(top);
      text("current-class",`${["Horn","Siren","Shout","Beep","Ambient"][cls]} · ${fmt(top*100,0)}%`);
      text("signal-note",`Window ${index+1} · amplitude normalized for display`);waveforms(f);
    }
    const d=f?.direction,available=Boolean(f?.direction_available);
    [["closure",d?.closure,d?.closure<=.75,(d?.closure||0)/1.5*100,2],["norm",d?.norm,d?.norm>=.6 && d?.norm<=1.4,(d?.norm||0)/2*100,2],["coherence",d?.coherence,d?.coherence>=.3,(d?.coherence||0)*100,2]].forEach(([id,value,pass,width,digits])=>{
      text(id+"-value",available?fmt(value,digits):"—");$("check-"+id).classList.toggle("fail",available&&!pass);
      $("check-"+id).querySelector(".meter i").style.width=`${available?Math.min(100,Math.max(0,width)):0}%`;
    });
    text("window-note",`${index<0?"Before first window":`Window ${index+1} of ${result.frames.length}`} · source ${result.onset_ms}–${result.offset_ms} ms`);
  }
  function tick(now) {
    animationId=null;if(!playing||!result)return;
    if(lastTick) replayTime+=(now-lastTick)*Number($("speed").value);lastTick=now;
    if(replayTime>=result.duration_ms){replayTime=result.duration_ms;stopReplay();}
    renderReplay();if(playing)animationId=requestAnimationFrame(tick);
  }
  function togglePlay() {
    if(!result)return;if(playing){stopReplay();return;}if(replayTime>=result.duration_ms){replayTime=0;lastIndex=-2;}
    playing=true;lastTick=0;text("play","Pause");$("play").setAttribute("aria-label","Pause replay");animationId=requestAnimationFrame(tick);
  }
  function showResult(r, remember = true) {
    stopReplay();result=r;const m=r.deda,b=r.baseline;
    text("scene-title",`${soundNames[r.options.sound]} · ${r.options.sound==="ambient"?"ambient control":r.options.angle+"° · "+r.options.snr_db+" dB"}`);
    text("latency",!m.critical?"No event":m.detected?`${m.latency_ms} ms`:"No warning");
    text("latency-note",!m.critical?"Ambient control":!m.detected?"Critical event was not accepted":m.missed_or_late?"Later than 300 ms on the model clock":"Within 300 ms on the model clock");
    $("latency").classList.toggle("bad",m.critical && m.missed_or_late);
    text("correct",outcomeText(m));$("correct").classList.toggle("bad",Boolean(m.wrong_direction));
    text("class-summary",m.critical?m.detected?(m.correct_class?"First alert class matched":"First alert class did not match"):"Class evidence not accepted":"Scripted ambient probabilities");
    text("baseline-latency",!b.critical?"No event":b.detected?`${b.latency_ms} ms`:"No warning");text("baseline-summary",outcomeText(b));
    $("true-direction").setAttribute("transform",`rotate(${r.options.angle} 200 200)`);$("true-direction").style.display=m.critical?"":"none";
    text("scene-explanation",r.options.sound==="ambient"?"This control uses a fixed ambient probability of 0.96 and no false-class confusers. No alert here is not evidence of classifier accuracy.":`${conditionNames[r.options.condition]}. The scripted ${soundNames[r.options.sound].toLowerCase()} score is ${Math.round(r.options.confidence*100)}%; the direction and motor commands are computed from synthetic microphone signals.`);
    text("runtime",`Seed ${r.options.seed} · engine computation ${fmt(r.runtime_ms,0)} ms · no hardware timing`);
    $("source-range").style.left=`${r.onset_ms/r.duration_ms*100}%`;$("source-range").style.width=`${(r.offset_ms-r.onset_ms)/r.duration_ms*100}%`;$("source-range").style.right="auto";
    $("timeline").max=r.duration_ms;$("timeline").step=r.hop_ms;
    ["play","next","previous","timeline","export-json","export-csv"].forEach(id=>$(id).disabled=false);
    $("jump-alert").disabled=!r.alerts.some(a=>a.kind!=="UPDATE");
    $("log").replaceChildren();
    r.frames.forEach(f=>{
      const row=document.createElement("tr"),td=document.createElement("td"),button=document.createElement("button");
      button.className="row-button";button.dataset.time=f.t_ms;button.textContent=`${f.t_ms} ms`;button.setAttribute("aria-label",`Inspect window ending ${f.t_ms} ms`);td.append(button);row.append(td);
      const top=Math.max(...f.probs),cls=f.probs.indexOf(top);
      cells(row,[`${["Horn","Siren","Shout","Beep","Ambient"][cls]} · ${fmt(top*100,0)}%`,f.direction_available?`${fmt(f.direction.theta_deg)}°`:"Unavailable",f.direction_available?(f.reliable?"Pass":"Fail"):"Unavailable",f.alerts.length?f.alerts.map(a=>`${a.kind} → ${a.motor_names.join(" + ")}`).join("; "):f.decision]);$("log").append(row);
    });
    replayTime=r.alerts.find(a=>a.kind!=="UPDATE")?.t_ms ?? r.onset_ms+r.hop_ms;lastIndex=-2;renderReplay();labels();
    if(remember){history.unshift({options:r.options,deda:r.deda,baseline:r.baseline,created:new Date().toISOString()});history=history.slice(0,6);try{localStorage.setItem("soundscape-scenes-v2",JSON.stringify(history));}catch(_){}renderHistory();}
  }
  async function runScene(o = settings()) {
    if(busy||!connected)return;
    if(!$("seed").checkValidity())$("seed").closest("details").open=true;
    if(!$("scene-form").reportValidity())return;
    stopReplay();setBusy("scene");status("run-status","Computing the microphone signals, direction and decision…");
    try{const r=await request("/api/simulate",o);showResult(r);status("run-status",`${r.frames.length} computed windows · seed ${r.options.seed}. Paused at the first warning, when available.`);}
    catch(e){status("run-status",e.message,true);}finally{setBusy();}
  }
  function renderHistory() {
    $("history").replaceChildren();$("history-csv").disabled=!history.length;
    if(!history.length){const row=document.createElement("tr"),cell=document.createElement("td");cell.colSpan=5;cell.className="empty";cell.textContent="Computed scene summaries will appear here.";row.append(cell);$("history").append(row);return;}
    history.forEach((h,i)=>{const row=document.createElement("tr");cells(row,[`${soundNames[h.options.sound]} · ${h.options.angle}°`,conditionNames[h.options.condition],`${outcomeText(h.deda)}${h.deda.latency_ms==null?"":" · "+h.deda.latency_ms+" ms"}`,`${outcomeText(h.baseline)}${h.baseline.latency_ms==null?"":" · "+h.baseline.latency_ms+" ms"}`]);const cell=document.createElement("td"),button=document.createElement("button");button.textContent="Restore settings";button.dataset.restore=i;button.disabled=Boolean(busy)||!connected;cell.append(button);row.append(cell);$("history").append(row);});
  }
  function tab(name, focus = false) {
    stopReplay();["demo","experiment","review"].forEach(n=>{const active=n===name;$(n+"-view").hidden=!active;$(n+"-tab").classList.toggle("active",active);$(n+"-tab").setAttribute("aria-selected",String(active));$(n+"-tab").tabIndex=active?0:-1;});
    if(focus)$(name+"-tab").focus();
  }
  function trialCount(){const seeds=Number($("seeds").value),critical=($("suite").value==="full"?192:32)*seeds;text("trial-count",`${critical} critical cases + ${seeds} ambient control${seeds===1?"":"s"}.`);}
  function experimentDisplay() {
    const r=experimentResult,p=r.policies;$("experiment-empty").hidden=true;$("experiment-data").hidden=false;
    text("experiment-caption",`${r.suite==="full"?"Full":"Quick"} matrix · ${r.seeds} seed${r.seeds===1?"":"s"} · ${r.trials.length} trials · ${fmt(r.runtime_ms/1000)} s computation`);
    const fields=[["Critical events","events",0,""],["Detected events","detected",0,""],["Wrong direction / all critical events","wrong_direction_pct",1,"%"],["Missed events","missed_pct",1,"%"],["Missed or later than 300 ms","missed_or_late_pct",1,"%"],["General first warnings / detections","nondirectional_pct",1,"%"],["Median simulated first-warning delay","latency_p50_ms",1," ms"],["95th percentile simulated delay","latency_p95_ms",1," ms"]];
    $("experiment-table").replaceChildren();fields.forEach(([label,key,digits,unit])=>{const row=document.createElement("tr");cells(row,[label,...["baseline","deda"].map(n=>p[n][key]==null?"—":fmt(p[n][key],digits)+unit)]);$("experiment-table").append(row);});
    $("comparison-chart").replaceChildren();
    [["Wrong-direction alerts","wrong_direction_pct"],["Missed or late events","missed_or_late_pct"]].forEach(([label,key])=>{const group=document.createElement("div");group.className="chart-group";const heading=document.createElement("strong");heading.textContent=label;group.append(heading);["baseline","deda"].forEach(n=>{const row=document.createElement("div"),name=document.createElement("span"),bar=document.createElement("div"),fill=document.createElement("i"),number=document.createElement("span");row.className="chart-row";name.textContent=n==="deda"?"DEDA":"Baseline B";bar.className="chart-bar";fill.style.width=`${Math.max(0,Math.min(100,p[n][key]??0))}%`;bar.append(fill);number.textContent=fmt(p[n][key])+"%";row.append(name,bar,number);group.append(row);});$("comparison-chart").append(group);});
    $("breakdown").replaceChildren();Object.keys(conditionNames).forEach(condition=>{const trials=r.trials.filter(t=>t.options.condition===condition && t.deda.critical);if(!trials.length)return;const pct=(policy,key)=>fmt(100*trials.filter(t=>t[policy][key]).length/trials.length)+"%";const row=document.createElement("tr");cells(row,[conditionNames[condition],trials.length,pct("baseline","wrong_direction"),pct("deda","wrong_direction"),pct("deda","missed_or_late")]);$("breakdown").append(row);});
    text("experiment-note",`Ambient exposure is only ${fmt(p.deda.ambient_hours*3600,2)} seconds. It contains scripted ambient probabilities with no false-class confusers. Ambient false alerts/h: B ${fmt(p.baseline.false_alerts_per_ambient_hour)}, DEDA ${fmt(p.deda.false_alerts_per_ambient_hour)}. These rates do not evaluate recognition or establish real-world false-alarm performance. Default thresholds are uncalibrated; this is separate from the paper benchmark.`);
    $("experiment-json").disabled=false;$("experiment-csv").disabled=false;
  }
  function rememberJob(id) {jobId=id;try{if(id)sessionStorage.setItem("soundscape-job",id);else sessionStorage.removeItem("soundscape-job");}catch(_){}}
  function finishJob(){if(pollTimer)clearTimeout(pollTimer);pollTimer=null;rememberJob(null);$("cancel-experiment").hidden=true;setBusy();}
  async function pollJob() {
    if(!jobId||pollInFlight)return;pollInFlight=true;
    try {
      const job=await request("/api/experiment/status?id="+encodeURIComponent(jobId));
      $("experiment-progress").hidden=false;$("progress").max=job.total;$("progress").value=job.completed;text("progress-value",`${job.completed} / ${job.total} trials · ${Math.round(job.completed/job.total*100)}%`);
      if(job.state==="complete"){experimentResult=job.result;experimentDisplay();status("experiment-status",`Completed ${job.total} trials. Results and exports are ready.`);finishJob();}
      else if(job.state==="cancelled"){status("experiment-status",`Cancelled after ${job.completed} of ${job.total} trials. No partial rates are published.`);finishJob();}
      else if(job.state==="failed"){status("experiment-status",job.error,true);finishJob();}
      else status("experiment-status","Computing real trials in Python. You can cancel between trials.");
    } catch(e) {
      status("experiment-status",e.message+" Retrying status…",true);
      if(e.status===404){finishJob();status("experiment-status",e.message+" Start a new experiment.",true);}
    } finally {pollInFlight=false;if(jobId)pollTimer=setTimeout(pollJob,900);}
  }
  async function runExperiment() {
    if(busy||!connected)return;stopReplay();setBusy("experiment");experimentResult=null;$("experiment-data").hidden=true;$("experiment-empty").hidden=false;
    $("experiment-json").disabled=true;$("experiment-csv").disabled=true;$("experiment-progress").hidden=false;$("progress").value=0;text("progress-value","Preparing trials…");status("experiment-status","Starting the trial matrix…");
    try{const job=await request("/api/experiment/start",{suite:$("suite").value,seeds:Number($("seeds").value)});rememberJob(job.id);$("cancel-experiment").hidden=false;$("cancel-experiment").disabled=false;pollJob();}
    catch(e){status("experiment-status",e.message,true);setBusy();}
  }
  function renderReview() {
    $("review-table").replaceChildren();cases.forEach((c,i)=>{
      const r=reviewResults[i],row=document.createElement("tr");cells(row,[c.name,c.expected,r?`${outcomeText(r.deda)}${r.deda.latency_ms==null?"":" · "+r.deda.latency_ms+" ms"}`:"Not run"]);
      const check=document.createElement("td"),label=document.createElement("span");label.className="badge"+(r?(reviewMatches(c.key,r)?" good":" fail"):"");label.textContent=r?(reviewMatches(c.key,r)?"As expected":"Inspect result"):"Pending";check.append(label);row.append(check);
      const evidence=document.createElement("td"),button=document.createElement("button");button.textContent="Inspect scene";button.disabled=!r||Boolean(busy);button.dataset.inspect=i;evidence.append(button);row.append(evidence);$("review-table").append(row);
    });$("review-json").disabled=!reviewResults.length||Boolean(busy);$("print-review").disabled=!reviewResults.length||Boolean(busy);
  }
  async function runReview() {
    if(busy||!connected)return;stopReplay();reviewResults=[];setBusy("review");renderReview();
    try{for(const c of cases){status("review-status",`Computing ${reviewResults.length+1} of ${cases.length}: ${c.name}…`);reviewResults.push(await request("/api/simulate",presets[c.key]));renderReview();}const expected=reviewResults.filter((r,i)=>reviewMatches(cases[i].key,r)).length;status("review-status",`${expected} of ${cases.length} behaviors matched the stated expectations. This is a scene check, not an accuracy score.`);}
    catch(e){status("review-status",e.message+" Completed evidence is retained below.",true);}finally{setBusy();renderReview();}
  }
  async function connect() {
    try {
      const health=await request("/api/health");if(health.status!=="ok")throw new Error("Engine is unavailable");connected=true;text("connection","Python engine connected");$("connection").className="online";$("reconnect").hidden=true;setBusy(busy);renderHistory();
      if(jobId){setBusy("experiment");$("cancel-experiment").hidden=false;$("cancel-experiment").disabled=false;tab("experiment");pollJob();}
      else if(!result&&!busy){applySettings(defaults);runScene();}
    } catch(e){connected=false;text("connection","Python server unavailable");$("connection").className="error";$("reconnect").hidden=false;setBusy(busy);status("run-status","Start-Simulator.cmd starts the local engine. Then select Reconnect.",true);}
  }

  $("scene-form").noValidate=true;
  $("scene-form").addEventListener("submit",e=>{e.preventDefault();runScene();});
  $("scene-form").addEventListener("input",labels);$("scene-form").addEventListener("change",labels);
  $("reset").addEventListener("click",()=>{applySettings(defaults);status("run-status","Default settings restored. Run the scene to recompute.");});
  document.querySelectorAll("[data-angle]").forEach(b=>b.addEventListener("click",()=>{$("angle").value=b.dataset.angle;labels();}));
  $("compass").addEventListener("click",e=>{if(busy||!connected||$("sound").value==="ambient")return;const point=new DOMPoint(e.clientX,e.clientY).matrixTransform($("compass").getScreenCTM().inverse());if(Math.hypot(point.x-200,point.y-200)<45)return;$("angle").value=Math.round((Math.atan2(point.x-200,200-point.y)*180/Math.PI+360)%360)%360;labels();});
  document.querySelectorAll("[data-preset]").forEach(b=>b.addEventListener("click",()=>{applySettings(presets[b.dataset.preset]);runScene();}));
  $("timeline").addEventListener("input",()=>seek(Number($("timeline").value)));$("play").addEventListener("click",togglePlay);
  $("previous").addEventListener("click",()=>seek((Math.ceil(replayTime/result.hop_ms)-1)*result.hop_ms));$("next").addEventListener("click",()=>seek((Math.floor(replayTime/result.hop_ms)+1)*result.hop_ms));
  $("jump-alert").addEventListener("click",()=>{const a=result?.alerts.find(a=>a.kind!=="UPDATE");if(a)seek(a.t_ms);});
  $("log").addEventListener("click",e=>{const button=e.target.closest("[data-time]");if(button)seek(Number(button.dataset.time));});
  $("export-json").addEventListener("click",()=>exportData(result,"json","soundscape-scene"));$("export-csv").addEventListener("click",()=>exportData(result,"csv","soundscape-windows"));
  $("history").addEventListener("click",e=>{const b=e.target.closest("[data-restore]");if(b&&!busy){applySettings(history[Number(b.dataset.restore)].options);status("run-status","Saved settings restored. Run the scene to recompute with the same seed.");}});
  $("history-csv").addEventListener("click",()=>{const quote=v=>'"'+String(v??"").replaceAll('"','""')+'"';const rows=[["created_utc","sound","condition","angle","snr_db","class_score","seed","policy","detected","wrong_direction","nondirectional","latency_ms"]];history.forEach(h=>["baseline","deda"].forEach(n=>rows.push([h.created,h.options.sound,h.options.condition,h.options.angle,h.options.snr_db,h.options.confidence,h.options.seed,n,h[n].detected,h[n].wrong_direction,h[n].nondirectional,h[n].latency_ms])));download(rows.map(row=>row.map(quote).join(",")).join("\r\n"),"soundscape-scene-comparisons.csv","text/csv;charset=utf-8");});
  ["demo","experiment","review"].forEach((name,i)=>{$(name+"-tab").addEventListener("click",()=>tab(name));$(name+"-tab").addEventListener("keydown",e=>{const tabs=["demo","experiment","review"];if(["ArrowRight","ArrowLeft","Home","End"].includes(e.key)){e.preventDefault();const index=e.key==="Home"?0:e.key==="End"?2:(i+(e.key==="ArrowRight"?1:2))%3;tab(tabs[index],true);}});});
  $("suite").addEventListener("change",trialCount);$("seeds").addEventListener("change",trialCount);$("run-experiment").addEventListener("click",runExperiment);
  $("cancel-experiment").addEventListener("click",async()=>{if(!jobId)return;$("cancel-experiment").disabled=true;try{await request("/api/experiment/cancel",{id:jobId});status("experiment-status","Cancellation requested. Finishing the current trial…");}catch(e){status("experiment-status",e.message,true);$("cancel-experiment").disabled=false;}});
  $("experiment-json").addEventListener("click",()=>exportData(experimentResult,"json","soundscape-experiment"));$("experiment-csv").addEventListener("click",()=>exportData(experimentResult,"csv","soundscape-trials"));
  $("run-review").addEventListener("click",runReview);$("review-table").addEventListener("click",e=>{const b=e.target.closest("[data-inspect]");if(b&&!busy){const r=reviewResults[Number(b.dataset.inspect)];applySettings(r.options);showResult(r,false);tab("demo");status("run-status","Inspecting the exact computed review-case trace.");window.scrollTo({top:0,behavior:"instant"});}});
  $("review-json").addEventListener("click",()=>exportData({schema_version:1,scope:"Synthetic scene checks, not recognition accuracy or hardware validation",created_utc:new Date().toISOString(),cases:reviewResults.map((r,i)=>({case:cases[i].name,expected:cases[i].expected,matched:reviewMatches(cases[i].key,r),result:r}))},"json","soundscape-review-evidence"));
  $("print-review").addEventListener("click",()=>window.print());$("reconnect").addEventListener("click",connect);
  document.addEventListener("visibilitychange",()=>{if(document.hidden)stopReplay();});
  renderHistory();renderReview();trialCount();waveforms(null);setBusy();connect();
})();
