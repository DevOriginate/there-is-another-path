const sel=(s)=>document.querySelector(s);

function esc(s=''){
  return String(s).replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));
}

function snapshotRows(snapshot={}){
  return Object.entries(snapshot).map(([key,value])=>{
    const label=key.replaceAll('_',' ');
    const shown=Array.isArray(value)?value.map(esc).join(', '):esc(value);
    return `<div class="snapshot-row"><span>${esc(label)}</span><strong>${shown}</strong></div>`;
  }).join('');
}

function metricRows(items=[]){
  return items.map(x=>`<div class="fit-row"><span>${esc(x.label)}</span><strong>${esc(x.score)}</strong></div>`).join('');
}

async function init(){
  const r=await fetch('/api/v1/reports/me',{credentials:'same-origin'});
  if(!r.ok){
    sel('#report').innerHTML='<div class="card"><h2>Private report unavailable</h2><p class="muted">This browser does not have an active paid session, or the retained report has expired.</p><a class="btn" href="/">Return home</a></div>';
    return;
  }

  const d=await r.json();
  document.title=d.headline+' — The Path Finder';
  const p=d.top_paths[0];

  sel('#report').innerHTML=`
<section class="report-hero">
  <div class="print-actions actions"><button class="btn secondary" id="print-report">Print / Save PDF</button></div>
  <div class="eyebrow">Your Path Consultation</div>
  <span class="score-pill">${esc(d.confidence.band)} · ${esc(d.confidence.score)}/100 confidence</span>
  <h1>${esc(d.headline)}</h1>
  <p class="lead">This consultation was composed from your assessment as a single case — your goals, constraints, time, risk tolerance, experience, preferences and ranked path together.</p>
</section>

<section class="section consultation-intro">
  <div class="consultant-note">
    <div class="eyebrow">Consultant's read</div>
    <p>${esc(d.consultant_read)}</p>
  </div>
  <div class="card tension-card">
    <div class="eyebrow">The tension that matters</div>
    <p>${esc(d.core_tension)}</p>
  </div>
</section>

${(d.client_words||d.help_words)?`
<section class="section client-voice-section">
  <div class="grid ${d.client_words&&d.help_words?'grid2':''}">
    ${d.help_words?`<div class="client-words">
      <div class="eyebrow">What you asked us to help with</div>
      <blockquote>“${esc(d.help_words)}”</blockquote>
    </div>`:''}
    ${d.client_words?`<div class="client-words">
      <div class="eyebrow">What you want to change in 12 months</div>
      <blockquote>“${esc(d.client_words)}”</blockquote>
    </div>`:''}
  </div>
</section>`:''}

<section class="section">
  <div class="eyebrow">Decision brief</div>
  <h2>The decision, stripped of noise.</h2>
  <div class="decision-grid">
    <div class="decision-main card">
      <div class="eyebrow">Primary direction</div>
      <h3>${esc(d.decision_brief.primary_path)}</h3>
      <p>${esc(d.decision_brief.why_now)}</p>
      <div class="brief-line"><span>Strongest advantage</span><strong>${esc(d.decision_brief.strongest_advantage)}</strong></div>
      <div class="brief-line"><span>Main constraint</span><strong>${esc(d.decision_brief.main_constraint)}</strong></div>
    </div>
    <div class="decision-action card">
      <div class="eyebrow">Your first move</div>
      <div class="first-move">${esc(d.first_move)}</div>
      <p class="muted">This is deliberately small. The job of the first move is to create evidence, not prove your entire future.</p>
    </div>
  </div>
</section>

<section class="section">
  <div class="eyebrow">Your situation</div>
  <h2>What this recommendation is actually accounting for.</h2>
  <div class="snapshot-card card">${snapshotRows(d.client_snapshot)}</div>
</section>

<section class="section">
  <div class="eyebrow">Ranked paths</div>
  <div class="grid grid3">
    ${d.top_paths.map((x,i)=>`<div class="card path-card ${i===0?'primary':''}">
      <div class="eyebrow">${i===0?'Primary path':i===1?'Second path':'Alternative path'}</div>
      <h3>${esc(x.name)}</h3>
      <div class="path-score">${esc(x.score)}</div>
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
    </div>
    <div class="card diagnostics-card">
      <div class="eyebrow">Fit diagnostics</div>
      <h3>Where the case is strongest</h3>
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
      <p class="switch-condition"><strong>Reconsider it if</strong> ${esc(x.reconsider_if)}.</p>
    </div>`).join('')}
  </div>
</section>`:''}

<section class="section">
  <div class="eyebrow">Your first 30 days</div>
  <h2>A plan built around this case, not a generic checklist.</h2>
  <p class="lead">You are not trying to become an expert in 30 days. You are trying to create enough real evidence to know whether this path deserves more of your life.</p>
  ${(d.week_plan||[]).map((w,i)=>`<div class="week consultation-week">
    <b>${esc(w.week||i+1)}</b>
    <div><div class="week-title">${esc(w.title||('Week '+(i+1)))}</div><p>${esc(w.action||w)}</p></div>
  </div>`).join('')}
</section>

