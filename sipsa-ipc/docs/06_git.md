# Git — Convenciones del equipo SIPSA IPC

---

## Ramas

| Prefijo | Para qué | Ejemplo |
|---------|---------|---------|
| `main` | Rama principal · siempre estable | — |
| `feature/` | Nueva funcionalidad | `feature/agregar-pipeline-precios` |
| `fix/` | Corrección de bug | `fix/variacion-mensual-enero` |
| `docs/` | Solo documentación | `docs/actualizar-manual-api` |
| `refactor/` | Limpieza sin cambio de comportamiento | `refactor/simplificar-cleaning` |

Regla: nunca hacer `push --force` a `main`.

---

## Mensajes de commit

Formato:

```
<tipo>: <descripción corta en imperativo>

[cuerpo opcional: por qué, no qué]
```

| Tipo | Cuándo |
|------|--------|
| `feat` | Nueva funcionalidad |
| `fix` | Corrección de bug |
| `docs` | Solo cambios en documentación |
| `test` | Solo pruebas |
| `refactor` | Cambio de estructura sin cambio de comportamiento |
| `chore` | Dependencias, configuración, scripts |

Ejemplos:

```
feat: agregar nodo calcular_td_abast_otros para importaciones

fix: corregir formato BEST12 cuando variación es negativa con 2 dígitos enteros

docs: documentar parámetro archivo_entrada en 03_configuracion.md

test: agregar pruebas de equivalencia SAS para td_destino
```

---

## Checklist de un PR completo

Antes de abrir un PR, verificar que el branch tiene:

- [ ] Código nuevo o modificado en `src/` o `tests/`
- [ ] Docstrings actualizados o agregados en funciones públicas (Google style)
- [ ] `docs/04_modulos.md` actualizado si se agrega o modifica un módulo
- [ ] `docs/03_configuracion.md` actualizado si hay nuevas variables de `.env` o `parameters.yml`
- [ ] `.env.example` actualizado si hay nuevas variables de entorno
- [ ] `pyproject.toml` actualizado con versión exacta si se agrega una nueva librería
- [ ] `pytest tests\ -m "not slow"` pasa sin errores

Un PR sin pruebas para código nuevo es un PR incompleto.

---

## Proceso de PR

1. Crear rama desde `main`:
   ```cmd
   git checkout main
   git pull origin main
   git checkout -b feature/nombre-descriptivo
   ```

2. Desarrollar y hacer commits frecuentes.

3. Ejecutar pruebas antes de abrir el PR:
   ```cmd
   .venv\Scripts\pytest.exe tests\ -m "not slow" -q
   ```

4. Abrir PR hacia `main` con:
   - Título corto (< 70 chars)
   - Descripción con: qué cambia, por qué, cómo probarlo

5. Merge a `main` solo después de que las pruebas pasen.

---

## Reglas de merge

- Usar **Squash and merge** para features/fixes pequeños (mantiene el historial limpio).
- Usar **Merge commit** para features grandes con historia significativa.
- Nunca hacer merge sin que las pruebas pasen.
- La documentación va en el **mismo PR** que el código que describe — sin excepciones.

---

## Lo que NO va en Git

```gitignore
.env              # credenciales (siempre en .gitignore)
data/             # archivos de datos (Excel, Parquets)
.venv/            # entorno virtual
__pycache__/
*.pyc
.coverage
```

Los archivos de `data/` se regeneran ejecutando el pipeline con el Excel de entrada del mes.
