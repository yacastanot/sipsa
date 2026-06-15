"""
SIPSA IPC — Pipeline Runner
============================
Interfaz web para ejecutar el proceso mensual de forma interactiva.

Pasos del usuario:
  1. Cargar el archivo Excel de entrada (BASE SIPSA_A mensual).
  2. Configurar los parámetros del período (mes, año, fecha).
  3. Lanzar el pipeline Kedro.
  4. Descargar los archivos de resultado (T38 + T39).

Uso:
    uvicorn sipsa_ipc.api.runner:app --reload --port 8080
    Abrir http://localhost:8080 en el navegador.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import yaml
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

# ─── Rutas del proyecto ────────────────────────────────────────────────────────
_THIS       = Path(__file__).resolve()
PROJECT_DIR = _THIS.parents[3]          # .../sipsa-ipc/
RAW_DIR     = PROJECT_DIR / "data" / "01_raw"
REPT_DIR    = PROJECT_DIR / "data" / "08_reporting"
PARAMS_FILE = PROJECT_DIR / "conf" / "base" / "parameters.yml"

# ─── Estado de trabajos en memoria ────────────────────────────────────────────
_jobs: dict[str, dict] = {}

# ─── Meses ────────────────────────────────────────────────────────────────────
_MESES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]
_MESES_OPTS = "\n".join(f'<option value="{m}">{m}</option>' for m in _MESES)

# ─── Etiquetas amigables de nodos ─────────────────────────────────────────────
_NODE_LABELS_JS = """{
  leer_base:                      'Leyendo archivo de entrada...',
  preparar_articulos_ipc:         'Validando artículos IPC y períodos...',
  limpiar_base:                   'Limpiando y clasificando filas...',
  filtrar_articulos_canasta:      'Filtrando artículos de la canasta...',
  generar_no_mapeados:            'Identificando variedades no mapeadas...',
  calcular_cobertura:             'Calculando cobertura IPC...',
  calcular_td_abast:              'Calculando tabla de abastecimiento...',
  calcular_td_abast_otros:        'Calculando importaciones...',
  calcular_td_destino:            'Calculando tabla de destinos...',
  calcular_td_total:              'Calculando totales de abastecimiento...',
  calcular_variaciones:           'Calculando variaciones mensuales y anuales...',
  formatear_td_abast:             'Formateando abastecimiento...',
  formatear_td_abast_otros:       'Formateando importaciones...',
  formatear_td_destino:           'Formateando destinos...',
  exportar_alimentos_priorizados: 'Generando Alimentos_priorizados.xlsx...',
  exportar_sipsa_ipc:             'Generando SIPSA_IPC.xlsx...',
  guardar_historico:              'Guardando histórico mensual...',
}"""

# ─── Plantilla HTML ────────────────────────────────────────────────────────────
_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SIPSA IPC — Proceso Mensual</title>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --blue:#1F497D;--blue2:#2e6db4;--green:#2e7d32;
  --red:#c62828;--amber:#e65100;
  --border:#ddd;--shadow:0 2px 10px rgba(0,0,0,.1);
}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
     background:#f0f2f5;color:#333;line-height:1.5}
a{color:inherit;text-decoration:none}

/* Header */
header{background:var(--blue);color:#fff;padding:18px 36px}
header h1{font-size:1.45rem;font-weight:700}
header p{font-size:.82rem;opacity:.72;margin-top:3px}

/* Layout */
.main{max-width:900px;margin:26px auto;padding:0 18px;
      display:flex;flex-direction:column;gap:18px}

/* Card */
.card{background:#fff;border-radius:9px;box-shadow:var(--shadow);padding:26px 30px}
.card.locked{opacity:.42;pointer-events:none}
.card-hdr{display:flex;align-items:center;gap:12px;margin-bottom:20px}
.card-hdr h2{font-size:1.02rem;font-weight:600;color:var(--blue)}

/* Step badge */
.badge{width:30px;height:30px;border-radius:50%;background:var(--blue);
       color:#fff;font-weight:700;font-size:.82rem;
       display:flex;align-items:center;justify-content:center;flex-shrink:0}
.badge.ok{background:var(--green)}

/* Drop zone */
.dz{border:2px dashed #bbb;border-radius:7px;padding:38px 18px;
    text-align:center;cursor:pointer;transition:.2s;color:#666}
.dz:hover,.dz.over{border-color:var(--blue);background:#f0f5ff;color:var(--blue)}
.dz .ico{font-size:2.5rem}
.dz p{margin-top:8px;font-size:.95rem}
.dz small{font-size:.8rem;color:#999;display:block;margin-top:5px}

.pill{display:none;align-items:center;gap:10px;padding:10px 14px;
      background:#e8f5e9;border:1px solid #a5d6a7;border-radius:6px;margin-top:12px}
.pill.show{display:flex}
.pill .fn{font-weight:600;flex:1;font-size:.88rem;word-break:break-all}
.pill .fs{font-size:.78rem;color:#666;white-space:nowrap}
.pill button{background:none;border:none;cursor:pointer;color:#999;font-size:.95rem;padding:2px 6px}
.pill button:hover{color:var(--red)}

/* Form */
.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.full{grid-column:1/-1}
.fld{display:flex;flex-direction:column;gap:5px}
.fld label{font-size:.75rem;font-weight:700;color:#666;text-transform:uppercase;letter-spacing:.4px}
.fld select,.fld input{padding:9px 11px;border:1px solid var(--border);
   border-radius:5px;font-size:.94rem;transition:.2s;width:100%}
.fld select:focus,.fld input:focus{outline:none;border-color:var(--blue);
   box-shadow:0 0 0 3px rgba(31,73,125,.12)}

/* Run button */
.run-btn{width:100%;padding:14px;background:var(--blue);color:#fff;
   border:none;border-radius:6px;font-size:1.02rem;font-weight:700;
   cursor:pointer;letter-spacing:.4px;transition:.2s}
.run-btn:hover:not(:disabled){background:var(--blue2)}
.run-btn:disabled{opacity:.4;cursor:not-allowed}

/* Progress */
.prog{display:none;margin-top:20px}
.prog.show{display:block}
.prog-hdr{display:flex;align-items:center;justify-content:space-between;margin-bottom:6px}
.spill{display:inline-flex;align-items:center;gap:6px;padding:3px 12px;
       border-radius:20px;font-size:.79rem;font-weight:600}
.s-run{background:#fff3e0;color:var(--amber)}
.s-ok{background:#e8f5e9;color:var(--green)}
.s-err{background:#ffebee;color:var(--red)}
.prog-pct{font-size:.8rem;color:#777}
.bar-track{height:7px;background:#e0e0e0;border-radius:4px;overflow:hidden;margin:8px 0}
.bar-fill{height:100%;background:var(--blue);border-radius:4px;width:0;transition:width .4s}
.cur-node{font-size:.82rem;color:#555;min-height:18px;margin-bottom:10px}

/* Log */
.log-wrap{position:relative}
.log-toggle{position:absolute;top:8px;right:10px;background:rgba(255,255,255,.1);
   border:1px solid rgba(255,255,255,.25);color:#aaa;font-size:.7rem;
   padding:2px 8px;border-radius:3px;cursor:pointer}
.log-box{background:#1e1e1e;color:#ccc;font-family:Consolas,'Courier New',monospace;
   font-size:.74rem;padding:10px 14px;border-radius:6px;
   max-height:300px;overflow-y:auto;line-height:1.45}
.log-box .le{color:#f48771}
.log-box .lw{color:#dcdcaa}
.log-box .lo{color:#4ec9b0}

/* Downloads */
.dl-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.dl-card{border:1px solid var(--border);border-radius:7px;padding:16px;
   display:flex;flex-direction:column;gap:7px}
.dl-card .dn{font-weight:600;font-size:.87rem;word-break:break-all}
.dl-card .dd{font-size:.79rem;color:#666}
.dl-card .ds{font-size:.76rem;color:#999}
.dl-btn{display:block;padding:9px 14px;background:#e8f5e9;color:var(--green);
   border:1px solid #a5d6a7;border-radius:5px;font-weight:600;font-size:.88rem;
   text-align:center;transition:.2s;margin-top:4px;cursor:pointer}
.dl-btn:hover{background:#c8e6c9}

/* Spinner */
.spin{display:inline-block;width:12px;height:12px;border:2px solid currentColor;
   border-top-color:transparent;border-radius:50%;
   animation:rot .7s linear infinite;vertical-align:middle}
@keyframes rot{to{transform:rotate(360deg)}}

@media(max-width:560px){
  .grid,.dl-grid{grid-template-columns:1fr}
  .main{padding:0 10px}
}
</style>
</head>
<body>

<header>
  <h1>SIPSA IPC — Proceso Mensual</h1>
  <p>Departamento Administrativo Nacional de Estadística &nbsp;·&nbsp;
     Sistema de Información de Precios y Abastecimiento de Alimentos</p>
</header>

<div class="main">

  <!-- ─── Paso 1: Archivo ─────────────────────────────────────────────────── -->
  <div class="card" id="c1">
    <div class="card-hdr">
      <div class="badge" id="b1">1</div>
      <h2>Cargar archivo de entrada</h2>
    </div>

    <div class="dz" id="dz" onclick="document.getElementById('fi').click()">
      <div class="ico">📂</div>
      <p>Haga clic aquí o arrastre el archivo</p>
      <small>Formato Excel (.xlsx) con las hojas BASE SIPSA_A, Artículos_IPC y Alimentos IPC Vs SIPSA_A</small>
    </div>
    <input type="file" id="fi" accept=".xlsx" style="display:none" onchange="onFilePick()">

    <div class="pill" id="pill">
      <span>📄</span>
      <span class="fn" id="pn"></span>
      <span class="fs" id="ps"></span>
      <button onclick="clearFile()" title="Cambiar archivo">✕</button>
    </div>
  </div>

  <!-- ─── Paso 2: Parámetros ──────────────────────────────────────────────── -->
  <div class="card locked" id="c2">
    <div class="card-hdr">
      <div class="badge" id="b2">2</div>
      <h2>Parámetros del período</h2>
    </div>

    <div class="grid">
      <div class="fld">
        <label>Mes actual</label>
        <select id="mes-act" onchange="autoFill()">
          <option value="">Seleccione...</option>
          __MESES__
        </select>
      </div>
      <div class="fld">
        <label>Año actual</label>
        <input type="number" id="anio-act" value="2026" min="2020" max="2040" onchange="autoFill()">
      </div>
      <div class="fld">
        <label>Mes anterior (t-1)</label>
        <select id="mes-ant">
          <option value="">—</option>
          __MESES__
        </select>
      </div>
      <div class="fld">
        <label>Año para comparativo anual (t-12)</label>
        <input type="number" id="anio-ant" value="2025" min="2019" max="2039">
      </div>
      <div class="fld full">
        <label>Fecha del proceso (YYYYMMDD)</label>
        <input type="text" id="fecha" placeholder="ej. 20260615" maxlength="8" oninput="chkReady()">
      </div>
    </div>
  </div>

  <!-- ─── Paso 3: Ejecutar ─────────────────────────────────────────────────── -->
  <div class="card locked" id="c3">
    <div class="card-hdr">
      <div class="badge" id="b3">3</div>
      <h2>Ejecutar proceso</h2>
    </div>

    <button class="run-btn" id="run-btn" disabled onclick="runPipeline()">
      ▶&nbsp; Ejecutar proceso completo
    </button>

    <div class="prog" id="prog">
      <div class="prog-hdr" style="margin-top:18px">
        <span class="spill s-run" id="spill"><span class="spin"></span>&nbsp;Iniciando...</span>
        <span class="prog-pct" id="ppct"></span>
      </div>
      <div class="bar-track"><div class="bar-fill" id="pbar"></div></div>
      <div class="cur-node" id="cnode"></div>
      <div class="log-wrap">
        <button class="log-toggle" onclick="toggleLog()">mostrar / ocultar log</button>
        <div class="log-box" id="lbox"></div>
      </div>
    </div>
  </div>

  <!-- ─── Paso 4: Resultados ──────────────────────────────────────────────── -->
  <div class="card locked" id="c4">
    <div class="card-hdr">
      <div class="badge" id="b4">4</div>
      <h2>Descargar resultados</h2>
    </div>
    <div class="dl-grid" id="dlg">
      <p style="color:#999;font-size:.88rem;grid-column:1/-1">
        Los archivos de resultado aparecerán aquí al completar el proceso.
      </p>
    </div>
  </div>

</div><!-- .main -->

<script>
const MESES = ['Enero','Febrero','Marzo','Abril','Mayo','Junio',
               'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'];
const NODE_LABELS = __NODE_LABELS__;

let uploaded = null, jobId = null, timer = null, logN = 0, logVis = true;

// ── Drop zone ─────────────────────────────────────────────────────────────────
const dz = document.getElementById('dz');
dz.addEventListener('dragover', e => { e.preventDefault(); dz.classList.add('over'); });
dz.addEventListener('dragleave', () => dz.classList.remove('over'));
dz.addEventListener('drop', e => {
  e.preventDefault(); dz.classList.remove('over');
  if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]);
});
function onFilePick() {
  const f = document.getElementById('fi').files[0];
  if (f) handleFile(f);
}

async function handleFile(file) {
  if (!file.name.endsWith('.xlsx')) { alert('Solo se aceptan archivos .xlsx'); return; }
  dz.style.display = 'none';
  document.getElementById('pn').textContent = file.name;
  document.getElementById('ps').textContent = fmtB(file.size);
  document.getElementById('pill').classList.add('show');

  const fd = new FormData();
  fd.append('file', file);
  try {
    const r = await fetch('/upload', { method: 'POST', body: fd });
    if (!r.ok) throw new Error(await r.text());
    const d = await r.json();
    uploaded = d.filename;
    unlock('c2'); unlock('c3');
    setNum('b1', true);
    autoFill();
  } catch(e) { alert('Error al cargar el archivo:\n' + e.message); clearFile(); }
}

function clearFile() {
  uploaded = null;
  document.getElementById('fi').value = '';
  document.getElementById('pill').classList.remove('show');
  dz.style.display = '';
  lock('c2'); lock('c3'); lock('c4');
  setNum('b1', false); setNum('b2', false); setNum('b3', false); setNum('b4', false);
  document.getElementById('run-btn').disabled = true;
}

// ── Params ────────────────────────────────────────────────────────────────────
function autoFill() {
  const mi   = MESES.indexOf(document.getElementById('mes-act').value);
  const anio = parseInt(document.getElementById('anio-act').value) || new Date().getFullYear();
  if (mi < 0) return;

  document.getElementById('mes-ant').value  = MESES[(mi + 11) % 12];
  document.getElementById('anio-ant').value = anio - 1;

  const fp = document.getElementById('fecha');
  if (!fp.value) {
    const h = new Date();
    fp.value = h.getFullYear() + pad2(h.getMonth()+1) + pad2(h.getDate());
  }
  chkReady();
}

function chkReady() {
  const ok = uploaded
    && document.getElementById('mes-act').value
    && document.getElementById('mes-ant').value
    && /^\\d{8}$/.test(document.getElementById('fecha').value);
  document.getElementById('run-btn').disabled = !ok;
}

document.getElementById('mes-act').addEventListener('change', chkReady);
document.getElementById('fecha').addEventListener('input', chkReady);

// ── Run ───────────────────────────────────────────────────────────────────────
async function runPipeline() {
  const body = new URLSearchParams({
    archivo_entrada:     uploaded,
    mes_actual_nombre:   document.getElementById('mes-act').value,
    mes_anterior_nombre: document.getElementById('mes-ant').value,
    anio_actual:         document.getElementById('anio-act').value,
    anio_anterior:       document.getElementById('anio-ant').value,
    fecha_proceso:       document.getElementById('fecha').value,
  });

  document.getElementById('run-btn').disabled = true;
  document.getElementById('prog').classList.add('show');
  document.getElementById('lbox').innerHTML = '';
  logN = 0;
  setSpill('run', '<span class="spin"></span>&nbsp;Iniciando proceso...');

  try {
    const r = await fetch('/run', {
      method: 'POST', body,
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    });
    if (!r.ok) { const d = await r.json(); throw new Error(d.detail || 'Error'); }
    const d = await r.json();
    jobId = d.job_id;
    timer = setInterval(poll, 1500);
  } catch(e) {
    setSpill('err', '⚠ ' + e.message);
    document.getElementById('run-btn').disabled = false;
  }
}

async function poll() {
  if (!jobId) return;
  try {
    const r = await fetch('/status/' + jobId);
    if (!r.ok) return;
    const d = await r.json();

    // Agregar nuevas líneas al log
    const box = document.getElementById('lbox');
    d.log.slice(logN).forEach(line => {
      if (!line.trim()) return;
      const el = document.createElement('div');
      el.textContent = line;
      const lo = line.toLowerCase();
      if (lo.includes('error') || lo.includes('failed') || lo.includes('exception'))
        el.className = 'le';
      else if (lo.includes('warning') || lo.includes('warn'))
        el.className = 'lw';
      else if (lo.includes('completed') || lo.includes('ok') || lo.includes('exitosamente'))
        el.className = 'lo';
      box.appendChild(el);
    });
    logN = d.log.length;
    box.scrollTop = box.scrollHeight;

    // Progreso
    const full = d.log.join('\\n');
    const pm = [...full.matchAll(/Completed (\\d+) out of (\\d+) tasks/g)];
    if (pm.length) {
      const [, done, total] = pm[pm.length-1];
      const pct = Math.round(+done / +total * 100);
      document.getElementById('pbar').style.width = pct + '%';
      document.getElementById('ppct').textContent = done + ' / ' + total + ' tareas (' + pct + '%)';
    }

    // Nodo actual
    const nm = [...full.matchAll(/Running node: ([\\w_]+):/g)];
    if (nm.length) {
      const node = nm[nm.length-1][1];
      document.getElementById('cnode').textContent = NODE_LABELS[node] || node;
    }

    if (d.status === 'done') {
      clearInterval(timer);
      document.getElementById('pbar').style.width = '100%';
      document.getElementById('ppct').textContent = 'Completado ✓';
      document.getElementById('cnode').textContent = '';
      setSpill('ok', '✓&nbsp; Proceso completado exitosamente');
      setNum('b3', true);
      renderDownloads(d.output_files);
      unlock('c4'); setNum('b4', true);

    } else if (d.status === 'error') {
      clearInterval(timer);
      setSpill('err', '⚠&nbsp; Error en la ejecución — revise el log técnico');
      document.getElementById('run-btn').disabled = false;

    } else {
      const cur = document.getElementById('cnode').textContent;
      setSpill('run', '<span class="spin"></span>&nbsp;' + (cur || 'Procesando...'));
    }
  } catch(e) { /* ignorar errores de red en polling */ }
}

// ── Downloads ─────────────────────────────────────────────────────────────────
function renderDownloads(files) {
  const g = document.getElementById('dlg');
  if (!files || !files.length) {
    g.innerHTML = '<p style="color:var(--red)">No se encontraron archivos de resultado.</p>';
    return;
  }
  g.innerHTML = files.map(f => `
    <div class="dl-card">
      <div class="dn">📊 ${f.name}</div>
      <div class="dd">${f.desc}</div>
      <div class="ds">${fmtB(f.size)}</div>
      <a class="dl-btn" href="/download/${encodeURIComponent(f.name)}"
         download="${f.name}">⬇&nbsp; Descargar</a>
    </div>
  `).join('');
}

// ── Utils ─────────────────────────────────────────────────────────────────────
function unlock(id){ document.getElementById(id).classList.remove('locked'); }
function lock(id)  { document.getElementById(id).classList.add('locked'); }

function setNum(id, done) {
  const el = document.getElementById(id);
  if (done) { el.classList.add('ok'); el.textContent = '✓'; }
  else      { el.classList.remove('ok'); el.textContent = id.replace('b',''); }
}

function setSpill(type, html) {
  const el = document.getElementById('spill');
  el.className = 'spill s-' + (type === 'run' ? 'run' : type === 'ok' ? 'ok' : 'err');
  el.innerHTML = html;
}

function fmtB(b) {
  if (!b) return '';
  if (b < 1024) return b + ' B';
  if (b < 1048576) return (b/1024).toFixed(1) + ' KB';
  return (b/1048576).toFixed(2) + ' MB';
}

function pad2(n) { return String(n).padStart(2,'0'); }

function toggleLog() {
  logVis = !logVis;
  document.getElementById('lbox').style.display = logVis ? '' : 'none';
}
</script>
</body>
</html>"""

