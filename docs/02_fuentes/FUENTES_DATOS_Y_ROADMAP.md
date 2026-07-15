# Fuentes de datos y roadmap de aprendizaje

Este documento clasifica las fuentes iniciales de ProcureWatch Analytics y explica como usarlas
sin perder el foco del TFM. La regla de trabajo es simple: primero datos trazables y limpios,
despues indicadores, despues grafos, y solo al final agentes/LLM para explicar.

## Mapa mental del proyecto

```text
Fuentes abiertas
  -> data/raw: guardar original sin tocar
  -> Agente 1: limpiar, normalizar y perfilar calidad
  -> data/processed: Parquet/CSV limpio y tipado
  -> Agente 2: red flags y scoring
  -> Agente 3: grafo organismo-empresa-contrato
  -> Agente 4: documentos, NLP, RAG y ficha explicativa
  -> dashboard: revision humana
```

## Estado tecnico 31/05/2026

Avance real implementado:

- Ingesta BOE, PLACE y OpenTender definida en el flujo de `run-agent1`.
- Place sources ya descargadas y localizadas en `data/raw/place`.
- PDFs de especificacion de PLACE descargados en `data/raw/reference_docs` para sustento documental.
- Reporte de cobertura entre fuentes habilitado (`agent1_contract_key_coverage.parquet`).

Pendientes inmediatos:

- revisar diferencias de emparejamiento por normalizacion de texto/fechas,
- añadir pruebas de no-deriva entre ejecuciones,
- preparar el set minimo de campos canonicos que consume Agent2.

## Fuentes aportadas

| Fuente | Rol en el TFM | Prioridad | Uso recomendado |
|---|---|---:|---|
| `arxiv.org/pdf/2602.16731` | Paper metodologico reciente sobre contratacion/datos/analitica. | Alta | Leer para justificar enfoque, red flags, datos o arquitectura si encaja con el estado del arte. |
| Hacienda - licitaciones Plataforma de Contratacion | Fuente oficial espanola de datos abiertos de contratacion. | Alta | Fuente primaria o complementaria para PLACE, especialmente si aporta datos mas actuales o completos que BOE. |
| OpenTender download | Fuente europea de comparacion y posibles indicadores ya procesados. | Media | Usar como benchmark metodologico y para comparar variables, no como primera fuente de implementacion. |
| Open Contracting Data Registry `publication/94` | Publicacion OCDS concreta en el registro de Open Contracting. | Media | Referencia para estructura OCDS y descargas interoperables. |
| datos.gob.es catalogo | Catalogo general de datasets publicos espanoles. | Media-baja | Buscar datasets auxiliares: territorios, organos, codigos, contexto economico o administrativo. |
| Zenodo `15120882` | Dataset o artefacto academico persistente. | Alta | Revisar como fuente trazable; si corresponde al BOE 2014-2024, usar como referencia de version/datos. |
| GitHub `mmunozpl/M2.851-May25` | Repositorio de codigo o practica asociada al dataset. | Alta | Aprender ETL/reproducibilidad; no copiar a ciegas, adaptar patrones utiles al TFM. |

### Conjunto de datos de `datos.gob.es` recomendados para esta fase

Para avanzar con contraste sin ruido de scraping:

- `Perfil de organismo de contratación` o equivalentes (catálogo normalizado de entidades).
- `Convocatorias de contratos` (cuando incluya CPV/estado/importes).
- `Adjudicaciones y contratos menores` (solo para entender cobertura y exclusiones).
- `Órganos de contratación / unidad de contratación` (si se encuentra disponible en datos.gob).
- `Padron de empresas o registros de proveedores` cuando haya identificadores fiables.

Criterio: se prioriza dataset con campos contractuales estables y actualizados; se ignora agregados solo de BI hasta terminar pipeline.

## Criterio de formatos

### Raw

En `data/raw` guardamos el original sin modificar. Esto es importante para reproducibilidad:

- permite demostrar de donde sale cada resultado;
- permite recalcular si cambiamos el parser;
- evita mezclar dato original con dato limpiado.

Formatos aceptables en raw:

```text
OCDS JSON / JSONL > CSV > Excel > HTML > PDF
```

### Processed

En `data/processed` guardamos datos ya limpios. El formato principal sera Parquet porque:

- conserva tipos de datos;
- ocupa menos que CSV;
- funciona bien con pandas, Polars y DuckDB;
- evita volver a parsear importes y fechas en cada ejecucion.

CSV limpio puede existir como salida auxiliar para inspeccion humana.

## Leccion 1: que estamos aprendiendo ahora

Ahora mismo estamos en la fase de Data Engineering, no de IA.

