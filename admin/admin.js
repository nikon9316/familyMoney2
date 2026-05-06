let csrfToken = sessionStorage.getItem('ff_admin_csrf') || '';
let isSuperadmin = sessionStorage.getItem('ff_is_superadmin') === 'true';
let lastData = null;

function el(tag, text, cls) { const e = document.createElement(tag); if (cls) e.className = cls; e.textContent = text ?? ''; return e; }
function setStatus(text) { sessionStatus.textContent = text; }
function money(v){ return Number(v||0).toLocaleString('ru-RU'); }

async function loginAdmin() {
  try {
    const r = await fetch('/api/admin/login', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({admin_token:token.value.trim(), superadmin_token:superToken.value.trim()})});
    if (!r.ok) throw new Error(await r.text());
    const d = await r.json();
    csrfToken = d.csrf; isSuperadmin = !!d.is_superadmin;
    sessionStorage.setItem('ff_admin_csrf', csrfToken); sessionStorage.setItem('ff_is_superadmin', String(isSuperadmin));
    token.value=''; superToken.value=''; setStatus(isSuperadmin ? 'Вход выполнен: superadmin' : 'Вход выполнен: admin');
    await load();
  } catch(e){ alert('Ошибка входа: '+e.message); }
}
async function logoutAdmin(){ try{ await fetch('/api/admin/logout',{method:'POST',headers:{'X-CSRF-Token':csrfToken}}); }catch(_){ } csrfToken=''; isSuperadmin=false; sessionStorage.clear(); document.querySelectorAll('#stats,#backups,#families,#users,#adminAudit,#familyDetail').forEach(x=>x.innerHTML=''); setStatus('Вы вышли из админки'); }
async function api(url, opts={}){ opts.headers={...(opts.headers||{})}; if (!(opts.body instanceof FormData)) opts.headers['Content-Type']='application/json'; if (csrfToken && !['GET', undefined].includes(opts.method)) opts.headers['X-CSRF-Token']=csrfToken; const r=await fetch(url, opts); if(!r.ok) throw new Error(await r.text()); return r.json(); }
async function load(){ try{ const params=new URLSearchParams(); if(auditAction.value)params.set('action',auditAction.value); if(auditEntity.value)params.set('entity_type',auditEntity.value); if(auditFrom.value)params.set('date_from',auditFrom.value); if(auditTo.value)params.set('date_to',auditTo.value); const d=await api('/api/admin/stats'+(params.toString()?'?'+params:'')); lastData=d; render(d); }catch(e){ alert('Ошибка админки: '+e.message); } }

function render(d){ renderStats(d.stats||{}); drawCharts(d.charts||{}); renderBackups(d.backups||[]); renderFamilies(d.families||[]); renderUsers(d.users||[]); renderAdminAudit(d.admin_audit_logs||[]); }
function renderStats(s){ stats.innerHTML=''; Object.entries(s).forEach(([k,v])=>{ const c=el('div','', 'card'); c.append(el('b',k), el('span',String(v))); stats.append(c); }); }
function drawBar(canvas, labels, series){ const ctx=canvas.getContext('2d'); const w=canvas.width=canvas.clientWidth*devicePixelRatio; const h=canvas.height=220*devicePixelRatio; ctx.clearRect(0,0,w,h); ctx.scale(devicePixelRatio,devicePixelRatio); const cw=canvas.clientWidth, ch=220, pad=32; const max=Math.max(1,...series.flatMap(s=>s.data)); ctx.strokeStyle='#e6eaf0'; ctx.beginPath(); ctx.moveTo(pad, ch-pad); ctx.lineTo(cw-pad, ch-pad); ctx.stroke(); const n=labels.length, gap=2, group=(cw-pad*2)/Math.max(1,n), bw=Math.max(2,(group-gap*3)/series.length); labels.forEach((lab,i)=>{ series.forEach((s,si)=>{ const val=s.data[i]||0; const bh=(ch-pad*2)*(val/max); const x=pad+i*group+si*bw+gap; const y=ch-pad-bh; ctx.fillStyle=s.color; ctx.fillRect(x,y,bw,bh); }); }); ctx.fillStyle='#667085'; ctx.font='11px sans-serif'; ctx.fillText(labels[0]||'', pad, ch-8); ctx.fillText(labels[labels.length-1]||'', cw-pad-42, ch-8); ctx.fillStyle='#182230'; ctx.fillText(String(Math.round(max)), pad, 14); }
function drawCharts(ch){ drawBar(moneyChart, ch.labels||[], [{data:ch.income||[],color:'#16a34a'},{data:ch.expense||[],color:'#dc2626'}]); drawBar(activityChart, ch.labels||[], [{data:ch.transactions||[],color:'#2563eb'},{data:ch.new_users||[],color:'#d97706'},{data:ch.new_families||[],color:'#7c3aed'}]); }

