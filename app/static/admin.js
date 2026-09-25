const sel=(s)=>document.querySelector(s);
let adminCredential='';

function esc(s=''){
  return String(s).replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));
}

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
    <div class="grid grid3 admin-status-grid">
      <div class="card"><div class="path-score">${d.purchases}</div><div class="muted">All purchase attempts</div></div>
      <div class="card"><div class="path-score">${d.refunded||0}</div><div class="muted">Refunded</div></div>
      <div class="card"><div class="path-score">${d.disputed||0}</div><div class="muted">Disputed</div></div>
    </div>
    <div class="card admin-feedback-card">
      <h3>Progress feedback</h3>
      <p class="muted">Day 7: ${d.feedback['7']||0} · Day 14: ${d.feedback['14']||0} · Day 30: ${d.feedback['30']||0}</p>
    </div>
    <div class="card admin-feedback-card">
      <div class="eyebrow">Support access recovery</div>
      <h3>Generate a backup for a verified active purchase</h3>
      <p class="muted">Use only after verifying the customer in Stripe. The credential stays in memory for this tab only and is never stored in browser storage.</p>
      <input id="support-purchase-id" class="textarea" type="number" min="1" inputmode="numeric" placeholder="Purchase ID">
      <br><br>
      <button class="btn secondary" id="generate-support-backup">Generate access backup</button>
      <div id="support-backup-result" class="muted"></div>
    </div>`;

  sel('#generate-support-backup')?.addEventListener('click',generateSupportBackup);
}

async function loadMetrics(){
  const credential=sel('#token').value;
  const r=await fetch('/api/v1/admin/summary',{
    headers:{'X-Admin-Token':credential},
    credentials:'same-origin'
  });
  if(!r.ok){
    sel('#err').textContent='Invalid credential.';
    return;
  }
  adminCredential=credential;
  sel('#token').value='';
  render(await r.json());
}

async function generateSupportBackup(){
  const id=Number(sel('#support-purchase-id').value);
  const output=sel('#support-backup-result');
  if(!Number.isInteger(id)||id<1){
    output.textContent='Enter a valid purchase ID.';
    return;
  }

  output.textContent='Checking purchase…';
  const r=await fetch('/api/v1/admin/access-backup/'+encodeURIComponent(id),{
    headers:{'X-Admin-Token':adminCredential},
    credentials:'same-origin'
  });
  const j=await r.json().catch(()=>({}));
  if(!r.ok){
    output.textContent=j.detail||'Could not create backup.';
    return;
  }

  const wrapper=document.createElement('div');
  wrapper.className='backup-key-content';
  const reference=document.createElement('p');
  reference.textContent='Reference: '+j.reference;
  const key=document.createElement('p');
  key.textContent='Backup key: '+j.key;
  const expires=document.createElement('p');
  expires.textContent='Expires: '+(j.expires_at||'unknown');
  const copy=document.createElement('button');
  copy.type='button';
  copy.className='btn secondary';
  copy.textContent='Copy recovery details';
  copy.onclick=async()=>{
    await navigator.clipboard.writeText('Reference: '+j.reference+'\nBackup key: '+j.key);
    copy.textContent='Copied';
  };
  wrapper.append(reference,key,expires,copy);
  output.replaceChildren(wrapper);
}

sel('#load-metrics')?.addEventListener('click',loadMetrics);
sel('#token')?.addEventListener('keydown',e=>{if(e.key==='Enter')loadMetrics()});
