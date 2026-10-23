import {$,el,api,notify,button,money,pct,metric,tag,facts} from './common.js';
let state,register=false;
async function load(){
 state=await api('/api/state');const user=state.user;
 $('#account-tag').textContent=user?user.role:'Visitor';$('#account-open').textContent=user?user.name:'Sign in / create account';
 $('#visitor').hidden=!!user;$('#profile-form').hidden=!user||user.role!=='candidate';$('#employer-info').hidden=!user||user.role!=='employer';$('#logout').hidden=!user;
 if(user?.role==='candidate'){$('#skills').value=state.profile.skills.join(', ');$('#summary').value=state.profile.summary}
 $('#metrics').replaceChildren(metric('Roles listed',state.jobs.length,'in this local workspace'),metric('Remote opportunities',state.jobs.filter(j=>j.location==='Remote').length,'location supplied by poster'),metric('Your listed skills',user?.role==='candidate'?state.profile.skills.length:'—','editable and self-reported'),metric('Account',user?user.role==='candidate'?'Candidate':'Employer':'Visitor',user?'Signed in locally':'Browse before registering'));
 renderJobs();
}
function renderJobs(){
 const q=$('#query').value.toLowerCase(),location=$('#location').value,list=state.jobs.filter(j=>(j.title+' '+j.company+' '+j.skills.join(' ')).toLowerCase().includes(q)&&(!location||j.location===location)&&(!$('#matches-only').checked||j.match.score>=.5));
 $('#results-count').textContent=list.length+' roles · salary ranges in USD per year';const container=$('#jobs');container.replaceChildren();
 for(const j of list){const card=el('article',undefined,'item'),tags=el('div',undefined,'pill-list');tags.append(tag(j.location),tag(j.demo?'Fictional example':'Workspace posting'));card.append(tags,el('h3',j.title),el('p',j.company),el('p',money(j.salary_min)+'–'+money(j.salary_max)+' / year'));const skills=el('div',undefined,'pill-list');j.skills.forEach(s=>skills.append(tag(s,state.profile?.skills.includes(s.toLowerCase())?'good':'')));card.append(skills);
  if(state.user?.role==='candidate')card.append(el('p',pct(j.match.score)+' listed skill coverage','note'));
  card.append(button('View role',()=>openJob(j),'plain'));container.append(card);
 }
 if(!list.length)container.append(el('p','No roles match these filters.'));
}
function openJob(j){
 $('#job-title').textContent=j.title;const d=$('#job-detail');d.replaceChildren(el('p',j.company+' · '+j.location),facts([['Salary',money(j.salary_min)+'–'+money(j.salary_max)],['Source',j.demo?'Fictional example':'Workspace employer']]),el('div','Responsibilities','section-label'),el('p',j.description),el('div','Required skills','section-label'),el('p',j.skills.join(', ')));
 if(state.user?.role==='candidate'){d.append(el('p','Your listed matches: '+(j.match.matched.join(', ')||'None')+'. Missing: '+(j.match.missing.join(', ')||'None')+'.','note'),button(j.demo?'Apply to example locally':'Apply locally',async()=>{await api('/api/jobs/'+j.id+'/apply','POST');notify('Application saved locally. No external message was sent.');$('#job-dialog').close()},'primary'))}
 else d.append(el('p','Sign in as a candidate to apply.','note'));$('#job-dialog').showModal();
}
$('#job-close').onclick=()=>$('#job-dialog').close();$('#query').oninput=renderJobs;$('#location').onchange=renderJobs;$('#matches-only').onchange=renderJobs;
function accountMode(value){register=value;$('#register-fields').hidden=!value;$('#account-submit').textContent=value?'Create account':'Sign in';$('#login-tab').classList.toggle('active',!value);$('#register-tab').classList.toggle('active',value);$('#password').autocomplete=value?'new-password':'current-password';$('#password').minLength=value?12:1;$('#display-name').required=value;$('#account-error').textContent=''}
$('#login-tab').onclick=()=>accountMode(false);$('#register-tab').onclick=()=>accountMode(true);$('#account-open').onclick=()=>{if(state.user)notify('Signed in as '+state.user.name+'. Use Sign out to switch accounts.');else $('#account-dialog').showModal()};$('#account-close').onclick=()=>$('#account-dialog').close();
$('#account-form').onsubmit=async e=>{
 e.preventDefault();const b=e.submitter;b.disabled=true;$('#account-error').textContent='';
 try{const credentials={username:$('#username').value.trim().toLowerCase(),password:$('#password').value};if(register)await api('/api/register','POST',{...credentials,name:$('#display-name').value.trim(),role:$('#role').value});await api('/api/login','POST',credentials);$('#password').value='';$('#account-dialog').close();await load();notify('Signed in locally.')}catch(e){$('#account-error').textContent=e.message}finally{b.disabled=false}
};
$('#logout').onclick=async()=>{await api('/api/logout','POST');await load();$('#applications').replaceChildren();notify('Signed out.')};
$('#profile-form').onsubmit=async e=>{e.preventDefault();await api('/api/profile','POST',{skills:$('#skills').value.split(',').map(s=>s.trim()).filter(Boolean),summary:$('#summary').value});await load();notify('Profile saved. Skill coverage updated.')};
$('#resume').onchange=async e=>{
 const file=e.target.files[0];if(!file)return;if(file.size>3000000)return notify('Resume must be under 3 MB.',true);e.target.disabled=true;
 try{const bytes=new Uint8Array(await file.arrayBuffer());let binary='';for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));const parsed=await api('/api/resume','POST',{filename:file.name,content:btoa(binary)});const skills=new Set([...$('#skills').value.split(',').map(s=>s.trim()).filter(Boolean),...parsed.skills]);$('#skills').value=[...skills].join(', ');$('#resume-result').textContent=parsed.skills.length+' recognized skill labels from '+parsed.characters+' characters. Review and Save profile to keep them.';}finally{e.target.disabled=false;e.target.value=''}
};
async function applications(){
 const d=$('#applications');d.replaceChildren();if(!state.user){d.append(el('p','Sign in to view applications.'));return}
 const rows=await api('/api/applications');$('#applications-title').textContent=state.user.role==='employer'?'Received applications':'Your applications';
 $('#applications-help').textContent=state.user.role==='employer'?'Only applications to your own postings appear here.':'Track applications submitted in this workspace.';
 if(!rows.length)d.append(el('p','No applications yet.'));
 const transitions={Received:['Reviewing','Rejected'],Reviewing:['Interview','Rejected'],Interview:['Offered','Rejected'],Offered:[],Rejected:[],Withdrawn:[]};
 for(const a of rows){const item=el('div',undefined,'result');item.append(el('h3',a.job.title),el('p',a.job.company+' · '+a.candidate+' · '+new Date(a.created).toLocaleDateString()),tag(a.status));const actions=el('div',undefined,'row');const next=state.user.role==='employer'?transitions[a.status]:['Received','Reviewing','Interview'].includes(a.status)?['Withdrawn']:[];next.forEach(s=>actions.append(button(s,async()=>{await api('/api/applications/'+a.id,'POST',{status:s});await applications();notify('Application status updated.')})));item.append(actions,el('hr',undefined,'rule'));d.append(item)}
}
$('#refresh-applications').onclick=applications;
document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{document.querySelectorAll('[data-view]').forEach(x=>x.classList.toggle('active',x===b));document.querySelectorAll('[id^="view-"]').forEach(x=>x.style.display=x.id==='view-'+b.dataset.view?'block':'none');if(b.dataset.view==='applications')applications();if(b.dataset.view==='post'&&state.user?.role!=='employer')notify('Sign in with an employer account to post a role.',true)});
$('#go-post').onclick=()=>document.querySelector('[data-view="post"]').click();
$('#posting-form').onsubmit=async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(e.target));data.skills=data.skills.split(',').map(s=>s.trim().toLowerCase()).filter(Boolean);data.salary_min=Number(data.salary_min);data.salary_max=Number(data.salary_max);await api('/api/jobs','POST',data);e.target.reset();await load();document.querySelector('[data-view="main"]').click();notify('Role published to this local workspace.')};await load();
