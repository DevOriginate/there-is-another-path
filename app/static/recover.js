const sel=(s)=>document.querySelector(s);

async function restoreAccess(){
  const reference=sel('#reference').value.trim();
  const key=sel('#key').value.trim();
  const status=sel('#restore-status');
  status.textContent='Checking…';

  const r=await fetch('/api/v1/access/restore',{
    method:'POST',
    credentials:'same-origin',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({reference,key})
  });
  const j=await r.json().catch(()=>({}));
  if(!r.ok){
    status.textContent=j.detail||'Could not restore access.';
    return;
  }
  location.href=j.destination||'/';
}

sel('#restore-access')?.addEventListener('click',restoreAccess);
sel('#key')?.addEventListener('keydown',e=>{if(e.key==='Enter')restoreAccess()});