# Inyectar opciones de meses y etiquetas de nodos en la plantilla
_HTML = (
    _HTML_TEMPLATE
    .replace("__MESES__", _MESES_OPTS)
    .replace("__NODE_LABELS__", _NODE_LABELS_JS)
)

# ─── Aplicación FastAPI ────────────────────────────────────────────────────────
app = FastAPI(title="SIPSA IPC Runner", version="1.0.0")


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    """Interfaz web principal."""
    return _HTML


@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    """Recibe el archivo Excel de entrada y lo guarda en data/01_raw/."""
    if not file.filename.endswith(".xlsx"):
        raise HTTPException(400, "Solo se aceptan archivos .xlsx")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    dest = RAW_DIR / file.filename
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"filename": file.filename, "size": dest.stat().st_size}


@app.post("/run")
async def run(
    background_tasks: BackgroundTasks,
    archivo_entrada:     str = Form(...),
    mes_actual_nombre:   str = Form(...),
    mes_anterior_nombre: str = Form(...),
    anio_actual:         int = Form(...),
    anio_anterior:       int = Form(...),
    fecha_proceso:       str = Form(...),
):
    """Actualiza parameters.yml y lanza kedro run en segundo plano."""
    if any(j["status"] == "running" for j in _jobs.values()):
        raise HTTPException(409, "Ya hay un proceso en ejecución. Espere a que termine.")

    job_id = uuid.uuid4().hex[:8]
    _jobs[job_id] = {"status": "running", "log": [], "output_files": []}

    _update_params({
        "archivo_entrada":     f"data/01_raw/{archivo_entrada}",
        "mes_actual_nombre":   mes_actual_nombre,
        "mes_anterior_nombre": mes_anterior_nombre,
        "anio_actual":         anio_actual,
        "anio_anterior":       anio_anterior,
        "fecha_proceso":       fecha_proceso,
    })

    background_tasks.add_task(
        _run_kedro, job_id, fecha_proceso, mes_actual_nombre, anio_actual
    )
    return {"job_id": job_id}


