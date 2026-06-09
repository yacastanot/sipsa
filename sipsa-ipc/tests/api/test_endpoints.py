"""Tests de endpoints — F8 FastAPI SIPSA IPC.

Cubre T50 del cronograma: tests de endpoints con pytest + httpx.
Usa TestClient de Starlette (síncrono) con una DataStore mockeada para
que los tests no dependan de los parquets en disco.
"""
from __future__ import annotations

import os
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest
from fastapi.testclient import TestClient

# API key de prueba
_TEST_KEY = "test-key-sipsa"
os.environ["SIPSA_API_KEY"] = _TEST_KEY


# ── Fixtures de datos ─────────────────────────────────────────────────────────

def _mock_td_total() -> pd.DataFrame:
    return pd.DataFrame({
        "RArtículo_IPC": pd.array([1001, 1002], dtype="Int64"),
        "Artículo_IPC": ["ARROZ", "LIMÓN"],
        "AbastTotal_MesActual": [22451.17, 12042.63],
        "AbastTotal_MesAnterior": [23183.75, 12460.01],
        "AbastTotal_AnoAnterior": [22842.12, 12313.28],
        "VariacMensual_num": [-3.159875, -3.349776],
        "VariacAnual_num": [-1.711501, -2.198065],
        "VariacMensual": ["-3,15987491238%", "-3,34977647089%"],
        "VariacAnual": ["-1,71150084588%", "-2,19806547109%"],
    })


def _mock_td_abast() -> pd.DataFrame:
    return pd.DataFrame({
        "RArtículo_IPC": pd.array([1001, 1001, 1002], dtype="Int64"),
        "Artículo_IPC": ["ARROZ", "ARROZ", "LIMÓN"],
        "Departamento Proc.": ["Tolima", "Meta", "Valle del Cauca"],
        "Sum_Ton": [5403.21, 5188.65, 6020.30],
        "Total_Artículo": [22451.17, 22451.17, 12042.63],
        "Participación": [24.07, 23.11, 50.00],
    })


def _mock_td_destino() -> pd.DataFrame:
    return pd.DataFrame({
        "RArtículo_IPC": pd.array([1001, 1001, 1002], dtype="Int64"),
        "Artículo_IPC": ["ARROZ", "ARROZ", "LIMÓN"],
        "Ciudad": pd.array(["Barranquilla", "Medellín", "Bogotá, D.C."], dtype="string"),
        "Sum_Ton": [6620.33, 6264.10, 12042.63],
        "Total_Artículo": [22451.17, 22451.17, 12042.63],
        "Participación": [29.49, 27.90, 100.0],
    })


def _mock_td_abast_otros() -> pd.DataFrame:
    return pd.DataFrame({
        "RArtículo_IPC": pd.array([1001], dtype="Int64"),
        "Artículo_IPC": ["ARROZ"],
        "Municipio Proc.": ["Ecuador"],
        "Sum_Ton": [460.0],
        "Total_Artículo": [463.5],
        "Participación": [99.24],
    })


def _mock_historico() -> pd.DataFrame:
    return pd.DataFrame({
        "RArtículo_IPC": pd.array([1001, 1002], dtype="Int64"),
        "Artículo_IPC": ["ARROZ", "LIMÓN"],
        "AbastTotal_MesActual": [22451.17, 12042.63],
        "AbastTotal_MesAnterior": [23183.75, 12460.01],
        "AbastTotal_AnoAnterior": [22842.12, 12313.28],
        "VariacMensual": ["-3,15987491238%", "-3,34977647089%"],
        "VariacAnual": ["-1,71150084588%", "-2,19806547109%"],
        "VariacMensual_num": [-3.159875, -3.349776],
        "VariacAnual_num": [-1.711501, -2.198065],
        "mes": ["Abril", "Abril"],
        "anio": [2025, 2025],
    })


@pytest.fixture
def client():
    """TestClient con DataStore mockeada en memoria.

    Se parchea ``store.load`` para que el lifespan de FastAPI no cargue los
    parquets reales y en su lugar use los datos de prueba.
    """
    from sipsa_ipc.api.data_store import store
    from sipsa_ipc.api.main import app

    def _cargar_mock():
        store._td_total = _mock_td_total()
        store._td_abast = _mock_td_abast()
        store._td_destino = _mock_td_destino()
        store._td_abast_otros = _mock_td_abast_otros()
        store._historico = _mock_historico()
        store.loaded = True

    with patch.object(store, "load", side_effect=_cargar_mock):
        with TestClient(app) as c:
            yield c


_HEADERS = {"X-API-Key": _TEST_KEY}


# ── /health ───────────────────────────────────────────────────────────────────

def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["estado"] == "ok"
    assert body["datos_cargados"] is True
    assert body["articulos_disponibles"] == 2


# ── Autenticación ──────────────────────────────────────────────────────────────

def test_sin_api_key_retorna_403(client):
    r = client.get("/meses")
    assert r.status_code == 403


