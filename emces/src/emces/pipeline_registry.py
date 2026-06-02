"""Registro de pipelines del proyecto EMCES.

Pipelines individuales (auto-descubiertos por find_pipelines)
─────────────────────────────────────────────────────────────────────────────
  fletes           Fletes mensual: R → Python/Kedro
  cancilleria      Cancillería mensual: SAS → Python/Kedro
  consolidacion_ra Consolida Fletes + Cancillería → base_ra (mes corriente)
  union_ra         Acumula base_ra al histórico RA → BaseEMCES-RA_..._F..C...xlsx

Pipelines compuestos (definidos aquí)
─────────────────────────────────────────────────────────────────────────────
  ra               fletes + cancilleria + consolidacion_ra
                   → Todos los RA del mes, desde fuentes crudas hasta base_ra.
                   → Equivale a "Función RA: Consolidación" del diagrama.

  ra_completo      ra + union_ra
                   → Flujo mensual RA completo: procesa + acumula al histórico.
                   → Ejecutar una vez al mes después de tener los archivos.

  __default__      Todos los individuales (no incluye compuestos para evitar
                   duplicar nodos en un kedro run sin --pipeline).

Uso frecuente
─────────────────────────────────────────────────────────────────────────────
  kedro run                          # todos los individuales
  kedro run --pipeline fletes        # solo fletes
  kedro run --pipeline cancilleria   # solo cancillería
  kedro run --pipeline ra            # fletes + cancillería + consolidación
  kedro run --pipeline union_ra      # solo acumulación histórica
  kedro run --pipeline ra_completo   # flujo mensual RA de extremo a extremo

Pipelines pendientes (diagrama de flujo EMCES)
─────────────────────────────────────────────────────────────────────────────
  viajes           Sub-proceso viajes (amber en diagrama)
  encuesta         Consolidación encuesta EMCES
  integracion      Encuesta + RA → Base Final EMCES
  panel / banrep / cuadros / empalme / anonimizacion
"""
from __future__ import annotations

from kedro.framework.project import find_pipelines
from kedro.pipeline import Pipeline


def register_pipelines() -> dict[str, Pipeline]:
    """Registra todos los pipelines del proyecto EMCES.

    - find_pipelines() auto-descubre los individuales.
    - Los compuestos se construyen sumando los individuales.
    - __default__ usa solo individuales para evitar duplicar nodos.
    """
    pipelines = find_pipelines(raise_errors=True)

    _get = lambda name: pipelines.get(name, Pipeline([]))  # noqa: E731

    # ── ra: procesamiento RA del mes (fuentes → base_ra) ─────────────────────
    pipelines["ra"] = (
        _get("fletes")
        + _get("cancilleria")
        + _get("consolidacion_ra")
    )

    # ── ra_completo: flujo mensual de extremo a extremo ───────────────────────
    # Orden garantizado por dependencias Kedro:
    #   fletes_maestro + canc_maestro → base_ra → base_ra_acumulada → Excel
    pipelines["ra_completo"] = (
        _get("fletes")
        + _get("cancilleria")
        + _get("consolidacion_ra")
        + _get("union_ra")
    )

    # ── __default__: todos los individuales sin los compuestos ────────────────
    _compuestos = {"ra", "ra_completo"}
    _individuales = {k: v for k, v in pipelines.items() if k not in _compuestos}
    pipelines["__default__"] = sum(_individuales.values())

    return pipelines
