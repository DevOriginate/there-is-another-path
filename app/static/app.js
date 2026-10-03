const $=(s)=>document.querySelector(s);
const $=(s)=>[...document.querySelectorAll(s)];
let checkoutInFlight=false;
const ATTRIBUTION_KEY='pf-acquisition-v1';
const pendingMetaEvents=[];

function safeStorage(storage,key,value){
  try{
    if(value===undefined)return storage.getItem(key);
    storage.setItem(key,value);
  }catch(_){}
  return null;
}

function qs(){
  return Object.fromEntries(new URLSearchParams(location.search).entries());
}

function captureAcquisition(){
  const q=qs();
  const current={
    utm_source:q.utm_source||'',
    utm_medium:q.utm_medium||'',
    utm_campaign:q.utm_campaign||'',
    utm_content:q.utm_content||'',
    utm_term:q.utm_term||'',
    landing_variant:'v1'
  };

  const hasCampaign=Object.entries(current).some(([key,value])=>key!=='landing_variant'&&Boolean(value));
  if(!hasCampaign && document.referrer){
    try{
      const refHost=new URL(document.referrer).hostname.toLowerCase();
      if(refHost.includes('instagram.com')){
        current.utm_source='instagram';
        current.utm_medium='organic_referral';
        current.utm_campaign='social_profile';
      }else if(refHost.includes('facebook.com')||refHost.includes('fb.com')){
        current.utm_source='facebook';
        current.utm_medium='organic_referral';
        current.utm_campaign='social_profile';
      }
    }catch(_){}
  }

  const previousRaw=safeStorage(sessionStorage,ATTRIBUTION_KEY);
  let previous={};
  if(previousRaw){
    try{previous=JSON.parse(previousRaw)||{}}catch(_){}
  }

  const merged={...previous};
  Object.entries(current).forEach(([key,value])=>{
    if(value)merged[key]=value;
  });
  if(!merged.landing_variant)merged.landing_variant='v1';

  if(hasCampaign||current.utm_source||Object.keys(previous).length){
    safeStorage(sessionStorage,ATTRIBUTION_KEY,JSON.stringify(merged));
  }
  return merged;
}

function acquisition(){
  return captureAcquisition();
}

function cleanCampaignQuery(){
  const params=new URLSearchParams(location.search);
  let changed=false;
  ['utm_source','utm_medium','utm_campaign','utm_content','utm_term'].forEach(key=>{
    if(params.has(key)){params.delete(key);changed=true}
  });
  if(!changed)return;
  const query=params.toString();
  history.replaceState(null,'',location.pathname+(query?'?'+query:'')+location.hash);
}

async function config(){
  return fetch('/api/v1/config/public').then(r=>r.json());
}

function emitMetaEvent(name,data={},marker=''){
  if(!window.fbq){
    pendingMetaEvents.push({name,data,marker});
    return false;
  }
  fbq('track',name,data);
  if(marker)safeStorage(localStorage,marker,'1');
  return true;
}

function fire(name,data={}){
  emitMetaEvent(name,data);
}

function fireOnce(key,name,data={}){
  const marker='pf-meta-event-'+key;
  if(safeStorage(localStorage,marker)==='1')return;
  emitMetaEvent(name,data,marker);
}

function flushMetaEvents(){
  if(!window.fbq)return;
  while(pendingMetaEvents.length){
    const event=pendingMetaEvents.shift();
    if(event.marker&&safeStorage(localStorage,event.marker)==='1')continue;
    fbq('track',event.name,event.data||{});
    if(event.marker)safeStorage(localStorage,event.marker,'1');
  }
}

function installPixel(id){
  if(!id||window.fbq)return;
  !function(f,b,e,v,n,t,s){
    if(f.fbq)return;
    n=f.fbq=function(){n.callMethod?n.callMethod.apply(n,arguments):n.queue.push(arguments)};
    if(!f._fbq)f._fbq=n;
    n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];
    t=b.createElement(e);t.async=!0;t.src=v;
    s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s);
  }(window,document,'script','https://connect.facebook.net/en_US/fbevents.js');
  fbq('init',id);fbq('track','PageView');flushMetaEvents();
}

function metaConsent(id){
  if(!id)return;
  const saved=localStorage.getItem('meta-ads-consent');
  if(saved==='accepted'){installPixel(id);return}
  if(saved==='declined')return;
  const box=document.createElement('div');
  box.className='consent-banner';
  box.innerHTML='<div><strong>Advertising measurement</strong><p>We use optional Meta advertising measurement only with your choice. It never changes your Path recommendation.</p></div><div class="consent-actions"><button class="btn secondary" data-no>Decline</button><button class="btn" data-yes>Accept</button></div>';
  document.body.appendChild(box);
  box.querySelector('[data-yes]').onclick=()=>{localStorage.setItem('meta-ads-consent','accepted');box.remove();installPixel(id)};
  box.querySelector('[data-no]').onclick=()=>{localStorage.setItem('meta-ads-consent','declined');box.remove()};
}