function renderBackups(list){ backups.innerHTML=''; if(!list.length){backups.append(el('p','Backup пока нет','hint'));return;} list.forEach(b=>{ const row=el('div','','row'); row.append(el('span',`${b.name} · ${(b.size/1024).toFixed(1)} KB · ${b.created_at}`)); const actions=el('div','','actions'); const a=el('button','Скачать','light'); a.addEventListener('click',()=>downloadBackup(b.name)); actions.append(a); row.append(actions); backups.append(row); }); }
function renderFamilies(list){ families.innerHTML=''; list.forEach(f=>{ const row=el('div','','row'); row.append(el('span',`#${f.id} ${f.name} · код ${f.invite_code} · участников ${f.members_count}`)); const actions=el('div','','actions'); const btn=el('button','Открыть карточку'); btn.addEventListener('click',()=>familyInfo(f.id)); const ops=el('button','Операции','light'); ops.addEventListener('click',()=>familyOperations(f.id)); actions.append(btn,ops); row.append(actions); families.append(row); }); }
function renderUsers(list){ users.innerHTML=''; list.forEach(u=>{ const row=el('div','',`row ${u.is_blocked?'blocked':''}`); const status=u.is_blocked? ' · ЗАБЛОКИРОВАН':' · активен'; row.append(el('span',`#${u.id} ${u.full_name} · tg:${u.telegram_id} · family:${u.family_id}${status}`)); const actions=el('div','','actions'); const sel=document.createElement('select'); ['admin','husband','wife','member'].forEach(r=>{const o=document.createElement('option');o.value=r;o.textContent=r;o.selected=u.role===r;sel.append(o);}); const roleBtn=el('button','Сменить роль','light'); roleBtn.addEventListener('click',()=>setRole(u.id,sel.value)); const blockBtn=el('button',u.is_blocked?'Разблокировать':'Заблокировать',u.is_blocked?'':'danger'); blockBtn.addEventListener('click',()=>setBlocked(u.id,!u.is_blocked)); actions.append(sel,roleBtn,blockBtn); row.append(actions); users.append(row); }); }
function renderAdminAudit(list){ adminAudit.innerHTML=''; if(!list.length){adminAudit.append(el('p','Пока нет admin-действий','hint'));return;} list.forEach(a=>{ const div=el('div','','audit-item'); div.append(el('span',a.action,'badge'), document.createTextNode(`${a.created_at} · ${a.admin_label||''} · ${a.ip_address||''} · ${a.details||''}`)); adminAudit.append(div); }); }

