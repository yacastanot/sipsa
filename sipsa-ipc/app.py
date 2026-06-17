"""FastAPI web app para ejecutar el pipeline SIPSA IPC.

Flujo mensual:
  - Carga del archivo Excel de alimentos priorizados
  - Configuración del período (mes_actual, mes_anterior, anio)
  - Ejecución de pipelines individuales o el completo
  - Streaming de logs vía Server-Sent Events
  - Descarga de los XLSX de salida

Credenciales: variables de entorno SIPSA_IPC_USER / SIPSA_IPC_PASS
  (por defecto: sipsa / cambiar_esta_clave)
"""
from __future__ import annotations

import asyncio
import os
import queue
import secrets
import subprocess
import sys
import threading
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from ruamel.yaml import YAML as _YAML

# ── Rutas del proyecto ────────────────────────────────────────────────────────

PROJECT_ROOT  = Path(__file__).parent
RAW_DIR       = PROJECT_ROOT / "data" / "01_raw"
REPORTING_DIR = PROJECT_ROOT / "data" / "08_reporting"
PARAMS_YML    = PROJECT_ROOT / "conf" / "base" / "parameters.yml"

# ── Catálogos de dominio ──────────────────────────────────────────────────────

MESES_NOMBRE: dict[int, str] = {
    1: "Enero",      2: "Febrero",   3: "Marzo",      4: "Abril",
    5: "Mayo",       6: "Junio",     7: "Julio",       8: "Agosto",
    9: "Septiembre", 10: "Octubre",  11: "Noviembre",  12: "Diciembre",
}

PIPELINES: list[tuple[str, str]] = [
    ("__default__",  "Completo — todos los pasos"),
    ("silver",       "Silver — Ingesta + Limpieza"),
    ("preparation",  "F0 · Preparación"),
    ("ingestion",    "F1 · Ingesta Excel"),
    ("cleaning",     "F2 · Limpieza y enriquecimiento"),
    ("validation",   "F3 · Validación"),
    ("aggregation",  "F4 · Agregación IPC"),
    ("comparison",   "F5 · Comparación interanual"),
    ("formatting",   "F6 · Formateo"),
    ("reporting",    "F7 · Reportes Excel"),
]

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="SIPSA IPC Pipeline", docs_url=None, redoc_url=None)
templates = Jinja2Templates(directory=str(PROJECT_ROOT / "templates"))
security = HTTPBasic()

_pipeline_running = False


# ── Autenticación ─────────────────────────────────────────────────────────────

def _check_auth(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    expected_user = os.environ.get("SIPSA_IPC_USER", "sipsa")
    expected_pass = os.environ.get("SIPSA_IPC_PASS", "cambiar_esta_clave")
    user_ok = secrets.compare_digest(credentials.username.encode(), expected_user.encode())
    pass_ok = secrets.compare_digest(credentials.password.encode(), expected_pass.encode())
    if not (user_ok and pass_ok):
        raise HTTPException(
            status_code=401,
            detail="Credenciales incorrectas",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


# ── Helpers YAML ──────────────────────────────────────────────────────────────

def _read_params() -> dict:
    yml = _YAML()
    with PARAMS_YML.open("r", encoding="utf-8") as f:
        data = yml.load(f)
    return {k: (str(v) if v is not None else "") for k, v in data.items()}


def _write_params(**updates) -> None:
    yml = _YAML()
    yml.preserve_quotes = True
    with PARAMS_YML.open("r", encoding="utf-8") as f:
        data = yml.load(f)
    for key, val in updates.items():
        if key in data:
            data[key] = val
    with PARAMS_YML.open("w", encoding="utf-8") as f:
        yml.dump(data, f)


# ── Modelos ───────────────────────────────────────────────────────────────────

class ConfigRequest(BaseModel):
    mes_num: int
    anio: int


# ── Rutas ─────────────────────────────────────────────────────────────────────

@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    return Response(status_code=204)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, _: str = Depends(_check_auth)) -> HTMLResponse:
    config = _read_params()
    mes_actual = config.get("mes_actual_nombre", "Enero")
    mes_num = next((k for k, v in MESES_NOMBRE.items() if v == mes_actual), 1)
    anio = int(config.get("anio_actual", 2026))
    return templates.TemplateResponse(request, "index.html", {
        "config":    config,
        "mes_num":   mes_num,
        "anio":      anio,
        "pipelines": PIPELINES,
    })


@app.get("/config")
async def get_config(_: str = Depends(_check_auth)) -> dict:
    return _read_params()


@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    _: str = Depends(_check_auth),
) -> dict:
    if not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(400, "Solo se aceptan archivos Excel (.xlsx, .xls)")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    dest = RAW_DIR / file.filename
    contents = await file.read()
    dest.write_bytes(contents)
    _write_params(archivo_entrada=f"data/01_raw/{file.filename}")
    return {"filename": file.filename, "size_kb": round(len(contents) / 1024, 1)}


