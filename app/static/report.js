const sel=(s)=>document.querySelector(s);
function esc(s=''){return String(s).replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]))}

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
 <div class="eyebrow">Your Path Report</div>
 <span class="score-pill">${esc(d.confidence.band)} · ${d.confidence.score}/100 confidence</span>
 <h1>${esc(d.headline)}</h1>
 <p class="lead">${esc(d.position)}</p>
</section>
<section class="section"><div class="grid grid3">${d.top_paths.map((x,i)=>`<div class="card path-card ${i===0?'primary':''}"><div class="eyebrow">${i===0?'Primary path':i===1?'Second path':'Alternative path'}</div><h3>${esc(x.name)}</h3><div class="path-score">${x.score}</div><div class="muted">${esc(x.band)} · ${esc(x.family_label)}</div><p>${esc((x.strengths||[])[0]||'Strong overall alignment.')}</p>${(x.constraints||[]).length?`<p class="muted"><strong>Watch:</strong> ${esc(x.constraints[0])}</p>`:''}</div>`).join('')}</div></section>
<section class="section"><div class="grid grid2"><div class="card"><div class="eyebrow">Why this path won</div><h2>${esc(p.name)}</h2><p>${esc(d.why_primary)}</p><p class="muted">${esc(d.caution)}</p><p class="muted">${esc(d.timeline_note)}</p></div><div class="card"><div class="eyebrow">Your first move</div><div class="first-move">${esc(d.first_move)}</div><p class="muted">Do this before you try to redesign your whole life.</p></div></div></section>
<section class="section"><div class="eyebrow">Your first 30 days</div><h2>Learn enough to test. Test enough to learn.</h2>${d.week_plan.map((w,i)=>`<div class="week"><b>${i+1}</b><div><h3>Week ${i+1}</h3><p class="muted">${esc(w)}</p></div></div>`).join('')}</section>
${d.long_term_opportunity?`<section class="section"><div class="card"><div class="eyebrow">Long-term opportunity</div><h2>${esc(d.long_term_opportunity.name)}</h2><p class="muted">Your underlying fit is strong, but this path is less compatible with your immediate timeline or current constraints. Keep it on your horizon rather than forcing it now.</p></div></section>`:''}
${(d.conflicts||[]).length?`<section class="section"><div class="card"><div class="eyebrow">Important tension</div>${d.conflicts.map(c=>`<p>${esc(c)}</p>`).join('')}</div></section>`:''}
<section class="section"><div class="card feedback"><div class="eyebrow">Make the engine better</div><h2>Come back as you test the path.</h2><p class="muted">Your Day 7, Day 14 and Day 30 feedback helps us measure whether a recommendation created real movement, not just a good-looking report.</p><div><button class="btn secondary feedback-btn" data-day="7">Day 7 check-in</button><button class="btn secondary feedback-btn" data-day="14">Day 14 check-in</button><button class="btn secondary feedback-btn" data-day="30">Day 30 check-in</button></div><p class="privacy-hint">Do not include names, contact details, medical information, account numbers, or other sensitive personal data in feedback.</p><p id="feedbackStatus" class="muted"></p></div></section>
<section class="section"><p class="muted">${esc(d.disclaimer)}</p></section>`;

 sel('#print-report')?.addEventListener('click',()=>window.print());
 document.querySelectorAll('.feedback-btn').forEach(btn=>btn.addEventListener('click',()=>feedback(Number(btn.dataset.day))));
}

async function feedback(day){
 const status=prompt(`Day ${day}: In one or two sentences, what happened after you started this path? Do not include sensitive personal information.`);
 if(!status)return;
 const progress=prompt('Choose one: not_started, started, meaningful_progress, changed_path')||'started';
 const r=await fetch(`/api/v1/feedback/${day}`,{
  method:'POST',
  credentials:'same-origin',
  headers:{'Content-Type':'application/json'},
  body:JSON.stringify({payload:{status:progress,note:status}})
 });
 let message='Could not save feedback.';
 if(r.ok) message='Feedback saved. Thank you.';
 else {
  try{
   const j=await r.json();
   if(Array.isArray(j.detail)) message='Please remove sensitive identifiers and try again.';
   else if(j.detail) message=String(j.detail);
  }catch(_){}
 }
 sel('#feedbackStatus').textContent=message;
}

init().catch(err=>{
 console.error('Report initialization failed',err);
 const report=sel('#report');
 if(report){
  report.innerHTML='<div class="card"><h2>Could not load your report</h2><p class="error">Your completed assessment is preserved. Reload this page to try again.</p><button class="btn" id="reload-report">Reload report</button></div>';
  sel('#reload-report')?.addEventListener('click',()=>location.reload());
 }
});