async function familyInfo(id){ try{ const d=await api(`/api/admin/families/${id}`); familyDetail.innerHTML=''; const grid=el('div','','detail-grid'); const blocks=[['Сводка',d.summary],['Месяц',d.month_summary],['Участники',d.members],['Кошельки',d.wallets],['Долги',d.debts],['Цели',d.goals]]; blocks.forEach(([title,data])=>{ const b=el('div','','mini'); b.append(el('h3',title)); const pre=el('pre',JSON.stringify(data,null,2)); b.append(pre); grid.append(b); }); familyDetail.append(grid); renderOperationsTable(d.recent||[], 'Последние операции семьи'); }catch(e){alert(e.message);} }
async function familyOperations(id){ try{ const d=await api(`/api/admin/families/${id}/operations?limit=300`); familyDetail.innerHTML=''; renderOperationsTable(d.operations||[], `Операции семьи #${id}`); }catch(e){alert(e.message);} }
function renderOperationsTable(rows,title){ const box=el('div','','mini'); box.append(el('h3',title)); const table=document.createElement('table'); table.className='table'; table.innerHTML='<thead><tr><th>ID</th><th>Дата</th><th>Тип</th><th>Сумма</th><th>Кошелек</th><th>Категория</th><th>Пользователь</th><th>Комментарий</th></tr></thead>'; const tb=document.createElement('tbody'); rows.forEach(r=>{ const tr=document.createElement('tr'); [r.id,r.created_at,r.type,`${r.amount} ${r.currency}`,r.wallet_name,r.category_name,r.user_name,r.comment].forEach(v=>tr.append(el('td',v??''))); tb.append(tr); }); table.append(tb); box.append(table); familyDetail.append(box); }

async function createBackup(){ try{ const d=await api('/api/admin/backup',{method:'POST'}); renderBackups(d.backups||[]); alert('Backup создан'); }catch(e){alert(e.message);} }
async function requestRestoreCode(){ try{ const d=await api('/api/admin/restore/request',{method:'POST'}); restoreOtp.value=''; alert(d.message||'OTP отправлен'); }catch(e){alert(e.message);} }
async function restoreBackup(){ const file=restoreFile.files[0]; if(!file)return alert('Выбери backup-файл'); if(!restoreOtp.value.trim())return alert('Нужен OTP код'); if(!confirm('Восстановление заменит текущую базу. Продолжить?'))return; const fd=new FormData(); fd.append('otp',restoreOtp.value.trim()); fd.append('backup',file); try{ const d=await api('/api/admin/restore',{method:'POST',body:fd}); alert(d.message); restoreOtp.value=''; await load(); }catch(e){alert(e.message);} }
async function setRole(user_id,role){ try{ const d=await api('/api/admin/users/role',{method:'POST',body:JSON.stringify({user_id,role})}); renderUsers(d.users); }catch(e){alert(e.message);} }
async function setBlocked(user_id,blocked){ try{ const d=await api('/api/admin/users/block',{method:'POST',body:JSON.stringify({user_id,blocked})}); renderUsers(d.users); }catch(e){alert(e.message);} }
async function downloadBackup(name){ try{ const r=await fetch(`/api/admin/backup/${encodeURIComponent(name)}`,{credentials:'same-origin'}); if(!r.ok)throw new Error(await r.text()); const blob=await r.blob(); downloadBlob(blob,name); }catch(e){alert(e.message);} }
function downloadBlob(blob,name){ const url=URL.createObjectURL(blob); const a=document.createElement('a'); a.href=url; a.download=name; a.click(); URL.revokeObjectURL(url); }
async function exportAuditLogs(){ const params=new URLSearchParams(); if(auditAction.value)params.set('action',auditAction.value); if(auditEntity.value)params.set('entity_type',auditEntity.value); if(auditFrom.value)params.set('date_from',auditFrom.value); if(auditTo.value)params.set('date_to',auditTo.value); const r=await fetch('/api/admin/audit/export.xlsx?'+params.toString(),{credentials:'same-origin'}); if(!r.ok)return alert(await r.text()); downloadBlob(await r.blob(),'admin_audit_logs.xlsx'); }
if (csrfToken) load();

// --- Level 4.4.2: strict CSP-safe static event bindings ---
function bindAdminStaticEvents(){
  const bind=(id,fn)=>{const el=document.getElementById(id); if(el) el.addEventListener('click',fn);};
  bind('loginAdminBtn', loginAdmin);
  bind('logoutAdminBtn', logoutAdmin);
  bind('createBackupBtn', createBackup);
  bind('requestRestoreCodeBtn', requestRestoreCode);
  bind('restoreBackupBtn', restoreBackup);
  bind('exportAuditLogsBtn', exportAuditLogs);
  bind('adminFilterBtn', load);
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', bindAdminStaticEvents); else bindAdminStaticEvents();
