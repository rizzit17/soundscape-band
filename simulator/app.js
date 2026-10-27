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
  let result = null, experimentResult = null, reviewResults = [], busy = "", connected = false, hosted = false;
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
    ["run","reset","run-experiment","run-review","suite","seeds","guided-start","guided-fallback","listen-stage","next-demo"].forEach(id => $(id).disabled = Boolean(kind) || !connected);
    document.querySelectorAll("[data-preset],[data-restore]").forEach(b => b.disabled = Boolean(kind) || !connected);
    document.body.classList.toggle("computing",kind === "scene");
    labels();
  }
  async function request(path, payload, timeoutMs = 20000) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(),timeoutMs);
    try {
      const response = await fetch(path, {signal:controller.signal,...(payload === undefined ? {} : {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)})});
      const data = await response.json();
      if (!response.ok) { const e = new Error(data.error || "Request failed"); e.status = response.status; throw e; }
      return data;
    } catch (error) {
      if (error.name === "AbortError") throw new Error(hosted?"The hosted calculation timed out. Try a smaller experiment or retry the scene.":"The engine did not respond in time. Check the Python server and reconnect.");
      if (error instanceof TypeError) throw new Error(location.hostname!=="127.0.0.1" && location.hostname!=="localhost"?"Cannot reach the hosted Python engine. Check your connection and retry.":"Cannot reach Python. Start the simulator server and reconnect.");
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
  let audioContext = null, audioNode = null, audioGain = null, audioBuffer = null;
  let audioEnabled = false, audioAnchor = 0, modelAnchor = 0;
  function silenceAudio() {
    if (audioNode) { try { audioNode.stop(); } catch (_) {} audioNode.disconnect(); audioNode = null; }
    if (audioGain) { audioGain.disconnect(); audioGain = null; }
  }
  async function enableAudio() {
    try {
      const Audio = window.AudioContext || window.webkitAudioContext;
      if (!Audio) throw new Error("Audio playback is unavailable in this browser.");
      if (!audioContext) audioContext = new Audio();
      await audioContext.resume();
      audioEnabled = true;
      $("audio-toggle").setAttribute("aria-pressed","true");text("audio-toggle","Sound on");text("stage-mute","Sound on");$("stage-mute").setAttribute("aria-pressed","true");
      text("audio-status","Ready. Audio follows replay, pause and seek.");
      return true;
    } catch (e) { text("audio-status",e.message + " Visual replay still works."); return false; }
  }
  function startAudio() {
    silenceAudio();
    if (!audioEnabled || !audioContext || !result?.audio) return;
    try {
      if (!audioBuffer) {
        const raw = atob(result.audio.data), bytes = Uint8Array.from(raw,c=>c.charCodeAt(0));
        const view = new DataView(bytes.buffer);
        audioBuffer = audioContext.createBuffer(1,bytes.length/2,result.audio.sample_rate);
        const samples = audioBuffer.getChannelData(0);
        for(let i=0;i<samples.length;i++) samples[i]=view.getInt16(i*2,true)/32768;
      }
      if (replayTime/1000 >= audioBuffer.duration) return;
      audioNode=audioContext.createBufferSource();audioNode.buffer=audioBuffer;
      audioNode.playbackRate.value=Number($("speed").value);
      audioGain=audioContext.createGain();audioGain.gain.value=Number($("volume").value)/100;
      audioNode.connect(audioGain);audioGain.connect(audioContext.destination);
      audioAnchor=audioContext.currentTime;modelAnchor=replayTime;
      audioNode.start(0,replayTime/1000);
      text("audio-status","Playing the computed Mic 1 signal with its noise and reflections.");
    } catch (_) { silenceAudio();text("audio-status","Audio could not play. Visual replay remains available."); }
  }
  function renderStory(f,a) {
    const active=Boolean(f?.source_active), score=f?Math.max(...f.probs.slice(0,4)):0;
    text("story-class",f?`${Math.round(score*100)}%`:"Awaiting input");
    text("story-direction",!f?"Awaiting window":!f.direction_available?"Unavailable":f.reliable?"Checks pass":"Checks fail");
    let step="input", title="Waiting for the sound to begin.", body="The three virtual microphones include background noise. A direction estimate alone does not justify an alert.";
    if(a) {
      step="alert";
      if(a.kind==="NONDIR") {title="The event is accepted. The direction is withheld.";body="DEDA could not establish reliable direction evidence within its decision policy. All four motor commands give a general warning instead of pointing somewhere unsupported.";}
      else {title=`A ${soundNames[result.options.sound].toLowerCase()} warning points ${a.motor_names.join(" and ").toLowerCase()}.`;body="Class evidence and accumulated direction evidence supported this command. Passing checks can still allow an incorrect but plausible direction; compare the outcome above.";}
    } else if(f?.decision.includes("Class accepted")) {step="direction";title="The sound is accepted. Its direction needs more evidence.";body="This is DEDA's separate decision: accepting an event does not automatically accept its direction. The policy waits within a bounded decision budget.";}
    else if(f?.decision.includes("Accumulating")) {step="class";title="Evidence is building across analysis windows.";body="DEDA accumulates class evidence while checking whether direction observations agree. It does not immediately turn every raw angle into a warning.";}
    else if(active && result.options.sound!=="ambient") {step="class";title="You can hear a sound. The class evidence is insufficient.";body="Audibility and classification confidence are different. Here the score is a scripted input; the policy can withhold an alert, which also means an important event can be missed.";}
    else if(result.options.sound==="ambient") {title="Background sound does not trigger this control case.";body="The input is scripted as ambient. This demonstrates the policy's no-alert path, not measured real-world false-alarm performance.";}
    else if(replayTime>=result.offset_ms) {title="The event ended without an accepted warning.";body="Inspect the class input and direction checks to understand the miss. Withholding an uncertain alert has a cost as well as a benefit.";}
    text("story-step",`LIVE EXPLANATION / ${Math.round(replayTime)} MODEL MS`);text("story-title",title);text("story-body",body);
    document.querySelectorAll("[data-stage]").forEach(el=>el.classList.toggle("active",el.dataset.stage===step));
    document.body.classList.toggle("source-sounding",active && playing);
  }
  async function guidedScene(fallback=false) {
    if(busy || !connected) return;
    await enableAudio();
    if(fallback) applySettings(presets.dropout);
    const o=settings();
    if(!result || signature(result.options)!==signature(o)) {const r=await runScene(o);if(!r)return;}
    seek(0);$("scene-title").closest(".stage").scrollIntoView({behavior:"instant",block:"start"});togglePlay();
  }
  function stopReplay() {
    silenceAudio();if(audioEnabled)text("audio-status",replayTime>=result?.duration_ms?"Replay complete. Replay or select another scene.":"Playback paused. Sound resumes with replay.");document.body.classList.remove("replaying","source-sounding");
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
  function renderComparison(f,a,b) {
    [["baseline",b],["deda",a]].forEach(([key,alert])=>{
      const other=key==="baseline"?"Fixed threshold + raw angle":"Separate class and direction evidence";
      text("duel-"+key,alert?(alert.kind==="NONDIR"?"General warning":alert.motor_names.join(" + ")):"No warning yet");
      text("duel-"+key+"-note",alert?`${alert.t_ms-result.onset_ms} ms after onset · ${alert.kind==="NONDIR"?"direction withheld":"direction commanded"}`:other);
      $("duel-"+key).closest("article").classList.toggle("has-alert",Boolean(alert));
    });
    if(!a && f?.decision.includes("Class accepted"))text("duel-deda-note","Class accepted; waiting for direction evidence.");
    const rows=$("class-evidence-bars").children;
    ["Horn","Siren","Shout","Beep"].forEach((name,i)=>{
      const score=f?.evidence[i]??0,row=rows[i],bounded=Math.max(-8,Math.min(8,score));
      row.querySelector("strong").textContent=fmt(score,2);
      const bar=row.querySelector("i");bar.style.width=`${Math.abs(bounded)/8*50}%`;
      bar.style.left=bounded<0?`${50-Math.abs(bounded)/8*50}%`:"50%";
      row.classList.toggle("negative",score<0);
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
    const f=result.frames[index];renderStory(f,a);renderComparison(f,a,b);
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
    if(audioNode) replayTime=modelAnchor+(audioContext.currentTime-audioAnchor)*1000*Number($("speed").value);
    else if(lastTick) replayTime+=(now-lastTick)*Number($("speed").value);lastTick=now;
    if(replayTime>=result.duration_ms){replayTime=result.duration_ms;stopReplay();}
    renderReplay();if(playing)animationId=requestAnimationFrame(tick);
  }
  function togglePlay() {
    if(!result)return;if(playing){stopReplay();return;}if(replayTime>=result.duration_ms){replayTime=0;lastIndex=-2;}
    playing=true;document.body.classList.add("replaying");lastTick=0;startAudio();lastIndex=-2;text("play","Pause");$("play").setAttribute("aria-label","Pause replay");animationId=requestAnimationFrame(tick);
  }
  function showResult(r, remember = true) {
    stopReplay();audioBuffer=null;result=r;const m=r.deda,b=r.baseline;
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
    ["play","next","previous","timeline","export-json","export-csv","stage-pause"].forEach(id=>$(id).disabled=false);
    $("jump-alert").disabled=!r.alerts.some(a=>a.kind!=="UPDATE");
    $("jump-onset").disabled=false;$("jump-end").disabled=false;
    $("jump-baseline").disabled=!r.baseline_alerts.length;$("jump-deda").disabled=!r.alerts.length;
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
    try{const r=await request("/api/simulate",o);showResult(r);status("run-status",`${r.frames.length} computed windows · seed ${r.options.seed}. Paused at the first warning, when available. Use Hear & watch to replay with sound.`);return r;}
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
    if(hosted) {
      $("cancel-experiment").hidden=true;$("progress").removeAttribute("value");
      text("progress-value","Computing in hosted Python…");
      status("experiment-status","Keep this tab open. Hosted experiments return when complete; live progress, cancellation and reload recovery are available in the local version.");
      try {
        experimentResult=await request("/api/experiment",{suite:$("suite").value,seeds:Number($("seeds").value)},150000);
        experimentDisplay();$("progress").max=experimentResult.trials.length;$("progress").value=experimentResult.trials.length;
        text("progress-value",`${experimentResult.trials.length} / ${experimentResult.trials.length} trials`);
        status("experiment-status",`Completed ${experimentResult.trials.length} trials in hosted Python. Results and exports are ready.`);
      } catch(e) {status("experiment-status",e.message,true);$("experiment-progress").hidden=true;}
      finally {setBusy();}
      return;
    }
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
      const health=await request("/api/health");if(health.status!=="ok")throw new Error("Engine is unavailable");connected=true;hosted=health.execution==="serverless";if(hosted)rememberJob(null);text("connection",hosted?"Hosted Python engine connected":"Python engine connected");$("connection").className="online";$("reconnect").hidden=true;setBusy(busy);renderHistory();
      if(jobId){setBusy("experiment");$("cancel-experiment").hidden=false;$("cancel-experiment").disabled=false;tab("experiment");pollJob();}
      else if(!result&&!busy){applySettings(defaults);runScene();}
    } catch(e){connected=false;text("connection","Python server unavailable");$("connection").className="error";$("reconnect").hidden=false;setBusy(busy);status("run-status",location.hostname!=="127.0.0.1" && location.hostname!=="localhost"?"Hosted engine unavailable. Try Reconnect in a moment.":"Start-Simulator.cmd starts the local engine. Then select Reconnect.",true);}
  }

  $("scene-form").noValidate=true;
  $("scene-form").addEventListener("submit",async e=>{
    e.preventDefault();
    if(busy || !connected)return;
    // A user-triggered run should visibly replay, even when settings are unchanged.
    if(audioEnabled && audioContext)await audioContext.resume().catch(()=>{});
    const r=await runScene();
    if(!r)return;
    seek(0);$("scene-title").closest(".stage").scrollIntoView({behavior:"instant",block:"start"});togglePlay();
    status("run-status",`${r.frames.length} computed windows · replay started from the beginning${audioEnabled?" with sound":" (sound muted)"}.`);
  });
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
  ["Horn","Siren","Shout","Beep"].forEach(name=>{
    const row=document.createElement("div"),label=document.createElement("span"),track=document.createElement("div"),bar=document.createElement("i"),value=document.createElement("strong");
    label.textContent=name;track.className="evidence-track";track.append(bar);value.textContent="0.00";row.append(label,track,value);$("class-evidence-bars").append(row);
  });
  $("presentation-toggle").addEventListener("click",()=>{
    const active=document.body.classList.toggle("presentation-mode");
    $("presentation-toggle").setAttribute("aria-pressed",String(active));text("presentation-toggle",active?"Exit presentation":"Presentation mode");
    if(active)tab("demo");
    if(active)$("scene-title").closest(".stage").scrollIntoView({behavior:"instant",block:"start"});
  });
  $("jump-onset").addEventListener("click",()=>seek(result.onset_ms));
  $("jump-end").addEventListener("click",()=>seek(result.duration_ms));
  $("jump-baseline").addEventListener("click",()=>seek(result.baseline_alerts[0].t_ms));
  $("jump-deda").addEventListener("click",()=>seek(result.alerts[0].t_ms));
  $("stage-pause").addEventListener("click",togglePlay);
  $("stage-mute").addEventListener("click",()=>$("audio-toggle").click());
  $("listen-stage").addEventListener("click",()=>guidedScene());
  $("next-demo").addEventListener("click",()=>{
    const keys=["horn","siren","dropout","weak","ambient"];
    const current=keys.findIndex(k=>result && signature(presets[k])===signature(result.options));
    applySettings(presets[keys[(current+1)%keys.length]]);guidedScene();
  });
  $("guided-start").addEventListener("click",()=>guidedScene());
  $("guided-fallback").addEventListener("click",()=>guidedScene(true));
  $("audio-toggle").addEventListener("click",async()=>{
    if(audioEnabled){audioEnabled=false;silenceAudio();text("audio-toggle","Sound off");text("stage-mute","Sound off");$("stage-mute").setAttribute("aria-pressed","false");$("audio-toggle").setAttribute("aria-pressed","false");text("audio-status","Muted. Visual replay continues.");}
    else if(await enableAudio()) {if(playing)startAudio();}
  });
  $("volume").addEventListener("input",()=>{text("volume-value",`${$("volume").value}%`);if(audioGain)audioGain.gain.setTargetAtTime(Number($("volume").value)/100,audioContext.currentTime,.02);});
  $("speed").addEventListener("change",()=>{if(playing){lastTick=0;startAudio();}});
  document.addEventListener("visibilitychange",()=>{if(document.hidden)stopReplay();});
  renderHistory();renderReview();trialCount();waveforms(null);setBusy();connect();
})();