${d.decision_rules&&Object.keys(d.decision_rules).length?`
<section class="section">
  <div class="eyebrow">Decision rules</div>
  <h2>Know what evidence changes the recommendation.</h2>
  <p class="lead">A useful consultation should tell you what would make it stronger, what would require adjustment, and what would justify changing direction.</p>
  <div class="grid grid3 decision-rules">
    <div class="card rule-card continue-rule">
      <div class="eyebrow">Continue</div>
      <h3>Keep investing in the path if…</h3>
      <p>${esc(d.decision_rules.continue)}</p>
    </div>
    <div class="card rule-card adjust-rule">
      <div class="eyebrow">Adjust</div>
      <h3>Change the experiment if…</h3>
      <p>${esc(d.decision_rules.adjust)}</p>
    </div>
    <div class="card rule-card switch-rule">
      <div class="eyebrow">Re-rank</div>
      <h3>Consider another path if…</h3>
      <p>${esc(d.decision_rules.switch)}</p>
    </div>
  </div>
</section>`:''}

${(d.anti_plan||[]).length?`
<section class="section">
  <div class="card anti-plan">
    <div class="eyebrow">What I would not do</div>
    <h2>Protect yourself from expensive confusion.</h2>
    ${d.anti_plan.map(x=>`<p>${esc(x)}</p>`).join('')}
  </div>
</section>`:''}

<section class="section">
  <div class="confidence-card card">
    <div class="eyebrow">How much should you trust this?</div>
    <h2>${esc(d.confidence.band)}</h2>
    <p>${esc(d.confidence.explanation)}</p>
    <div class="confidence-number">${esc(d.confidence.score)}/100</div>
  </div>
</section>

${d.long_term_opportunity?`
<section class="section"><div class="card">
  <div class="eyebrow">Long-term opportunity</div>
  <h2>${esc(d.long_term_opportunity.name)}</h2>
  <p class="muted">Your underlying fit is strong, but this path is less compatible with your immediate timeline or current constraints. Keep it on the horizon rather than forcing it now.</p>
</div></section>`:''}

${(d.conflicts||[]).length?`
<section class="section"><div class="card">
  <div class="eyebrow">Important tension detected by the engine</div>
  ${d.conflicts.map(c=>`<p>${esc(c)}</p>`).join('')}
</div></section>`:''}

<section class="section">
  <div class="card feedback">
    <div class="eyebrow">Reality check</div>
    <h2>Come back as you test the path.</h2>
    <p class="muted">Day 7, Day 14 and Day 30 feedback matters because this consultation only earns your trust if it creates useful movement in the real world.</p>
    <div>
      <button class="btn secondary feedback-btn" data-day="7">Day 7 check-in</button>
      <button class="btn secondary feedback-btn" data-day="14">Day 14 check-in</button>
      <button class="btn secondary feedback-btn" data-day="30">Day 30 check-in</button>
    </div>
    <p class="privacy-hint">Do not include names, contact details, medical information, account numbers, or other sensitive personal data in feedback.</p>
    <p id="feedbackStatus" class="muted"></p>
  </div>
</section>

<section class="section">
  <p class="muted">${esc(d.disclaimer)}</p>
  <div class="privacy-controls">
    <button class="btn secondary" id="delete-private-data">Delete my private consultation data</button>
    <p class="privacy-hint">This removes your stored assessment and progress feedback from this service. Minimal transaction records may remain for payment, accounting, fraud prevention, or legal obligations.</p>
  </div>
</section>`;

  sel('#print-report')?.addEventListener('click',()=>window.print());
  document.querySelectorAll('.feedback-btn').forEach(btn=>btn.addEventListener('click',()=>feedback(Number(btn.dataset.day))));
  sel('#delete-private-data')?.addEventListener('click',deletePrivateData);
}

async function feedback(day){
  const note=prompt(`Day ${day}: In one or two sentences, what happened after you started this path? Do not include sensitive personal information.`);
  if(!note)return;
  const progress=prompt('Choose one: not_started, started, meaningful_progress, changed_path')||'started';
  const r=await fetch(`/api/v1/feedback/${day}`,{
    method:'POST',
    credentials:'same-origin',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({payload:{status:progress,note}})
  });
  let message='Could not save feedback.';
  if(r.ok) message='Feedback saved. Thank you.';
  else{
    try{
      const j=await r.json();
      if(Array.isArray(j.detail)) message='Please remove sensitive identifiers and try again.';
      else if(j.detail) message=String(j.detail);
    }catch(_){}
  }
  sel('#feedbackStatus').textContent=message;
}

async function deletePrivateData(){
  const ok=confirm('Delete your stored assessment and progress feedback? This cannot be undone.');
  if(!ok)return;
  const r=await fetch('/api/v1/privacy/delete',{method:'POST',credentials:'same-origin'});
  if(r.ok){
    location.href='/';
    return;
  }
  alert('Could not delete the private consultation data. Please try again or contact support.');
}

init().catch(err=>{
  console.error('Report initialization failed',err);
  const report=sel('#report');
  if(report){
    report.innerHTML='<div class="card"><h2>Could not load your report</h2><p class="error">Your completed assessment is preserved. Reload this page to try again.</p><button class="btn" id="reload-report">Reload report</button></div>';
    sel('#reload-report')?.addEventListener('click',()=>location.reload());
  }
});