@app.get("/status/{job_id}")
async def status(job_id: str):
    """Devuelve el estado actual del trabajo: status, log y output_files."""
    if job_id not in _jobs:
        raise HTTPException(404, "Job no encontrado")
    return JSONResponse(_jobs[job_id])


@app.get("/download/{filename}")
async def download(filename: str):
    """Descarga un archivo de resultado de data/08_reporting/."""
    # Evitar path traversal
    safe_name = Path(filename).name
    path = REPT_DIR / safe_name
    if not path.exists():
        raise HTTPException(404, f"Archivo '{safe_name}' no encontrado en reporting")
    return FileResponse(
        path=str(path),
        filename=safe_name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ─── Funciones internas ───────────────────────────────────────────────────────

def _update_params(params: dict) -> None:
    """Actualiza las claves indicadas en conf/base/parameters.yml."""
    with PARAMS_FILE.open("r", encoding="utf-8") as f:
        current = yaml.safe_load(f) or {}
    current.update(params)
    with PARAMS_FILE.open("w", encoding="utf-8") as f:
        yaml.dump(current, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def _run_kedro(
    job_id: str,
    fecha_proceso: str,
    mes_actual: str,
    anio_actual: int,
) -> None:
    """Ejecuta kedro run en un hilo de BackgroundTasks y captura la salida."""
    job = _jobs[job_id]
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}

    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "kedro", "run"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(PROJECT_DIR),
            env=env,
        )
        for raw in iter(proc.stdout.readline, b""):
            line = raw.decode("utf-8", errors="replace").rstrip()
            if line.strip():
                job["log"].append(line)
        proc.wait()

        if proc.returncode == 0:
            job["status"] = "done"
            job["output_files"] = _find_outputs(fecha_proceso, mes_actual, anio_actual)
        else:
            job["status"] = "error"

    except Exception as exc:
        job["status"] = "error"
        job["log"].append(f"ERROR INTERNO: {exc}")


def _find_outputs(fecha_proceso: str, mes_actual: str, anio_actual: int) -> list[dict]:
    """Busca los archivos de resultado y devuelve nombre, descripción y tamaño."""
    mes_corto  = mes_actual[:3].lower()
    anio_corto = str(anio_actual)[-2:]

    candidates = [
        (
            f"SIPSA_IPC_{fecha_proceso}.xlsx",
            "Tablas TD_Total, TD_Abast, TD_Destino, TD_Abast_Otros y TREF_Productos",
        ),
        (
            f"Alimentos_priorizados_{mes_corto}{anio_corto}_SIPSA_{fecha_proceso}.xlsx",
            "Hoja Artículos_IPC — zonas abastecedoras, destinos y variaciones",
        ),
    ]
    result = []
    for name, desc in candidates:
        p = REPT_DIR / name
        if p.exists():
            result.append({"name": name, "desc": desc, "size": p.stat().st_size})
    return result