El objetivo inmediato es construir el Agente 1:

1. leer el CSV bruto de BOE;
2. detectar problemas de codificacion, comillas, separadores e importes;
3. crear una tabla limpia de contratos/adjudicaciones;
4. filtrar CPV 71;
5. generar un informe de calidad;
6. guardar el resultado en `data/processed`.

Un error habitual en proyectos de IA es empezar por el modelo. En este TFM no conviene. Si los
datos no estan bien normalizados, los red flags, grafos y agentes explicadores heredan ruido.

## Leccion 2: como pensar como cientifico de datos

El cientifico de datos se pregunta:

- Que patrones queremos medir?
- Que variables existen realmente?
- Que campos faltan?
- Que sesgos tiene la fuente?
- Que indicador es interpretable y defendible?

Ejemplo: "un solo licitador" es una red flag potente, pero solo se puede calcular si la fuente
incluye numero de ofertas o licitadores. Si no lo incluye, hay que buscarlo en PLACE, OpenTender o
documentos.

## Leccion 3: como pensar como data engineer

El data engineer se pregunta:

- Puedo repetir el proceso desde cero?
- Se conserva el dato bruto?
- Hay version, hash y fecha de la fuente?
- Los tipos estan bien definidos?
- El pipeline falla de forma clara cuando la fuente cambia?

Para ProcureWatch, esto significa que cada fichero raw debe convertirse en un dataset procesado
con esquema estable.

## Leccion 4: como pensar como Data/AI engineer

El Data/AI engineer se pregunta:

- Que parte debe resolver una regla determinista?
- Que parte puede resolver un modelo estadistico?
- Que parte justifica un LLM?
- Como evitamos que el LLM invente?
- Donde guardamos evidencias y explicaciones?

En ProcureWatch, el LLM no decide el riesgo. Solo explica resultados ya calculados por reglas,
modelos y evidencia documental.

## Proxima tarea tecnica (estado 31/05/2026)

Hoy:

- Completar la bitacora de evidencia de parser versioning en informes.
- Ejecutar la corrida completa de `run-agent1 --year 2024 --cpv-prefix 71`.
- Validar que los reportes de cobertura reflejan reglas de normalizacion acordadas.

Siguiente micro-hito:

Integrar el set de outputs de Agent1 al documento de metodologia y al diagrama de arquitectura.

Implementar el primer normalizador del CSV BOE:

```text
data/raw/licitaciones_contrataciones_BOE_2014_2024-2(in).csv
  -> data/processed/contracts_boe.parquet
  -> data/processed/contracts_boe_cpv71.parquet
  -> data/processed/data_quality_report.json
```

Campos minimos de salida:

| Campo | Tipo | Motivo |
|---|---|---|
| `contract_id` | texto | Identificador trazable del contrato/anuncio. |
| `institution` | texto | Ministerio/institucion principal. |
| `buyer_name` | texto | Organismo contratante. |
| `file_number` | texto | Expediente. |
| `award_date` | fecha | Analisis temporal. |
| `contract_type` | texto | Tipo/naturaleza contractual. |
| `procedure` | texto | Base de red flags procedimentales. |
| `region` | texto | Analisis territorial. |
| `cpv_codes` | lista/texto | Filtro CPV 71 y subfamilias. |
| `estimated_value_eur` | decimal | Desviacion de importe. |
| `awarded_value_eur` | decimal | Scoring y concentracion economica. |
| `supplier_name` | texto | Grafo y concentracion. |
| `source_url` | texto | Trazabilidad documental. |

## Decision de alcance recomendada

Para la primera demo defendible:

1. BOE 2014-2024 como fuente principal.
2. CPV 71 como dominio de validacion.
3. PLACE solo para enriquecer documentos o campos que falten.
4. OpenTender/OCDS como referencia comparativa, no como dependencia critica inicial.
5. Zenodo/GitHub como referencia academica y reproducible del origen del dataset.

## Cierre de sesion 31/05/2026

- Corrida completa de `run-agent1 --year 2024 --cpv-prefix 71` ejecutada correctamente.
- `agent1_data_quality_summary.json` en estado `ok`.
- `agent2_contracts_canonical.parquet` disponible con 51.720 filas.
- PLACE 2024 ya se procesa con filtrado temprano CPV 71.
- OpenTender 2024 ya extrae CPV correctamente desde OCDS/tender.
- `run-agent1` reutiliza cache y tarda ~23 segundos en corrida normal con artefactos existentes.
- Siguiente micro-hito: integrar el canonico Agent2 con primeras red flags y mejorar matching entre fuentes.

