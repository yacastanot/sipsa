"""Configuración global de pytest para el proyecto SIPSA IPC.

Marcadores disponibles:
  - slow        : pruebas que ejecutan el pipeline completo (~30s)
  - integration : pruebas que acceden a archivos reales en disco
  - performance : pruebas de rendimiento y carga de la API

Para saltar las pruebas lentas en desarrollo:
    pytest -m "not slow"

Para ejecutar solo las de integración:
    pytest -m integration
"""
import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: pruebas que ejecutan kedro run completo")
    config.addinivalue_line("markers", "integration: pruebas que leen artefactos reales en disco")
    config.addinivalue_line("markers", "performance: pruebas de rendimiento de la API")