async function initCommon(){
  captureAcquisition();
  const c=await config();
  metaConsent(c.meta_pixel_id);
  document.querySelectorAll('.support-email').forEach(x=>{
    x.textContent=c.support_email;
    x.href='mailto:'+c.support_email;
  });
  return c;
}

function setCheckoutBusy(busy){
  $$('.checkout-btn').forEach(button=>{
    button.disabled=busy;
    if(busy){
      button.dataset.previousLabel=button.textContent;
      button.textContent='Opening secure checkout…';
    }else if(button.dataset.previousLabel){
      button.textContent=button.dataset.previousLabel;
      delete button.dataset.previousLabel;
    }
  });
}

async function beginCheckout(){
  if(checkoutInFlight)return;
  checkoutInFlight=true;
  setCheckoutBusy(true);
  try{
    const c=await initCommon();
    fire('InitiateCheckout',{value:c.product_price_usd,currency:'USD'});
    const r=await fetch('/api/v1/checkout/session',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({acquisition:acquisition()})
    });
    const j=await r.json();
    if(!r.ok)throw new Error(j.detail||'Checkout failed');
    location.href=j.url;
  }catch(err){
    alert(err.message||'Checkout failed');
    checkoutInFlight=false;
    setCheckoutBusy(false);
  }
}

async function existingAccess(){
  try{
    const r=await fetch('/api/v1/access/me',{credentials:'same-origin'});
    if(!r.ok)return null;
    return await r.json();
  }catch(_){
    return null;
  }
}

function formatDate(value){
  if(!value)return '';
  const date=new Date(value);
  if(Number.isNaN(date.getTime()))return '';
  return date.toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'});
}

async function switchConsultation(purchaseId){
  const r=await fetch('/api/v1/access/switch/'+encodeURIComponent(purchaseId),{
    method:'POST',
    credentials:'same-origin'
  });
  const j=await r.json().catch(()=>({}));
  if(!r.ok){
    alert(j.detail||'That consultation is no longer available.');
    return;
  }
  location.href=j.destination||'/';
}

function renderConsultationHistory(access,container){
  const items=(access.consultations||[]).filter(x=>x.valid);
  if(items.length<=1)return;

  const box=document.createElement('div');
  box.className='consultation-history';
  const title=document.createElement('div');
  title.className='eyebrow';
  title.textContent='Your active consultations';
  box.appendChild(title);

  items.forEach(item=>{
    const row=document.createElement('div');
    row.className='consultation-history-row';
    const label=document.createElement('span');
    label.textContent=(item.completed?'Completed consultation':'Assessment in progress')+
      (item.purchased_at?' · '+formatDate(item.purchased_at):'');
    const button=document.createElement('button');
    button.className='btn secondary';
    button.type='button';
    button.textContent=item.active?'Currently open':'Open';
    button.disabled=Boolean(item.active);
    button.onclick=()=>switchConsultation(item.purchase_id);
    row.append(label,button);
    box.appendChild(row);
  });
  container.appendChild(box);
}

function prepareNewPurchaseMode(access,c){
  $$('.checkout-btn').forEach(button=>{
    button.textContent='Start a new consultation — $'+c.product_price_usd;
    button.onclick=beginCheckout;
  });
  const card=document.querySelector('#offer .grid2 > .card');
  if(!card)return;
  const eyebrow=card.querySelector('.eyebrow');
  const description=card.querySelector('p.muted');
  if(eyebrow)eyebrow.textContent='New consultation';
  if(description)description.textContent=
    'A new purchase creates a separate consultation with a fresh '+c.access_days+'-day private access window. Your current consultation is not overwritten.';
  if(access?.valid){
    const back=document.createElement('button');
    back.type='button';
    back.className='btn secondary block';
    back.textContent=access.completed?'Open current consultation':'Continue current assessment';
    back.onclick=()=>{location.href=access.completed?(access.report_url||'/report'):'/start'};
    card.appendChild(back);
  }
}

