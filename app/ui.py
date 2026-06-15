"""Panel web (página única) del backup-agent."""

PAGE = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>backup-agent — Respaldos OMV</title>
<style>
  :root{--bg:#0f172a;--card:#1e293b;--mut:#94a3b8;--bd:#334155;--ac:#38bdf8;--ok:#22c55e;--err:#ef4444;--txt:#e2e8f0}
  *{box-sizing:border-box}
  body{margin:0;font-family:system-ui,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--txt);font-size:14px}
  header{display:flex;align-items:center;gap:14px;padding:14px 20px;background:var(--card);border-bottom:1px solid var(--bd);position:sticky;top:0;z-index:5}
  header h1{font-size:17px;margin:0;flex:1}
  .pill{font-size:12px;color:var(--mut)}
  main{max-width:980px;margin:0 auto;padding:18px}
  .card{background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:16px;margin-bottom:16px}
  .card h2{margin:0 0 12px;font-size:15px;display:flex;align-items:center;gap:8px}
  .card h2 .s{font-size:12px;color:var(--mut);font-weight:400}
  label.row{display:flex;align-items:center;gap:9px;padding:6px 4px;border-radius:6px}
  label.row:hover{background:#0b1220}
  .row .meta{color:var(--mut);font-size:12px;margin-left:auto}
  .tag{font-size:11px;padding:1px 6px;border-radius:6px;background:#0b1220;color:var(--mut);border:1px solid var(--bd)}
  .tag.db{color:#fbbf24}.tag.heavy{color:#f87171}.tag.rec{color:var(--ok)}
  button{background:var(--ac);color:#04222e;border:0;border-radius:8px;padding:9px 14px;font-weight:600;cursor:pointer;font-size:14px}
  button.sec{background:#0b1220;color:var(--txt);border:1px solid var(--bd)}
  button:disabled{opacity:.5;cursor:default}
  input,select{background:#0b1220;border:1px solid var(--bd);color:var(--txt);border-radius:7px;padding:7px 9px;font-size:13px}
  table{width:100%;border-collapse:collapse;font-size:13px}
  th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--bd)}
  th{color:var(--mut);font-weight:500}
  .dest{display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:8px;border:1px solid var(--bd);border-radius:8px;margin-bottom:8px}
  pre{background:#0b1220;border:1px solid var(--bd);border-radius:8px;padding:10px;max-height:260px;overflow:auto;font-size:12px;white-space:pre-wrap}
  .muted{color:var(--mut)}
  .ok{color:var(--ok)}.err{color:var(--err)}
  .flex{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
  .grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
  @media(max-width:640px){.grid{grid-template-columns:1fr}}
  .toast{position:fixed;bottom:16px;right:16px;background:var(--card);border:1px solid var(--bd);padding:10px 14px;border-radius:8px;opacity:0;transition:.2s}
  .toast.show{opacity:1}
</style>
</head>
<body>
<header>
  <h1>🗄️ backup-agent <span class="pill" id="ver"></span></h1>
  <span class="pill" id="status">…</span>
  <button class="sec" onclick="scanNow()">Reescanear</button>
  <button id="runBtn" onclick="runBackup()">Respaldar ahora</button>
</header>
<main>

  <div class="card">
    <h2>1 · Qué respaldar <span class="s">(autoescaneo · lo recomendado viene marcado)</span></h2>
    <div id="base"></div>
    <h3 class="muted" style="font-size:13px;margin:12px 0 4px">Bases de datos (se respaldan por dump)</h3>
    <div id="dbs"></div>
    <h3 class="muted" style="font-size:13px;margin:12px 0 4px">Volúmenes Docker</h3>
    <div id="vols"></div>
    <h3 class="muted" style="font-size:13px;margin:12px 0 4px">Stacks (definiciones compose)</h3>
    <div id="comp"></div>
  </div>

  <div class="card">
    <h2>2 · A dónde respaldar</h2>
    <div id="dests"></div>
    <div class="flex" style="margin-top:10px">
      <select id="dtype">
        <option value="rclone">Remote rclone (OneDrive, etc.)</option>
        <option value="local">Carpeta local / disco</option>
      </select>
      <select id="dremote"></select>
      <input id="dpath" placeholder="subcarpeta (ej: Respaldos/omv)" size="22">
      <button class="sec" onclick="addDest()">+ Añadir destino</button>
    </div>
    <p class="muted" id="rcwarn" style="font-size:12px"></p>
  </div>

  <div class="card">
    <h2>3 · Programación</h2>
    <div class="flex">
      <label class="row"><input type="checkbox" id="schEnabled"> Activar respaldo automático</label>
      <span>a las <input id="schTime" type="time" value="03:30"></span>
      <span>conservar <input id="schRet" type="number" min="1" max="60" value="7" style="width:60px"> días</span>
    </div>
    <p class="muted" style="font-size:12px">El propio servicio lleva el reloj; no depende de cron externo.</p>
  </div>

  <div class="flex" style="margin-bottom:16px">
    <button onclick="saveAll()">💾 Guardar configuración</button>
    <span id="saved" class="muted"></span>
  </div>

  <div class="card">
    <h2>Historial</h2>
    <table><thead><tr><th>Fecha</th><th>Origen</th><th>Tamaño</th><th>Destinos</th><th>Resultado</th></tr></thead>
    <tbody id="hist"><tr><td colspan="5" class="muted">—</td></tr></tbody></table>
  </div>

  <div class="card">
    <h2>Registro <span class="s">(últimas líneas)</span> <button class="sec" style="margin-left:auto" onclick="loadLogs()">↻</button></h2>
    <pre id="logs" class="muted">…</pre>
  </div>
</main>
<div class="toast" id="toast"></div>

<script>
let INV=null, CFG=null, REMOTES=[];
const $=id=>document.getElementById(id);
function toast(m){const t=$('toast');t.textContent=m;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),2200);}
async function jget(u){const r=await fetch(u);if(!r.ok)throw new Error(r.status);return r.json();}
async function jpost(u,b){const r=await fetch(u,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b||{})});return r.json();}

function chk(id,label,checked,meta,tags){
  const tg=(tags||[]).map(t=>`<span class="tag ${t.c||''}">${t.t}</span>`).join(' ');
  return `<label class="row"><input type="checkbox" data-k="${id}" ${checked?'checked':''}>
    <span>${label}</span> ${tg} <span class="meta">${meta||''}</span></label>`;
}

async function scanNow(){
  $('status').textContent='escaneando…';
  INV=await jget('/api/scan'); CFG=await jget('/api/settings');
  const rm=await jget('/api/remotes'); REMOTES=rm.remotes||[];
  renderScan(); renderDests(); renderSchedule(); fillRemotes(rm);
  $('status').textContent='listo';
  loadStatus(); loadHistory(); loadLogs();
}

function sel(arr,v){return arr&&arr.indexOf(v)>=0;}

function renderScan(){
  // base: omv config + manifiesto
  let h='';
  const omv=INV.omv||{};
  h+=chk('omv','Configuración de OMV (config.xml)', CFG.include_omv_config!==false,
        omv.available?omv.size_kb+' KB':'no encontrado', omv.available?[{t:'recomendado',c:'rec'}]:[]);
  h+=chk('manifest','Manifiesto (plugins, paquetes, fstab, discos)', CFG.include_manifest!==false,'',[{t:'recomendado',c:'rec'}]);
  const si=INV.system_identities||{};
  h+=chk('sysid','Identidades del sistema (usuarios, contraseñas, Samba)', CFG.include_system_identities===true,
     si.available?(si.items||[]).join(', '):'no disponible (monta /etc y /var/lib/samba)',
     [{t:'sensible',c:'heavy'}]);
  $('base').innerHTML=h;

  $('dbs').innerHTML=(INV.databases||[]).map(d=>chk('db:'+d.key,
     d.container+' · '+d.engine, CFG.databases?sel(CFG.databases,d.key):d.recommended,
     d.database||'', [{t:'dump',c:'db'}, d.has_password?null:{t:'sin clave?',c:'heavy'}].filter(Boolean)
  )).join('')||'<span class="muted">—</span>';

  $('vols').innerHTML=(INV.volumes||[]).map(v=>{
     const tags=[]; if(v.is_database)tags.push({t:'es base→dump',c:'db'});
     if(v.heavy)tags.push({t:'pesado',c:'heavy'}); if(v.anonymous)tags.push({t:'anónimo',c:'heavy'});
     if(v.recommended)tags.push({t:'recomendado',c:'rec'});
     const def=CFG.volumes?sel(CFG.volumes,v.name):v.recommended;
     return chk('vol:'+v.name, v.name, def, v.size, tags);
  }).join('')||'<span class="muted">—</span>';

  const useSel=CFG.compose_stacks&&CFG.compose_stacks.length;
  $('comp').innerHTML=(INV.stacks||[]).map(s=>chk('stack:'+s.path,
     s.name, useSel?sel(CFG.compose_stacks,s.path):s.recommended,
     s.root.split('/').slice(-2,-1)[0]||'', [{t:'recomendado',c:'rec'}]
  )).join('')||'<span class="muted">—</span>';
}

function fillRemotes(rm){
  $('dremote').innerHTML=(rm.remotes||[]).map(r=>`<option>${r}</option>`).join('')||'<option value="">(sin remotes)</option>';
  $('rcwarn').textContent=rm.rclone?('Remotes rclone disponibles: '+(rm.remotes||[]).join(', ')||'ninguno'):'⚠ rclone no disponible en el contenedor';
}

function renderDests(){
  const ds=CFG.destinations||[];
  $('dests').innerHTML=ds.length?ds.map((d,i)=>`<div class="dest">
     <input type="checkbox" ${d.enabled!==false?'checked':''} onchange="CFG.destinations[${i}].enabled=this.checked">
     <b>${d.type==='local'?'📁 local':'☁ '+ (d.remote||'')}</b>
     <span class="muted">${d.type==='local'?(d.path||'(raíz)'):(d.remote+':'+(d.path||''))}</span>
     <button class="sec" style="margin-left:auto;padding:4px 9px" onclick="delDest(${i})">quitar</button>
   </div>`).join(''):'<span class="muted">Sin destinos. Añade al menos uno abajo.</span>';
}
function addDest(){
  const t=$('dtype').value, path=$('dpath').value.trim();
  const d={id:t+'-'+((CFG.destinations||[]).length+1),type:t,path:path,enabled:true};
  if(t==='rclone'){d.remote=$('dremote').value;}
  CFG.destinations=CFG.destinations||[]; CFG.destinations.push(d); $('dpath').value=''; renderDests();
}
function delDest(i){CFG.destinations.splice(i,1);renderDests();}

function renderSchedule(){
  const s=CFG.schedule||{}; $('schEnabled').checked=!!s.enabled;
  $('schTime').value=s.time||'03:30'; $('schRet').value=s.retention_days||7;
}

function collect(){
  const get=k=>document.querySelector(`input[data-k="${k}"]`);
  const out={include_omv_config:get('omv')?.checked, include_manifest:get('manifest')?.checked,
     include_system_identities:get('sysid')?.checked,
     volumes:[],databases:[],compose_roots:[],compose_stacks:[],destinations:CFG.destinations||[],
     schedule:{enabled:$('schEnabled').checked,time:$('schTime').value,retention_days:+$('schRet').value}};
  document.querySelectorAll('input[data-k]').forEach(el=>{
     if(!el.checked)return; const k=el.dataset.k;
     if(k.startsWith('vol:'))out.volumes.push(k.slice(4));
     else if(k.startsWith('db:'))out.databases.push(k.slice(3));
     else if(k.startsWith('stack:'))out.compose_stacks.push(k.slice(6));
  });
  return out;
}
async function saveAll(){
  CFG=await jpost('/api/settings',collect()); $('saved').textContent='guardado ✓';
  setTimeout(()=>$('saved').textContent='',2500); toast('Configuración guardada');
}

async function runBackup(){
  const r=await jpost('/api/backup/run',{});
  if(r.started){toast('Respaldo iniciado…');pollRun();}else toast(r.error||'no se pudo');
}
function pollRun(){
  $('runBtn').disabled=true;$('runBtn').textContent='Respaldando…';
  const iv=setInterval(async()=>{const s=await jget('/api/status');loadLogs();
    if(!s.running){clearInterval(iv);$('runBtn').disabled=false;$('runBtn').textContent='Respaldar ahora';
      loadHistory();toast('Respaldo terminado');}},2500);
}
async function loadStatus(){const s=await jget('/api/status');
  $('status').textContent=s.running?'respaldando…':(s.next_run?('próximo: '+s.next_run):'programación apagada');
  $('runBtn').disabled=!!s.running;}
async function loadHistory(){const h=await jget('/api/history');
  $('hist').innerHTML=h.length?h.map(e=>{
    const dd=(e.destinos||[]).map(x=>`${x.destino}:${x.ok?'<span class=ok>ok</span>':'<span class=err>err</span>'}`).join(' ');
    return `<tr><td>${e.timestamp||e.fecha}</td><td>${e.trigger||''}</td><td>${e.size_mb?e.size_mb+' MB':'—'}</td>
      <td>${dd||'<span class=muted>sin destino</span>'}</td>
      <td>${e.ok?'<span class=ok>OK</span>':'<span class=err>con errores</span>'}</td></tr>`;
  }).join(''):'<tr><td colspan=5 class=muted>Aún no hay respaldos</td></tr>';}
async function loadLogs(){$('logs').textContent=await (await fetch('/api/logs')).text()||'(vacío)';$('logs').scrollTop=$('logs').scrollHeight;}

(async()=>{const h=await jget('/health');$('ver').textContent='v'+h.version;await scanNow();})();
</script>
</body></html>
"""
