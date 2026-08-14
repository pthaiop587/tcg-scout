/* ---------------- tabs ---------------- */
const tabs = Array.from(document.querySelectorAll('[role="tab"]'));
function show(id){
  tabs.forEach(t => {
    const on = t.id === id;
    t.setAttribute('aria-selected', on ? 'true' : 'false');
    document.getElementById(t.getAttribute('aria-controls')).hidden = !on;
  });
  try { history.replaceState(null, '', '#' + id.slice(2)); } catch(e){}
}
tabs.forEach(t => t.addEventListener('click', () => show(t.id)));
document.querySelector('[role="tablist"]').addEventListener('keydown', e => {
  const i = tabs.indexOf(document.activeElement);
  if (i < 0) return;
  let n = null;
  if (e.key === 'ArrowRight') n = (i + 1) % tabs.length;
  if (e.key === 'ArrowLeft')  n = (i - 1 + tabs.length) % tabs.length;
  if (n === null) return;
  e.preventDefault(); tabs[n].focus(); show(tabs[n].id);
});
const start = (location.hash || '').slice(1);
if (start && document.getElementById('t-' + start)) show('t-' + start);

const esc = s => (s||'').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'})[c]);
const money = n => '$' + n.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});

/* ---------------- shelf search ---------------- */
const ROWS = __ROWS__;
const tb=document.getElementById('tb'), q=document.getElementById('q'),
      cnt=document.getElementById('count'), empty=document.getElementById('empty'),
      fStore=document.getElementById('f-store'), fBuy=document.getElementById('f-buy');
function renderShelf(){
  const term=q.value.trim().toLowerCase();
  const onlyStore=fStore.getAttribute('aria-pressed')==='true';
  const onlyBuy=fBuy.getAttribute('aria-pressed')==='true';
  const list=ROWS.filter(r=>{
    if(onlyStore && r.w!=='store') return false;
    if(onlyBuy && r.x<2) return false;
    if(!term) return true;
    return (r.p+' '+r.s+' '+r.g+' '+(r.c||'')).toLowerCase().indexOf(term)>-1;
  });
  cnt.textContent=list.length+' of '+ROWS.length+' shown';
  empty.hidden=list.length>0;
  tb.innerHTML=list.map(r=>{
    const cls=r.x>=2?'x-hi':(r.x>=1.5?'x-mid':'x-lo');
    const ch=r.c ? '<b>'+esc(r.c)+'</b><br>'+money(r.cp)+(r.cr?' &middot; '+esc(r.cr):'')
                 : '<span style="opacity:.55">not listed yet</span>';
    return '<tr><td><div class="prod">'+esc(r.p)+'</div><div class="setname">'+esc(r.g)+' &middot; '+esc(r.s)+'</div></td>'
      +'<td><span class="wtag w-'+r.w+'">'+r.w+'</span></td>'
      +'<td class="num mono">'+money(r.r)+'</td><td class="num mono">'+money(r.m)+'</td>'
      +'<td class="num mono xcell '+cls+'">'+r.x.toFixed(2)+'&times;</td>'
      +'<td class="chasecell mono">'+ch+'</td></tr>';
  }).join('');
}
const tog=b=>{b.setAttribute('aria-pressed',b.getAttribute('aria-pressed')==='true'?'false':'true');renderShelf();};
q.addEventListener('input',renderShelf);
fStore.addEventListener('click',()=>tog(fStore));
fBuy.addEventListener('click',()=>tog(fBuy));
renderShelf();

/* ---------------- interactive map ---------------- */
const STORES = __STORES__;
const COLOR  = __COLOR__;
const HUNT   = __HUNT__;
const dotsG=document.getElementById('dots'), mq=document.getElementById('mq'),
      mcount=document.getElementById('mcount'), mempty=document.getElementById('mempty'),
      slist=document.getElementById('storelist');
const chainBtns=Array.from(document.querySelectorAll('#chainchips .ck'));
const radBtns=Array.from(document.querySelectorAll('#radchips .rad'));

/* draw every dot once; filtering just toggles a class */
dotsG.innerHTML = STORES.map((s,i)=>
  '<circle cx="'+s.x+'" cy="'+s.y+'" r="'+(s.ch==='Card shop'?7:5.5)+'" '
  +'fill="'+COLOR[s.ch]+'" class="dot" data-i="'+i+'">'
  +'<title>'+esc(s.n)+' &#183; '+s.d+' mi</title></circle>').join('');
const dotEls = Array.from(dotsG.children);

function activeChains(){
  return chainBtns.filter(b=>b.getAttribute('aria-pressed')==='true')
                  .map(b=>b.dataset.chain);
}
function activeRadius(){
  const on = radBtns.find(b=>b.getAttribute('aria-pressed')==='true');
  return on ? parseFloat(on.dataset.r) : 20;
}
function renderMap(){
  const term=mq.value.trim().toLowerCase();
  const chains=activeChains(), rad=activeRadius();
  const keep=new Set();
  STORES.forEach((s,i)=>{
    if(chains.indexOf(s.ch)<0) return;
    if(s.d>rad) return;
    if(term && (s.n+' '+s.a+' '+s.c+' '+s.ch).toLowerCase().indexOf(term)<0) return;
    keep.add(i);
  });
  dotEls.forEach((el,i)=>el.classList.toggle('off', !keep.has(i)));
  const list=STORES.map((s,i)=>({s,i})).filter(o=>keep.has(o.i));
  mcount.textContent=list.length+' of '+STORES.length+' stores';
  mempty.hidden=list.length>0;
  slist.innerHTML=list.slice(0,60).map(o=>{
    const s=o.s;
    const addr=[s.a, s.c].filter(Boolean).join(', ') || 'address not mapped';
    const url='https://www.google.com/maps/search/?api=1&query='+s.lat+','+s.lon;
    return '<a class="st" href="'+url+'" target="_blank" rel="noopener">'
      +'<span class="swatch" style="background:'+COLOR[s.ch]+'"></span>'
      +'<span class="body"><span class="nm">'+esc(s.ch)+'</span>'
      +'<span class="ad">'+esc(addr)+'</span>'
      +'<span class="hunt">'+HUNT[s.ch]+'</span></span>'
      +'<span><span class="mi">'+s.d+' mi</span><span class="go">Directions &rarr;</span></span></a>';
  }).join('');
}
mq.addEventListener('input',renderMap);
chainBtns.forEach(b=>b.addEventListener('click',()=>{
  b.setAttribute('aria-pressed', b.getAttribute('aria-pressed')==='true'?'false':'true');
  renderMap();
}));
radBtns.forEach(b=>b.addEventListener('click',()=>{
  radBtns.forEach(o=>o.setAttribute('aria-pressed','false'));
  b.setAttribute('aria-pressed','true');
  renderMap();
}));
renderMap();
