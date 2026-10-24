"use strict";
const $ = id => document.getElementById(id);
let result = null, experimentResult = null, playing = false, replayTime = 0, lastTick = 0, lastIndex = -1, busy = false, animationId = null;
const names = ["Front", "Right", "Back", "Left"];
const angleName = angle => names[Math.floor((angle % 360) / 90 + .5) % 4];
const fmt = (n, digits=1) => n === null || n === undefined ? "—" : Number(n).toFixed(digits);
const presets = {
  horn: {sound:"horn", angle:180, snr:20, condition:"clean", confidence:95},
  siren: {sound:"siren", angle:270, snr:20, condition:"clean", confidence:95},
  dropout: {sound:"horn", angle:180, snr:20, condition:"dropout", confidence:95},
  ambient: {sound:"ambient", angle:0, snr:0, condition:"clean", confidence:95},
  interference: {sound:"horn", angle:90, snr:0, condition:"interference", confidence:95}
};
function labels() {
  $("angle-value").textContent = `${$("angle").value}° · ${angleName(+$("angle").value)}`;
  $("snr-value").textContent = `${$("snr").value} dB`;
  $("confidence-value").textContent = `${$("confidence").value}%`;
}
["angle", "snr", "confidence"].forEach(id => $(id).addEventListener("input", labels));
function setBusy(value) {
  busy = value;
  ["run", "run-experiment", ...Object.keys(presets).map(p=>p)].forEach(id => { if ($(id)) $(id).disabled = value; });
  document.querySelectorAll("[data-preset]").forEach(b=>b.disabled=value);
}
async function api(path, payload) {
  const response = await fetch(path, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload)});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Request failed");
  return data;
}
function download(data, filename, type) {
  const blob = new Blob([data], {type});
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a"); a.href=url; a.download=filename; a.click();
  setTimeout(()=>URL.revokeObjectURL(url), 1000);
}
function exportData(data, format, prefix) {
  if (!data) return;
  const stamp = new Date().toISOString().replace(/[:.]/g,"-");
  if (format === "csv") download(data.csv, `${prefix}-${stamp}.csv`, "text/csv;charset=utf-8");
  else { const {csv, ...rest} = data; download(JSON.stringify(rest,null,2), `${prefix}-${stamp}.json`, "application/json"); }
}
function latestAlert(alerts) {return alerts.filter(a=>a.t_ms<=replayTime).at(-1);}
function stopReplay() {
  playing=false;
  if(animationId!==null) cancelAnimationFrame(animationId);
  animationId=null;
  $("play").textContent="▶";
}
function displayMotors(mask) {
  [1,2,4,8].forEach(bit=>$("motor-"+bit).classList.toggle("on", Boolean(mask & bit)));
}
function check(id, value, pass, width, digits) {
  $(id+"-value").textContent = fmt(value, digits);
  $("check-"+id).classList.toggle("fail", !pass);
  $("check-"+id).querySelector(".meter i").style.width = `${Math.max(0,Math.min(100,width))}%`;
}
function waveforms(f) {
  const canvas = $("waveforms"), ctx = canvas.getContext("2d"), {width:w,height:h} = canvas;
  ctx.clearRect(0,0,w,h);
  const colors = ["#4b8154", "#5c9d97", "#9aab5c"];
  const data = f ? f.waveform : [[],[],[]];
  const peak = Math.max(1, ...data.flat().map(Math.abs));
  data.forEach((row,i)=>{
    const y = h*(i+.5)/3;
    ctx.strokeStyle="#e5ebdf";ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(w,y);ctx.stroke();
    ctx.strokeStyle=colors[i];ctx.lineWidth=1.8;ctx.beginPath();
    row.forEach((v,k)=>{const x=k*w/(row.length-1), yy=y-v/peak*20;k?ctx.lineTo(x,yy):ctx.moveTo(x,yy);});ctx.stroke();
  });
}
function renderReplay() {
  if (!result) return;
  $("timeline").value = replayTime;
  $("time-value").textContent = `${Math.round(replayTime)} / ${result.duration_ms} ms`;
  const index = Math.min(result.frames.length-1, Math.floor(replayTime/result.hop_ms)-1);
  const a = latestAlert(result.alerts), b = latestAlert(result.baseline_alerts);
  displayMotors(a ? a.motors : 0);
  $("motor-readout").textContent = a ? a.motor_names.join(" + ") : "No alert";
  $("alert-badge").textContent = a ? (a.kind==="NONDIR"?"General warning":a.kind==="UPDATE"?"Direction updated":"Directional warning") : "No alert yet";
  $("alert-badge").classList.toggle("alert", Boolean(a));
  $("baseline-decision").textContent = b ? `${b.kind === "NONDIR" ? "General" : "Directional"} · ${b.motor_names.join(" + ")} · ${b.t_ms} ms` : "No alert";
  if (index === lastIndex) return;
  lastIndex = index;
  document.querySelectorAll("#log tr.current").forEach(row=>row.classList.remove("current"));
  const row = $("log").children[index]; if(index>=0 && row) row.classList.add("current");
  if (index < 0) {
    $("estimated-value").textContent="—"; $("reliability-value").textContent="Before first window";
    $("reliability-value").classList.remove("fail"); $("estimated-direction").style.display="none";
    $("decision").textContent="Waiting for the first 64 ms analysis window";
    $("reason").textContent="Source starts at 192 ms on the simulated event clock.";
    ["closure","norm","coherence"].forEach(id=>{ $(id+"-value").textContent="—";$("check-"+id).classList.remove("fail");$("check-"+id).querySelector(".meter i").style.width="0";});
    waveforms(null);return;
  }
  const f = result.frames[index], d=f.direction;
  $("estimated-value").textContent = f.direction_available ? `${fmt(d.theta_deg,0)}°` : "Unavailable";
  $("estimated-direction").style.display = f.direction_available ? "" : "none";
  $("estimated-direction").setAttribute("transform", `rotate(${d.theta_deg} 240 212)`);
  $("reliability-value").textContent = f.reliable ? "Checks pass" : "Unreliable";
  $("reliability-value").classList.toggle("fail", !f.reliable);
  check("closure", d.closure, d.closure<=.75, d.closure/1.5*100, 2);
  check("norm", d.norm, d.norm>=.6 && d.norm<=1.4, d.norm/2*100, 2);
  check("coherence", d.coherence, d.coherence>=.3, d.coherence*100, 2);
  $("decision").textContent=f.decision;
  $("reason").textContent=f.reasons.join(". ");
  $("signal-note").textContent=`Window ${index+1} · ${f.t_ms} ms · per-frame amplitude normalised for display`;
  waveforms(f);
}
function tick(now) {
  animationId=null;
  if (!playing || !result) return;
  if (lastTick) replayTime += (now-lastTick)*Number($("speed").value);
  lastTick=now;
  if(replayTime>=result.duration_ms) {replayTime=result.duration_ms;playing=false;$("play").textContent="▶";}
  renderReplay();
  if(playing) animationId=requestAnimationFrame(tick);
}
function play() {
  if (!result) return;
  if (playing) {stopReplay();return;}
  if(replayTime>=result.duration_ms) {replayTime=0;lastIndex=-2;}
  playing=true;lastTick=0;$("play").textContent="Ⅱ";animationId=requestAnimationFrame(tick);
}
$("play").addEventListener("click",play);
$("timeline").addEventListener("input",()=>{stopReplay();replayTime=+$("timeline").value;renderReplay();});
function renderSummary() {
  const m=result.deda;
  $("latency").textContent=m.critical ? (m.latency_ms===null?"No accepted alert":`${m.latency_ms} ms`) : "No critical event";
  $("correct").textContent=!m.critical?"Not applicable":!m.detected?"No alert":m.nondirectional?"General warning · no direction":m.wrong_direction?"No":"Yes";
  $("fallback").textContent=m.nondirectional?"Yes · all four motors":"No";
  $("runtime").textContent=`Laptop computation: ${fmt(result.runtime_ms,0)} ms`;
  const body=$("log");body.replaceChildren();
  result.frames.forEach(f=>{
    const tr=document.createElement("tr");
    const c=Math.max(...f.probs), idx=f.probs.indexOf(c);
    const cells=[`${f.t_ms} ms`,`${["horn","siren","shout","beep","ambient"][idx]} · ${fmt(c*100,0)}% (simulated)`,f.direction_available?`${fmt(f.direction.theta_deg,1)}°`:"Unavailable",f.reliable?"Pass":"Fail",f.alerts.length?f.alerts.map(a=>`${a.kind} → ${a.motor_names.join(" + ")}`).join("; "):f.decision];
    cells.forEach(text=>{const td=document.createElement("td");td.textContent=text;tr.append(td);});body.append(tr);
  });
}
async function runScene() {
  if (busy) return;
  stopReplay();
  setBusy(true);$("run-status").classList.remove("error");$("run-status").textContent="Computing microphone signals, GCC-PHAT and DEDA…";
  try {
    result=await api("/api/simulate", {sound:$("sound").value,angle:+$("angle").value,snr_db:+$("snr").value,condition:$("condition").value,confidence:+$("confidence").value/100,seed:+$("seed").value,active_frac:+$("bins").value,event_ms:+$("duration").value});
    $("true-direction").setAttribute("transform",`rotate(${result.options.angle} 240 212)`);
    $("true-direction").style.display=result.options.sound==="ambient"?"none":"";
    renderSummary();replayTime=0;lastIndex=-2;$("timeline").max=result.duration_ms;
    ["timeline","play","export-json","export-csv"].forEach(id=>$(id).disabled=false);
    $("run-status").textContent=`Computed ${result.frames.length} windows · seed ${result.options.seed}. Replay shows the actual Python output.`;
    renderReplay();play();
  } catch(error) {$("run-status").textContent=error.message;$("run-status").classList.add("error");}
  finally {setBusy(false);}
}
$("run").addEventListener("click",runScene);
document.querySelectorAll("[data-preset]").forEach(button=>button.addEventListener("click",()=>{
  const p=presets[button.dataset.preset];Object.entries(p).forEach(([k,v])=>$(k).value=v);
  $("seed").value=7;$("duration").value=1024;$("bins").value=.25;labels();runScene();
}));
$("export-json").addEventListener("click",()=>exportData(result,"json","soundscape-run"));
$("export-csv").addEventListener("click",()=>exportData(result,"csv","soundscape-windows"));
function tab(name) {
  ["demo","experiment"].forEach(n=>{const selected=n===name;$(n+"-view").hidden=!selected;$(n+"-tab").classList.toggle("active",selected);$(n+"-tab").setAttribute("aria-selected",selected);});
}
$("demo-tab").addEventListener("click",()=>tab("demo"));$("experiment-tab").addEventListener("click",()=>tab("experiment"));
function experimentDisplay() {
  $("experiment-empty").hidden=true;$("experiment-data").hidden=false;
  const p=experimentResult.policies, body=$("experiment-table");body.replaceChildren();
  const fields=[["Critical events","events",false],["Wrong-direction alerts / all critical events","wrong_direction_pct",true],["Missed events","missed_pct",true],["Missed or later than 300 ms","missed_or_late_pct",true],["General first warnings / detected events","nondirectional_pct",true],["Median simulated alert delay","latency_p50_ms",false," ms"],["95th percentile simulated alert delay","latency_p95_ms",false," ms"],["Ambient false alerts per hour*","false_alerts_per_ambient_hour",false]];
  fields.forEach(([name,key,percent,suffix=""])=>{const row=document.createElement("tr");[name,...["baseline","deda"].map(policy=>p[policy][key]===null?"—":fmt(p[policy][key],key==="events"?0:1)+(percent?"%":suffix))].forEach(v=>{const td=document.createElement("td");td.textContent=v;row.append(td);});body.append(row);});
  const chart=$("comparison-chart");chart.replaceChildren();
  [["Wrong-direction alerts","wrong_direction_pct"],["Missed or late events","missed_or_late_pct"]].forEach(([label,key])=>{
    const group=document.createElement("div");group.className="chart-group";const title=document.createElement("strong");title.textContent=label;group.append(title);
    ["baseline","deda"].forEach(policy=>{const row=document.createElement("div");row.className="chart-row";const span=document.createElement("span");span.textContent=policy==="deda"?"DEDA":"Baseline B";const bar=document.createElement("div");bar.className="chart-bar";const fill=document.createElement("i");fill.style.width=`${p[policy][key]??0}%`;bar.append(fill);const number=document.createElement("span");number.textContent=fmt(p[policy][key])+"%";row.append(span,bar,number);group.append(row);});chart.append(group);
  });
  $("experiment-note").textContent=`* Ambient exposure: ${fmt(p.deda.ambient_hours*3600,2)} seconds, with scripted ambient probabilities and no false confusers. Zero does not establish a low real-world false-alert rate. Class recognition is not evaluated. ${experimentResult.note}`;
}
$("run-experiment").addEventListener("click",async()=>{
  if(busy)return;setBusy(true);$("experiment-status").classList.remove("error");
  const count=($("suite").value==="full"?192:32)*Number($("seeds").value);
  $("experiment-status").textContent=`Computing ${count} critical trials plus ambient controls. This may take a few minutes. Keep this page open…`;
  try {experimentResult=await api("/api/experiment",{suite:$("suite").value,seeds:+$("seeds").value});experimentDisplay();$("experiment-status").textContent=`Completed ${experimentResult.trials.length} trials in ${fmt(experimentResult.runtime_ms/1000,1)} s.`;$("experiment-json").disabled=false;$("experiment-csv").disabled=false;}
  catch(error){$("experiment-status").textContent=error.message;$("experiment-status").classList.add("error");}
  finally{setBusy(false);}
});
$("experiment-json").addEventListener("click",()=>exportData(experimentResult,"json","soundscape-experiment"));
$("experiment-csv").addEventListener("click",()=>exportData(experimentResult,"csv","soundscape-trials"));
fetch("/api/health").then(r=>{if(!r.ok)throw new Error();return r.json();}).then(()=>{$("connection").textContent="Python engine connected";}).catch(()=>{$("connection").textContent="Python server unavailable";$("connection").classList.add("error");});
labels();waveforms(null);