@app.post("/configure")
async def configure(
    body: ConfigRequest,
    _: str = Depends(_check_auth),
) -> dict:
    mes_num = body.mes_num
    anio    = body.anio

    if not (1 <= mes_num <= 12):
        raise HTTPException(400, "mes_num debe estar entre 1 y 12")
    if not (2020 <= anio <= 2040):
        raise HTTPException(400, "Año fuera del rango permitido (2020–2040)")

    mes_ant_num = 12 if mes_num == 1 else mes_num - 1
    anio_ant    = anio - 1 if mes_num == 1 else anio

    _write_params(
        mes_actual_nombre=MESES_NOMBRE[mes_num],
        mes_anterior_nombre=MESES_NOMBRE[mes_ant_num],
        anio_actual=anio,
        anio_anterior=anio_ant,
    )

    return {
        "ok":                   True,
        "mes_actual_nombre":    MESES_NOMBRE[mes_num],
        "mes_anterior_nombre":  MESES_NOMBRE[mes_ant_num],
        "anio_actual":          anio,
        "anio_anterior":        anio_ant,
    }


@app.get("/status")
async def status(_: str = Depends(_check_auth)) -> dict:
    return {"running": _pipeline_running}


@app.get("/outputs")
async def list_outputs(_: str = Depends(_check_auth)) -> dict:
    if not REPORTING_DIR.exists():
        return {"files": []}
    files = sorted(
        REPORTING_DIR.glob("*.xlsx"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    return {"files": [f.name for f in files]}


@app.delete("/outputs")
async def clear_outputs(_: str = Depends(_check_auth)) -> dict:
    if not REPORTING_DIR.exists():
        return {"deleted": 0}
    deleted = 0
    for f in REPORTING_DIR.glob("*.xlsx"):
        f.unlink()
        deleted += 1
    return {"deleted": deleted}


@app.get("/download/{filename}")
async def download(filename: str, _: str = Depends(_check_auth)) -> FileResponse:
    path = (REPORTING_DIR / filename).resolve()
    if not str(path).startswith(str(REPORTING_DIR.resolve())):
        raise HTTPException(403, "Acceso denegado")
    if not path.exists():
        raise HTTPException(404, "Archivo no encontrado")
    return FileResponse(
        str(path),
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.post("/run")
async def run_pipeline(
    pipeline_name: str = Form("__default__"),
    _: str = Depends(_check_auth),
) -> StreamingResponse:
    global _pipeline_running
    if _pipeline_running:
        raise HTTPException(409, "El pipeline ya está en ejecución")

    cmd = [sys.executable, "-m", "kedro", "run"]
    if pipeline_name != "__default__":
        cmd += ["--pipeline", pipeline_name]

    line_queue: queue.Queue = queue.Queue()

    def _run_kedro() -> None:
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(PROJECT_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            for line in proc.stdout:
                line_queue.put(line.rstrip())
            proc.wait()
            line_queue.put(("__DONE__", proc.returncode))
        except Exception as exc:
            line_queue.put(("__DONE__", str(exc)))

    async def generate():
        global _pipeline_running
        _pipeline_running = True
        thread = threading.Thread(target=_run_kedro, daemon=True)
        thread.start()
        loop = asyncio.get_event_loop()
        try:
            while True:
                item = await loop.run_in_executor(None, line_queue.get)
                if isinstance(item, tuple) and item[0] == "__DONE__":
                    rc = item[1]
                    yield "data: __SUCCESS__\n\n" if rc == 0 else f"data: __ERROR__{rc}\n\n"
                    break
                yield f"data: {item}\n\n"
        except Exception as exc:
            yield f"data: __ERROR__{exc}\n\n"
        finally:
            _pipeline_running = False

    return StreamingResponse(generate(), media_type="text/event-stream")