def test_api_key_incorrecta_retorna_403(client):
    r = client.get("/meses", headers={"X-API-Key": "clave-incorrecta"})
    assert r.status_code == 403


def test_api_key_valida_permite_acceso(client):
    r = client.get("/meses", headers=_HEADERS)
    assert r.status_code == 200


# ── GET /meses ────────────────────────────────────────────────────────────────

def test_meses_retorna_lista(client):
    r = client.get("/meses", headers=_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert "periodos" in body
    assert body["total"] == 1
    assert body["periodos"][0]["mes"] == "Abril"
    assert body["periodos"][0]["anio"] == 2025
    assert body["periodos"][0]["periodo"] == "Abril2025"


# ── GET /abastecimiento/{mes}/{articulo} ───────────────────────────────────────

def test_abastecimiento_por_codigo(client):
    r = client.get("/abastecimiento/Abril2025/1001", headers=_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["codigo_ipc"] == 1001
    assert body["articulo_ipc"] == "ARROZ"
    assert len(body["departamentos"]) == 2
    assert body["departamentos"][0]["departamento"] == "Tolima"


def test_abastecimiento_por_nombre(client):
    r = client.get("/abastecimiento/Abril2025/ARROZ", headers=_HEADERS)
    assert r.status_code == 200
    assert r.json()["codigo_ipc"] == 1001


def test_abastecimiento_articulo_inexistente_retorna_404(client):
    r = client.get("/abastecimiento/Abril2025/9999", headers=_HEADERS)
    assert r.status_code == 404


def test_abastecimiento_mes_invalido_retorna_422(client):
    r = client.get("/abastecimiento/mes-invalido/1001", headers=_HEADERS)
    assert r.status_code == 422


def test_abastecimiento_destinos(client):
    r = client.get("/abastecimiento/destinos/Abril2025/1001", headers=_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["codigo_ipc"] == 1001
    assert len(body["ciudades"]) == 2


# ── GET /estadisticas/{articulo}/{mes} ─────────────────────────────────────────

def test_estadisticas_retorna_variaciones(client):
    r = client.get("/estadisticas/1001/Abril2025", headers=_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["articulo_ipc"] == "ARROZ"
    assert body["variac_mensual_fmt"] == "-3,15987491238%"
    assert body["abast_mes_actual"] == pytest.approx(22451.17)
    assert len(body["top_departamentos"]) == 2
    assert len(body["top_destinos"]) == 2
    assert len(body["importaciones"]) == 1


def test_estadisticas_articulo_por_nombre(client):
    r = client.get("/estadisticas/LIMÓN/Abril2025", headers=_HEADERS)
    assert r.status_code == 200
    assert r.json()["codigo_ipc"] == 1002


def test_estadisticas_articulo_inexistente_retorna_404(client):
    r = client.get("/estadisticas/9999/Abril2025", headers=_HEADERS)
    assert r.status_code == 404


# ── GET /comparacion/{periodo_a}/{periodo_b} ──────────────────────────────────

def test_comparacion_mismo_periodo(client):
    r = client.get("/comparacion/Abril2025/Abril2025", headers=_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["periodo_a"] == "Abril2025"
    assert body["periodo_b"] == "Abril2025"
    assert len(body["articulos"]) == 2
    for item in body["articulos"]:
        assert item["variacion_pct"] == pytest.approx(0.0)


def test_comparacion_periodo_inexistente_retorna_404(client):
    r = client.get("/comparacion/Enero2020/Abril2025", headers=_HEADERS)
    assert r.status_code == 404


def test_comparacion_formato_invalido_retorna_422(client):
    r = client.get("/comparacion/abc/Abril2025", headers=_HEADERS)
    assert r.status_code == 422


# ── POST /procesar/{mes} ──────────────────────────────────────────────────────

def test_procesar_kedro_exitoso(client):
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stderr = ""
    mock_result.stdout = "Pipeline execution completed."

    with patch("sipsa_ipc.api.routers.pipeline.subprocess.run", return_value=mock_result):
        r = client.post("/procesar/Abril2025", headers=_HEADERS)

    assert r.status_code == 202
    body = r.json()
    assert body["estado"] == "completado"
    assert body["returncode"] == 0


def test_procesar_kedro_falla(client):
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = "Error: archivo no encontrado"

    with patch("sipsa_ipc.api.routers.pipeline.subprocess.run", return_value=mock_result):
        r = client.post("/procesar/Abril2025", headers=_HEADERS)

    assert r.status_code == 202
    body = r.json()
    assert body["estado"] == "error"
    assert body["returncode"] == 1


def test_procesar_mes_invalido_retorna_422(client):
    r = client.post("/procesar/mes-invalido", headers=_HEADERS)
    assert r.status_code == 422


# ── GET / (root) ──────────────────────────────────────────────────────────────

def test_root_no_requiere_auth(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["api"] == "SIPSA IPC"
