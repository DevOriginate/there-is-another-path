const sel=(s)=>document.querySelector(s);

function render(d){
  sel('#login').classList.add('hidden');
  sel('#metrics').classList.remove('hidden');
  sel('#metrics').innerHTML=`
    <div class="eyebrow">Live MVP metrics</div>
    <h1>Path Finder</h1>
    <div class="grid grid3">
      <div class="card"><div class="path-score">${d.paid}</div><div class="muted">Paid orders</div></div>
      <div class="card"><div class="path-score">$${(d.revenue_cents/100).toFixed(2)}</div><div class="muted">Gross revenue</div></div>
      <div class="card"><div class="path-score">${d.paid_to_assessment_rate}%</div><div class="muted">Paid → assessment</div></div>
    </div>
    <div class="card admin-feedback-card">
      <h3>Progress feedback</h3>
      <p class="muted">Day 7: ${d.feedback['7']||0} · Day 14: ${d.feedback['14']||0} · Day 30: ${d.feedback['30']||0}</p>
    </div>`;
}

async function loadMetrics(){
  const credential=sel('#token').value;
  const r=await fetch('/api/v1/admin/summary',{headers:{'X-Admin-Token':credential},credentials:'same-origin'});
  if(!r.ok){
    sel('#err').textContent='Invalid credential.';
    return;
  }
  sel('#token').value='';
  render(await r.json());
}

sel('#load-metrics')?.addEventListener('click',loadMetrics);
sel('#token')?.addEventListener('keydown',e=>{if(e.key==='Enter')loadMetrics()});
