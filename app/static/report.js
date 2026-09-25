const token=location.pathname.split('/').pop();
const sel=(s)=>document.querySelector(s);
function esc(s=''){return String(s).replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]))}
function list(items=[]){return items.map(x=>`<li>${esc(x)}</li>`).join('')}
function metricRows(items=[]){return items.map(x=>`<div class="fit-row"><span>${esc(x.label)}</span><strong>${esc(x.score)}</strong></div>`).join('')}
function snapshotRows(snapshot={}){return Object.entries(snapshot).map(([k,v])=>`<div class="snapshot-row"><span>${esc(k.replaceAll('_',' '))}</span><strong>${Array.isArray(v)?v.map(esc).join(', '):esc(v)}</strong></div>`).join('')}

async function init(){
 const r=await fetch('/api/v1/reports/'+encodeURIComponent(token));
 if(!r.ok){sel('#report').innerHTML='<div class="card"><h2>Report not found</h2></div>';return}
 const d=await r.json();
 document.title=d.headline+' — The Path Finder';
 const p=d.top_paths[0];

 sel('#report').innerHTML=`
<section class="report-hero">
  <div class="print-actions actions">
    <button class="btn secondary" onclick="window.print()">Print / Save PDF</button>
    <button class="btn secondary" onclick="navigator.clipboard.writeText(location.href)">Copy private link</button>
  </div>
  <div class="eyebrow">Your Path Report</div>
  <span class="score-pill">${esc(d.confidence.band)} · ${d.confidence.score}/100 confidence</span>
  <h1>${esc(d.headline)}</h1>
  <p class="lead">${esc(d.position)}</p>
</section>

<section class="section consultation-intro">
  <div class="consultant-note">
    <div class="eyebrow">Consultant's read</div>
    <p>${esc(d.consultant_note)}</p>
  </div>
  ${d.client_words?`<div class="client-words"><div class="eyebrow">What you said you want to change</div><blockquote>“${esc(d.client_words)}”</blockquote></div>`:''}
</section>

<section class="section">
  <div class="eyebrow">Decision brief</div>
  <h2>The decision, stripped of noise.</h2>
  <div class="decision-grid">
    <div class="decision-main card">
      <div class="eyebrow">Primary direction</div>
      <h3>${esc(d.decision_brief.primary_path)}</h3>
      <p>${esc(d.decision_brief.why_now)}</p>
      <div class="brief-line"><span>Strongest advantage</span><strong>${esc(d.decision_brief.biggest_advantage)}</strong></div>
      <div class="brief-line"><span>Main constraint</span><strong>${esc(d.decision_brief.biggest_constraint)}</strong></div>
    </div>
    <div class="decision-action card">
      <div class="eyebrow">Immediate action</div>
      <div class="first-move">${esc(d.decision_brief.first_move)}</div>
      <div class="brief-line"><span>30-day target</span><strong>${esc(d.decision_brief.thirty_day_target)}</strong></div>
    </div>
  </div>
</section>

<section class="section">
  <div class="eyebrow">Your situation</div>
  <h2>What the recommendation is actually accounting for.</h2>
  <div class="snapshot-card card">${snapshotRows(d.client_snapshot)}</div>
</section>

<section class="section">
  <div class="eyebrow">Ranked paths</div>
  <div class="grid grid3">
    ${d.top_paths.map((x,i)=>`<div class="card path-card ${i===0?'primary':''}">
      <div class="eyebrow">${i===0?'Primary path':i===1?'Second path':'Alternative path'}</div>
      <h3>${esc(x.name)}</h3>
      <div class="path-score">${x.score}</div>
      <div class="muted">${esc(x.band)} · ${esc(x.family_label)}</div>
      <p>${esc((x.strengths||[])[0]||'Strong overall alignment.')}</p>
      ${(x.constraints||[]).length?`<p class="muted"><strong>Watch:</strong> ${esc(x.constraints[0])}</p>`:''}
    </div>`).join('')}
  </div>
</section>

<section class="section">
  <div class="grid grid2">
    <div class="card">
      <div class="eyebrow">Why this path won</div>
      <h2>${esc(p.name)}</h2>
      <p>${esc(d.why_primary)}</p>
      <p class="muted">${esc(d.caution)}</p>
      <p class="muted">${esc(d.timeline_note)}</p>
    </div>
    <div class="card diagnostics-card">
      <div class="eyebrow">Fit diagnostics</div>
      <h3>Where the recommendation is strongest</h3>
      ${metricRows(d.fit_highlights)}
      <h3 class="watch-title">Where to stay realistic</h3>
      ${metricRows(d.fit_watchouts)}
    </div>
  </div>
</section>

${(d.alternative_analysis||[]).length?`
<section class="section">
  <div class="eyebrow">Why not the other paths?</div>
  <h2>Good options can still be the wrong first move.</h2>
  <div class="grid grid2">
    ${d.alternative_analysis.map(x=>`<div class="card alternative-card">
      <div class="eyebrow">${esc(x.family_label)}</div>
      <h3>${esc(x.name)}</h3>
      <div class="alt-score">${esc(x.score)} · ${esc(x.band)}</div>
      <p><strong>What it has going for it:</strong> ${esc(x.upside)}</p>
      <p><strong>Why it is not first:</strong> ${esc(x.why_below)}</p>
      <p class="switch-condition"><strong>Reconsider it if</strong> ${esc(x.switch_condition)}</p>
    </div>`).join('')}
  </div>
</section>`:''}

<section class="section">
  <div class="eyebrow">Your first 30 days</div>
  <h2>Learn enough to test. Test enough to learn.</h2>
  <p class="lead">The goal is not to become an expert in 30 days. The goal is to create enough evidence to know whether this path deserves more of your time.</p>
  ${d.week_plan.map((w,i)=>`<div class="week"><b>${i+1}</b><div><h3>Week ${i+1}</h3><p class="muted">${esc(w)}</p></div></div>`).join('')}
</section>

<section class="section">
  <div class="confidence-card card">
    <div class="eyebrow">How much should you trust this?</div>
    <h2>${esc(d.confidence.band)}</h2>
    <p>${esc(d.confidence.explanation)}</p>
    <div class="confidence-number">${esc(d.confidence.score)}/100</div>
  </div>
</section>

${d.long_term_opportunity?`<section class="section"><div class="card"><div class="eyebrow">Long-term opportunity</div><h2>${esc(d.long_term_opportunity.name)}</h2><p class="muted">Your underlying fit is strong, but this path is less compatible with your immediate timeline or current constraints. Keep it on your horizon rather than forcing it now.</p></div></section>`:''}

${(d.conflicts||[]).length?`<section class="section"><div class="card"><div class="eyebrow">Important tension</div>${d.conflicts.map(c=>`<p>${esc(c)}</p>`).join('')}</div></section>`:''}

<section class="section">
  <div class="card feedback">
    <div class="eyebrow">Reality check</div>
    <h2>Come back as you test the path.</h2>
    <p class="muted">Day 7, Day 14 and Day 30 feedback matters because a recommendation only earns your trust if it creates movement in the real world.</p>
    <div>
      <button class="btn secondary" onclick="feedback(7)">Day 7 check-in</button>
      <button class="btn secondary" onclick="feedback(14)">Day 14 check-in</button>
      <button class="btn secondary" onclick="feedback(30)">Day 30 check-in</button>
    </div>
    <p id="feedbackStatus" class="muted"></p>
  </div>
</section>

<section class="section"><p class="muted">${esc(d.disclaimer)}</p></section>
`;
}

async function feedback(day){
 const status=prompt(`Day ${day}: In one or two sentences, what happened after you started this path?`);
 if(!status)return;
 const progress=prompt('Choose one: not_started, started, meaningful_progress, changed_path')||'started';
 const r=await fetch(`/api/v1/feedback/${encodeURIComponent(token)}/${day}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({payload:{status:progress,note:status}})});
 sel('#feedbackStatus').textContent=r.ok?'Feedback saved. Thank you.':'Could not save feedback.';
}

init().catch(err=>{
 console.error('Report initialization failed',err);
 sel('#report').innerHTML='<div class="card"><h2>Could not load your report</h2><p class="error">Your completed assessment is preserved. Reload this page to try again.</p><button class="btn" onclick="location.reload()">Reload report</button></div>';
});
