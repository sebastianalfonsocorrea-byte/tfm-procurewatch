# Modelo de datos analítico

Fuente de requisitos: apartado 5.4 de `Propuesta Técnica_SASM.pdf`.

La definición ejecutable y versionada se encuentra en
`scr/procurewatch/agent1/analytical_schema.py`. El esquema declara todos los campos mínimos de
las entidades `CONTRATO` y `ADJUDICATARIO`.

## Responsabilidad por agente

| Responsable | Campos |
|---|---|
| Agent1 | Identificadores, organismo, contrato, procedimiento, CPV, importes, fechas, ofertas, adjudicatario, agregados básicos y fuentes cruzadas |
| Agent2 | Red flags, scores, niveles de riesgo y métricas de recurrencia o concentración |
| Agent3 | Centralidad y comunidades del grafo |
| Agent4 | Referencias a fragmentos documentales recuperados |
| Front-end | Estado de revisión humana |

## Política de valores ausentes

- Todos los campos exigidos forman parte del esquema aunque todavía no puedan rellenarse.
- Cuando una fuente no proporciona un dato, se conserva como `null`.
- No se inventan ni imputan valores para aparentar una mayor cobertura.
- La cobertura se medirá por campo y por fuente.
- Los campos producidos por Agent2, Agent3, Agent4 o el front-end permanecerán nulos hasta que se
  ejecute el componente responsable.

## Salidas de Agent1

Agent1 materializa:

- `data/processed/contracts_analytical.parquet`
- `data/processed/contracts_analytical_preview.csv`
- `data/processed/suppliers_analytical.parquet`
- `data/processed/suppliers_analytical_preview.csv`

El canónico técnico anterior se conserva como frontera trazable. Las nuevas tablas aplican el
modelo del apartado 5.4 y dejan como `null` los campos que dependen de información no disponible o
de otros agentes.

## Unidades de análisis BOE

- `id_aviso`: identifica una publicación BOE.
- `id_expediente`: agrupa publicaciones y líneas que comparten organismo y número de expediente.
- `id_linea_adjudicacion`: distingue adjudicatarios/importes dentro de un anuncio y expediente.

En la tabla `CONTRATO`, `id_contrato` usa la línea de adjudicación y `id_licitacion` usa el
expediente. El identificador del aviso se conserva en la capa canónica como
`source_notice_id`.

El BOE no siempre publica un identificador explícito de lote. Por ello,
`id_linea_adjudicacion` es una clave técnica trazable, no una afirmación de que la fila sea un
contrato jurídico independiente.

El informe se regenera con:

```bash
python -m procurewatch.agent1.boe_units
```
