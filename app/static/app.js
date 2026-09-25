const $=(s)=>document.querySelector(s);
const $$=(s)=>[...document.querySelectorAll(s)];

function qs(){
  return Object.fromEntries(new URLSearchParams(location.search).entries());
}

function acquisition(){
  const q=qs();
  return {
    utm_source:q.utm_source||'',
    utm_medium:q.utm_medium||'',
    utm_campaign:q.utm_campaign||'',
    utm_content:q.utm_content||'',
    utm_term:q.utm_term||'',
    landing_variant:'v1'
  };
}

async function config(){
  return fetch('/api/v1/config/public').then(r=>r.json());
}

function fire(name,data={}){
  if(window.fbq)fbq('track',name,data);
}

function installPixel(id){
  if(!id||window.fbq)return;
  !function(f,b,e,v,n,t,s){
    if(f.fbq)return;
    n=f.fbq=function(){n.callMethod?n.callMethod.apply(n,arguments):n.queue.push(arguments)};
    if(!f._fbq)f._fbq=n;
    n.push=n;
    n.loaded=!0;
    n.version='2.0';
    n.queue=[];
    t=b.createElement(e);
    t.async=!0;
    t.src=v;
    s=b.getElementsByTagName(e)[0];
    s.parentNode.insertBefore(t,s);
  }(window,document,'script','https://connect.facebook.net/en_US/fbevents.js');
  fbq('init',id);
  fbq('track','PageView');
}

function metaConsent(id){
  if(!id)return;
  const saved=localStorage.getItem('meta-ads-consent');
  if(saved==='accepted'){
    installPixel(id);
    return;
  }
  if(saved==='declined')return;

  const box=document.createElement('div');
  box.className='consent-banner';
  box.innerHTML='<div><strong>Advertising measurement</strong><p>We use optional Meta advertising measurement only with your choice. It never changes your Path recommendation.</p></div><div class="consent-actions"><button class="btn secondary" data-no>Decline</button><button class="btn" data-yes>Accept</button></div>';
  document.body.appendChild(box);
  box.querySelector('[data-yes]').onclick=()=>{
    localStorage.setItem('meta-ads-consent','accepted');
    box.remove();
    installPixel(id);
  };
  box.querySelector('[data-no]').onclick=()=>{
    localStorage.setItem('meta-ads-consent','declined');
    box.remove();
  };
}

async function initCommon(){
  const c=await config();
  metaConsent(c.meta_pixel_id);
  document.querySelectorAll('.support-email').forEach(x=>{
    x.textContent=c.support_email;
    x.href='mailto:'+c.support_email;
  });
  return c;
}

async function beginCheckout(){
  const c=await initCommon();
  fire('InitiateCheckout',{value:c.product_price_usd,currency:'USD'});
  const r=await fetch('/api/v1/checkout/session',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({acquisition:acquisition()})
  });
  const j=await r.json();
  if(!r.ok){
    alert(j.detail||'Checkout failed');
    return;
  }
  location.href=j.url;
}

async function existingAccess(){
  try{
    const r=await fetch('/api/v1/access/me',{credentials:'same-origin'});
    if(!r.ok)return null;
    const data=await r.json();
    return data?.valid?data:null;
  }catch(_){
    return null;
  }
}

function activateReturningCustomer(access){
  const completed=Boolean(access.completed);
  const destination=completed?(access.report_url||'/report'):'/start';
  const label=completed?'Open my consultation':'Continue my assessment';

  $$('.checkout-btn').forEach(button=>{
    button.textContent=label;
    button.onclick=()=>{location.href=destination};
  });

  const offerCard=document.querySelector('#offer .grid2 > .card');
  if(offerCard){
    const eyebrow=offerCard.querySelector('.eyebrow');
    const price=offerCard.querySelector('.price');
    const description=offerCard.querySelector('p.muted');

    if(eyebrow)eyebrow.textContent='Your access is active';
    if(price)price.innerHTML='<span class="returning-access">Paid access detected</span>';
    if(description){
      description.textContent=completed
        ?'Your private consultation is still available in this browser. You do not need to purchase again.'
        :'Your purchase is already active in this browser. Continue the assessment without another payment.';
    }
  }
}

async function initLanding(){
  const c=await initCommon();
  $$('.price-value').forEach(x=>x.textContent='$'+c.product_price_usd);

  const access=await existingAccess();
  if(access){
    activateReturningCustomer(access);
    return;
  }

  $$('.checkout-btn').forEach(b=>b.onclick=beginCheckout);
}

window.PathFinder={config,fire,initCommon};
window.addEventListener('DOMContentLoaded',()=>{
  if(document.body.dataset.page==='landing')initLanding();
  else initCommon();
});
