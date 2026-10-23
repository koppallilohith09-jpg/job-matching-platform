export const $=s=>document.querySelector(s);
export function el(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n}
export function notify(text,error=false){$('#status').textContent=text;$('#status').classList.toggle('error',error)}
export async function api(url,method='GET',body){const r=await fetch(url,{method,headers:{'Content-Type':'application/json','X-Workspace':'1'},...(body===undefined?{}:{body:JSON.stringify(body)})});const b=await r.json();if(!r.ok)throw Error(typeof b.detail==='string'?b.detail:b.error||'Please check the submitted values.');return b}
export function button(label,fn,cls=''){const b=el('button',label,cls);b.addEventListener('click',async()=>{b.disabled=true;try{await fn()}catch(e){notify(e.message,true)}finally{b.disabled=false}});return b}
export function td(value,cls){return el('td',String(value),cls)}
export const money=n=>new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:2}).format(n);
export const pct=n=>(n*100).toFixed(1)+'%';
export function metric(label,value,caption){const div=el('div',undefined,'metric');div.append(el('label',label),el('strong',value),el('small',caption||''));return div}
export function tag(value,kind=''){return el('span',value,'tag '+kind)}
export function facts(pairs){const dl=el('dl',undefined,'facts');for(const [key,val]of pairs){const div=el('div');div.append(el('dt',key),el('dd',String(val)));dl.append(div)}return dl}
export function textList(items){const list=el('ul',undefined,'list');items.forEach(x=>list.append(el('li',x)));return list}
export function download(name,content,type='text/csv'){const url=URL.createObjectURL(new Blob([content],{type})),a=el('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
export function lineChart(canvas,series){const ratio=Math.min(devicePixelRatio||1,2),w=canvas.clientWidth||600,h=canvas.clientHeight||200;canvas.width=w*ratio;canvas.height=h*ratio;const ctx=canvas.getContext('2d');ctx.scale(ratio,ratio);const hi=Math.max(1,...series.flatMap(s=>s.values))*1.1;ctx.font='10px Segoe UI';ctx.fillStyle='#616c66';for(let j=0;j<=4;j++){const y=12+(h-35)*j/4;ctx.strokeStyle='#e8ece2';ctx.beginPath();ctx.moveTo(42,y);ctx.lineTo(w-10,y);ctx.stroke();ctx.fillText(Math.round(hi*(1-j/4)).toLocaleString(),0,y+3)}for(const s of series){ctx.strokeStyle=s.color;ctx.lineWidth=2;ctx.beginPath();s.values.forEach((v,i)=>{const x=42+(w-55)*i/(s.values.length-1||1),y=12+(h-35)*(1-v/hi);i?ctx.lineTo(x,y):ctx.moveTo(x,y)});ctx.stroke()}ctx.fillStyle='#616c66';ctx.fillText('Start',42,h-4);ctx.fillText('End',w-30,h-4)}
export function nav(callback){document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{document.querySelectorAll('[data-view]').forEach(x=>x.classList.toggle('active',x===b));document.querySelectorAll('[id^="view-"]').forEach(x=>x.style.display=x.id==='view-'+b.dataset.view?'block':'none');callback?.(b.dataset.view)})}
window.addEventListener('unhandledrejection',e=>notify(e.reason?.message||'Something went wrong.',true));
