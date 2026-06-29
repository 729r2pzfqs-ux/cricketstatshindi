
let CSH_idx=null,CSH_box=null;
async function CSH_load(){if(CSH_idx)return CSH_idx;
  const base=location.pathname.includes('/players/')||location.pathname.split('/').filter(Boolean).length>0?
    location.origin+'/':'/';
  const r=await fetch(location.origin+'/search-index.json');CSH_idx=await r.json();return CSH_idx;}
function CSH_search(){if(CSH_box){CSH_box.remove();CSH_box=null;return;}
  CSH_box=document.createElement('div');
  CSH_box.style.cssText='position:fixed;inset:0;z-index:200;background:rgba(20,40,25,.45);backdrop-filter:blur(3px);display:flex;align-items:flex-start;justify-content:center;padding-top:10vh';
  CSH_box.innerHTML='<div onclick="event.stopPropagation()" style="width:92%;max-width:560px;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 20px 60px rgba(0,0,0,.3)">'+
    '<input id="cshq" placeholder="खिलाड़ी, टीम, रिकॉर्ड खोजें…" style="width:100%;padding:16px 18px;border:0;outline:0;font-size:16px;border-bottom:1px solid #e2e8e0;font-family:Inter,Noto Sans Devanagari,sans-serif">'+
    '<div id="cshr" style="max-height:60vh;overflow:auto"></div></div>';
  CSH_box.onclick=()=>CSH_search();
  document.body.appendChild(CSH_box);
  const q=document.getElementById('cshq');q.focus();
  CSH_load().then(()=>CSH_render(''));
  q.addEventListener('input',e=>CSH_render(e.target.value));
  q.addEventListener('keydown',e=>{if(e.key==='Escape')CSH_search();
    if(e.key==='Enter'){const a=document.querySelector('#cshr a');if(a)location.href=a.href;}});}
function CSH_render(q){const box=document.getElementById('cshr');if(!box)return;
  q=q.trim().toLowerCase();let res;
  if(!q){res=CSH_idx.slice(0,8);}
  else{res=[];for(const row of CSH_idx){const hay=(row[0]+' '+row[3]).toLowerCase();
    let i=0,ok=true;for(const ch of q){i=hay.indexOf(ch,i);if(i<0){ok=false;break;}i++;}
    if(hay.includes(q)){res.push([0,row]);}else if(ok){res.push([1,row]);}}
    res.sort((a,b)=>a[0]-b[0]);res=res.slice(0,20).map(x=>x[1]);}
  if(!res.length){box.innerHTML='<div style="padding:20px;color:#52635a;font-family:Noto Sans Devanagari">कोई परिणाम नहीं</div>';return;}
  box.innerHTML=res.map(r=>'<a href="'+location.origin+r[1]+'" style="display:flex;justify-content:space-between;gap:10px;padding:11px 18px;text-decoration:none;border-bottom:1px solid #f0f3f0;color:#16241b">'+
    '<span style="font-weight:600">'+r[0]+'</span><span style="font-size:12px;color:#15803d;font-family:Noto Sans Devanagari;align-self:center">'+r[2]+'</span></a>').join('');}
document.addEventListener('keydown',e=>{if((e.key==='/'||((e.metaKey||e.ctrlKey)&&e.key==='k'))&&!/INPUT|TEXTAREA/.test(document.activeElement.tagName)){e.preventDefault();CSH_search();}});
