"""FastAPI web app para ejecutar el pipeline SIPSA."""
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

PROJECT_ROOT = Path(__file__).parent
RAW_DIR = PROJECT_ROOT / "data" / "01_raw"
REPORTING_DIR = PROJECT_ROOT / "data" / "08_reporting"

app = FastAPI(title="SIPSA Pipeline", docs_url=None, redoc_url=None)
templates = Jinja2Templates(directory=str(PROJECT_ROOT / "templates"))
security = HTTPBasic()

_pipeline_running = False


# ── Autenticación ─────────────────────────────────────────────────────────────

def _check_auth(credentials: HTTPBasicCredentials = Depends(security)):
    """Valida usuario y contraseña contra las variables de entorno SIPSA_USER / SIPSA_PASS."""
    expected_user = os.environ.get("SIPSA_USER", "sipsa")
    expected_pass = os.environ.get("SIPSA_PASS", "cambiar_esta_clave")

    user_ok = secrets.compare_digest(
        credentials.username.encode("utf-8"),
        expected_user.encode("utf-8"),
    )
    pass_ok = secrets.compare_digest(
        credentials.password.encode("utf-8"),
        expected_pass.encode("utf-8"),
    )
    if not (user_ok and pass_ok):
        raise HTTPException(
            status_code=401,
            detail="Credenciales incorrectas",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


# ── Rutas ─────────────────────────────────────────────────────────────────────

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, _: str = Depends(_check_auth)):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    _: str = Depends(_check_auth),
):
    if not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(400, "Solo se aceptan archivos Excel (.xlsx, .xls)")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    dest = RAW_DIR / file.filename
    contents = await file.read()
    dest.write_bytes(contents)
    return {"filename": file.filename}


@app.get("/status")
async def status(_: str = Depends(_check_auth)):
    return {"running": _pipeline_running}


@app.get("/outputs")
async def list_outputs(_: str = Depends(_check_auth)):
    if not REPORTING_DIR.exists():
        return {"files": []}
    files = sorted(
        REPORTING_DIR.glob("*.xlsx"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    return {"files": [f.name for f in files]}


@app.get("/download/{filename}")
async def download(filename: str, _: str = Depends(_check_auth)):
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
    fecha: str = Form(...),
    archivo: str = Form(...),
    _: str = Depends(_check_auth),
):
    global _pipeline_running
    if _pipeline_running:
        raise HTTPException(409, "El pipeline ya está en ejecución")

    env = os.environ.copy()
    env["SIPSA_FECHA"] = fecha.strip()
    env["SIPSA_ARCHIVO"] = archivo.strip()

    line_queue: queue.Queue = queue.Queue()

    def _run_kedro():
        try:
            proc = subprocess.Popen(
                [sys.executable, "-m", "kedro", "run"],
                cwd=str(PROJECT_ROOT),
                env=env,
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