function activateReturningCustomer(access,c){
  const completed=Boolean(access.completed);
  const destination=completed?(access.report_url||'/report'):'/start';
  const label=completed?'Open my consultation':'Continue my assessment';

  $$('.checkout-btn').forEach(button=>{
    button.textContent=label;
    button.onclick=()=>{location.href=destination};
  });

  const offerCard=document.querySelector('#offer .grid2 > .card');
  if(!offerCard)return;

  const eyebrow=offerCard.querySelector('.eyebrow');
  const price=offerCard.querySelector('.price');
  const description=offerCard.querySelector('p.muted');
  if(eyebrow)eyebrow.textContent='Your access is active';
  if(price)price.innerHTML='<span class="returning-access">Paid access detected</span>';
  if(description){
    const until=access.expires_at?formatDate(access.expires_at):'the end of the access window';
    description.textContent=completed
      ?'Your private consultation is available until '+until+'. You do not need to purchase again to reopen it.'
      :'Your purchase is active. Continue the assessment before '+until+' without another payment.';
  }

  if(completed){
    const newButton=document.createElement('button');
    newButton.type='button';
    newButton.className='btn secondary block new-consultation-btn';
    newButton.textContent='Start another consultation — $'+c.product_price_usd;
    newButton.onclick=()=>{location.href='/?new=1#offer'};
    offerCard.appendChild(newButton);

    const note=document.createElement('p');
    note.className='privacy-hint';
    note.textContent='Use this when your situation has materially changed or you want a fresh consultation. Each new consultation is a separate one-time purchase.';
    offerCard.appendChild(note);
  }

  renderConsultationHistory(access,offerCard);
}

function showEndedAccess(access,c){
  $$('.checkout-btn').forEach(button=>{
    button.textContent='Start a new consultation — $'+c.product_price_usd;
    button.onclick=beginCheckout;
  });
  const card=document.querySelector('#offer .grid2 > .card');
  if(!card)return;
  const eyebrow=card.querySelector('.eyebrow');
  const description=card.querySelector('p.muted');
  if(eyebrow)eyebrow.textContent='Previous access ended';
  if(description){
    const reason=access.state==='expired'
      ?'Your previous '+c.access_days+'-day consultation window has ended.'
      :'Your previous consultation is no longer active.';
    description.textContent=reason+' A new $'+c.product_price_usd+' purchase starts a completely new assessment and consultation.';
  }
}

function showCheckoutReturnNotice(){
  const params=new URLSearchParams(location.search);
  if(params.get('checkout')!=='cancelled')return;

  const notice=document.createElement('section');
  notice.className='checkout-return-notice';
  notice.setAttribute('role','status');
  notice.setAttribute('aria-live','polite');

  const inner=document.createElement('div');
  inner.className='wrap checkout-return-inner';

  const copy=document.createElement('div');
  copy.innerHTML='<div class="eyebrow">Checkout canceled</div><strong>No payment was completed.</strong><p>You can continue browsing or return to the offer whenever you are ready.</p>';

  const actions=document.createElement('div');
  actions.className='checkout-return-actions';

  const retry=document.createElement('button');
  retry.type='button';
  retry.className='btn secondary';
  retry.textContent='Return to the offer';
  retry.onclick=()=>{
    document.querySelector('#offer')?.scrollIntoView({behavior:'smooth',block:'start'});
    window.setTimeout(()=>document.querySelector('#offer .checkout-btn')?.focus(),350);
  };

  const dismiss=document.createElement('button');
  dismiss.type='button';
  dismiss.className='checkout-notice-dismiss';
  dismiss.setAttribute('aria-label','Dismiss checkout canceled message');
  dismiss.textContent='×';
  dismiss.onclick=()=>notice.remove();

  actions.append(retry,dismiss);
  inner.append(copy,actions);
  notice.appendChild(inner);

  const nav=document.querySelector('body[data-page="landing"] > .wrap:first-child');
  if(nav)nav.insertAdjacentElement('afterend',notice);
  else document.body.prepend(notice);

  params.delete('checkout');
  const query=params.toString();
  history.replaceState(null,'',location.pathname+(query?'?'+query:'')+location.hash);
}

async function initLanding(){
  const c=await initCommon();
  fire('ViewContent',{content_name:'The Path Finder',value:c.product_price_usd,currency:'USD'});
  cleanCampaignQuery();
  showCheckoutReturnNotice();
  $$('.price-value').forEach(x=>x.textContent='$'+c.product_price_usd);
  document.querySelectorAll('.access-days').forEach(x=>x.textContent=String(c.access_days));

  const access=await existingAccess();
  const forceNew=qs().new==='1';

  if(forceNew){
    prepareNewPurchaseMode(access,c);
    return;
  }

  if(access?.valid){
    activateReturningCustomer(access,c);
    return;
  }

  if(access && !access.valid){
    showEndedAccess(access,c);
    return;
  }

  $$('.checkout-btn').forEach(b=>b.onclick=beginCheckout);
}

window.PathFinder={config,fire,fireOnce,initCommon,acquisition};
window.addEventListener('DOMContentLoaded',()=>{
  if(document.body.dataset.page==='landing')initLanding();
  else initCommon();
});
