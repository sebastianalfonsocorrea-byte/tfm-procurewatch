# Demo rápida del MVP

Objetivo: enseñar Agent 1 con salida reproducible y persistencia opcional en PostgreSQL, sin
descargar datos nuevos.

## Requisitos previos

- Docker Desktop en ejecución.
- El contenedor `postgres` levantado con `docker compose up -d postgres`.
- Variables `.env` cargadas o `PROCUREWATCH_POSTGRES_DSN` definido.

## Ejecución

```bash
cd /ruta/al/repo/tfm-procurewatch
PYTHONPATH=scr PROCUREWATCH_POSTGRES_DSN=postgresql://procurewatch:procurewatch@localhost:5432/procurewatch \
  python -m procurewatch run-mvp --year 2024 --cpv-prefix 71
```

## Qué enseña

- `data/processed/agent1_run_report.json`
- `data/processed/contracts_analytical.parquet`
- `data/processed/suppliers_analytical.parquet`
- Tablas PostgreSQL:
  - `agent1_contracts_analytical`
  - `agent1_suppliers_analytical`

## Verificación rápida

```bash
PYTHONPATH=scr python - <<'PY'
from sqlalchemy import create_engine, text

engine = create_engine(
    "postgresql+psycopg://procurewatch:procurewatch@localhost:5432/procurewatch",
    future=True,
)
with engine.connect() as conn:
    for table in ["agent1_contracts_analytical", "agent1_suppliers_analytical"]:
        print(table, conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one())
PY
```
