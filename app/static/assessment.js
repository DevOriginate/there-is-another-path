const sel=s=>document.querySelector(s);
const token=new URLSearchParams(location.search).get('token');
let qs=[],i=0,a={};
const pretty=s=>String(s).replaceAll('_',' ').replace(/\b\w/g,c=>c.toUpperCase());
async function init(){
 if(!token){location.href='/';return}
 const access=await fetch('/api/v1/access/'+encodeURIComponent(token));
 if(!access.ok){sel('#app').innerHTML='<div class="card"><h2>Access not found</h2><a class="btn" href="/">Return home</a></div>';return}
 const aj=await access.json(); if(aj.completed){location.href=aj.report_url;return}
 qs=(await fetch('/api/v1/assessment/schema').then(r=>r.json())).questions; render();
}
function render(){
 const q=qs[i]; sel('#step').textContent='Question '+(i+1)+' of '+qs.length; sel('#progress').style.width=Math.round(i/qs.length*100)+'%';
 let html='';
 if(q.type==='single') html=q.options.map(o=>`<label class="option"><input type="radio" name="v" value="${o}" ${a[q.id]===o?'checked':''}> ${pretty(o)}</label>`).join('');
 else if(q.type==='multi') html=q.options.map(o=>`<label class="option"><input type="checkbox" value="${o}" ${(a[q.id]||[]).includes(o)?'checked':''}> ${pretty(o)}</label>`).join('');
 else if(q.type==='text') html=`<textarea id="txt" class="textarea">${a[q.id]||''}</textarea>`;
 else if(q.type==='scale_1_5') html=[1,2,3,4,5].map(n=>`<label class="option"><input type="radio" name="v" value="${n}" ${a[q.id]===n?'checked':''}> ${n}</label>`).join('');
 else if(q.type==='forced_pairs'){const pairs=[['customers','computer'],['build','sell'],['technical','people'],['create','improve']];html=pairs.map((p,k)=>`<div class="card"><label class="option"><input type="radio" name="p${k}" value="${p[0]}"> ${pretty(p[0])}</label><label class="option"><input type="radio" name="p${k}" value="${p[1]}"> ${pretty(p[1])}</label></div>`).join('')}
 sel('#question').innerHTML=`<div class="eyebrow">Path Assessment</div><h1>${q.prompt}</h1><div class="options">${html}</div><div id="err" class="error"></div><div class="navrow"><button class="btn secondary" id="back" ${i===0?'disabled':''}>Back</button><button class="btn" id="next">${i===qs.length-1?'Build my path report':'Continue'}</button></div>`;
 sel('#back').onclick=()=>{capture(false);i--;render()}; sel('#next').onclick=next;
}
function capture(validate=true){
 const q=qs[i]; let v;
 if(q.type==='single'){const e=document.querySelector('input[name=v]:checked');v=e?.value}
 if(q.type==='multi')v=[...document.querySelectorAll('.options input[type=checkbox]:checked')].map(e=>e.value);
 if(q.type==='text')v=sel('#txt').value.trim();
 if(q.type==='scale_1_5'){const e=document.querySelector('input[name=v]:checked');v=e?Number(e.value):undefined}
 if(q.type==='forced_pairs'){v={};for(let k=0;k<4;k++){const e=document.querySelector('input[name=p'+k+']:checked');if(e)v['p'+k]=e.value}}
 if(validate && q.type==='single' && v===undefined){sel('#err').textContent='Choose an answer to continue.';return false}
 if(validate && q.type==='scale_1_5' && v===undefined){sel('#err').textContent='Choose an answer to continue.';return false}
 if(validate && q.id==='primary_objectives' && (!v.length||v.length>2)){ sel('#err').textContent='Choose one or two options.';return false}
 if(validate && q.id==='natural_activities' && v.length>5){sel('#err').textContent='Choose up to five options.';return false}
 if(validate && q.type==='forced_pairs' && Object.keys(v).length<4){sel('#err').textContent='Choose one option in each pair.';return false}
 if(q.id==='experience_areas'&&v.includes('none')&&v.length>1){sel('#err').textContent='Choose None by itself.';return false}
 if(q.id==='constraints'&&v.includes('none')&&v.length>1){sel('#err').textContent='Choose None by itself.';return false}
 a[q.id]=v;return true
}
async function next(){
 if(!capture(true))return;
 if(i<qs.length-1){i++;render();return}
 sel('#question').innerHTML='<div class="loading"><h2>Building your path report…</h2></div>';
 const r=await fetch('/api/v1/assessments/submit/'+encodeURIComponent(token),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(a)});
 const j=await r.json(); if(!r.ok){sel('#question').innerHTML='<div class="card"><h2>Could not build report</h2><p class="error">'+(j.detail||'Try again')+'</p></div>';return}
 location.href=j.report_url;
}
init();