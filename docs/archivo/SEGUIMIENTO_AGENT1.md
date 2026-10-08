# Seguimiento Operativo del Proyecto

Objetivo: registrar avances del pipeline para trazabilidad del TFM y reproducibilidad de decisiones.


## 23/06/2026

### Hecho

- Se ejecuta el MVP real con PostgreSQL de Docker usando `procurewatch run-mvp`.
- El runner reutiliza los artefactos cacheados de BOE y OpenTender y un placeholder local de PLACE
  para no forzar descargas durante la prueba.
- La persistencia en PostgreSQL queda verificada con filas reales en:
  - `agent1_contracts_analytical`;
  - `agent1_suppliers_analytical`.
- El entorno local necesitaba el driver `psycopg` para que SQLAlchemy pudiera abrir el DSN
  `postgresql://...`; el conector lo normaliza a `postgresql+psycopg://...`.

## 22/06/2026

### Hecho

- Se añade `procurewatch run-mvp` como envoltorio mínimo para el borrador:
  ejecuta Agent 1 y activa la persistencia en PostgreSQL cuando `PROCUREWATCH_POSTGRES_DSN`
  está configurado en el entorno.
- Se añade la persistencia mínima de Agent 1 a PostgreSQL para el MVP:
  `procurewatch run-agent1 --write-postgres`.
- El pipeline guarda las tablas analíticas `CONTRATO` y `ADJUDICATARIO` en la base de datos
  configurada por `PROCUREWATCH_POSTGRES_DSN`, manteniendo los Parquet como salida principal.
- Se incorpora una prueba de integración con SQLite para verificar que la exportación SQL escribe
  filas reales sin depender de tener PostgreSQL levantado durante los tests.
- Se corrige el parser de OpenTender para el formato real descargado desde la página española:
  el JSONL es OCDS compilado en la raíz, no un contenedor con `releases`.
- La normalización de OpenTender deja de producir una salida vacía y, sobre una muestra real,
  parsea 1.298 registros con 1.260 filas CPV 71.
- Se rehace la ingesta de OpenTender y la reconstrucción de artefactos derivados sin repetir
  la descarga de PLACE.
- Resultado de cobertura tras la reconstrucción:
  - `op_contract_keys`: 1.260;
  - `boe_contract_keys`: 3.883;
  - `place_contract_keys`: 12.605;
  - intersecciones con OpenTender: 0.
- La limpieza de temporales sigue funcionando: la carpeta `/private/tmp/procurewatch-raw`
  desaparece al finalizar la corrida.

## 21/06/2026

### Hecho

- Se integra `OrganosContratacion.xlsx` como enriquecimiento opcional del Agente 1 mediante
  `procurewatch run-agent1 --buyer-catalog <ruta>` y se genera
  `buyer_catalog_enrichment_report.json`.
- `run-agent1` y `run-batch` aceptan `--raw-dir` para descargar fuentes en un directorio temporal
  y `--cleanup-downloads` para borrar solo los archivos descargados por el pipeline al terminar.
- OpenTender admite `--opentender-download-url` para bajar el fichero desde la página española
  `https://opentender.eu/es/download`; si esa página no expone el enlace directo en HTML, el
  conector usa un fallback técnico al registro de OCP para resolver la descarga.
- El cruce es determinista y conservador: solo rellena `codigo_organismo` y
  `nivel_administracion` cuando la coincidencia por nombre es segura.
- Validacion sobre un preview real de BOE CPV 71:
  - 174/200 filas con `codigo_organismo` rellenado;
  - 173/200 filas con `nivel_administracion` rellenado;
  - 26 filas siguen sin cruce oficial;
  - 52 nombres del catalogo quedan ambiguos y se excluyen del relleno automatico.
- Se incorpora un informe reproducible que separa presencia de columnas, cobertura real y
  cumplimiento de requisitos:
  - `agent1_coverage_report.json`;
  - `agent1_coverage_report.md`.
- El informe se regenera con `procurewatch report-agent1-coverage` y no interpreta campos nulos
  como requisitos cumplidos.
- Resultado sobre las 4.062 líneas de adjudicación BOE:
  - los 27 campos obligatorios de `CONTRATO` existen en el esquema;
  - completitud de los siete campos OCDS críticos medibles: 99,79 %;
  - 4.018 filas tienen completos esos siete campos;
  - cobertura de NIF del adjudicatario: 0 %, objetivo no alcanzado;
  - coherencia temporal: no evaluable por ausencia de fecha de adjudicación;
  - 0 identificadores de contrato duplicados y 0 importes negativos detectados.
- El estado global permanece `partial`: faltan integración efectiva de PLACE/OpenTender, carga en
  PostgreSQL y actualización incremental por registros.
- La tabla analítica `CONTRATO` deja de construirse con todos los avisos BOE y utiliza la salida
  conservadora de líneas de adjudicación cuando está disponible.
- `id_contrato` representa la línea de adjudicación y `id_licitacion` representa el expediente.
- La capa canónica conserva `source_notice_id` y `source_tender_id` para mantener trazabilidad y
  preparar el mismo contrato de datos para PLACE y OpenTender.
- La reconstrucción completa con los datos BOE disponibles genera:
  - 4.062 contratos analíticos/líneas de adjudicación;
  - 3.607 licitaciones o expedientes distintos;
  - 2.086 adjudicatarios agregados por el identificador disponible;
  - 2.182,547 millones de euros de importe adjudicado.
- Estas cifras son resultados reproducibles del pipeline actual y no se fuerzan para coincidir con
  las cifras descriptivas de la memoria.
- Se implementan identificadores estables para las unidades de análisis BOE:
  - aviso;
  - expediente;
  - línea de adjudicación.
- Se genera `boe_analysis_units_report.json` con recuentos, organismos, adjudicatarios e importes
  para cada unidad.
- Resultado reproducible:
  - 8.097 filas CPV 71 y 7.929 avisos identificados;
  - 4.452 filas de tipo contratación y 4.284 anuncios identificados;
  - 4.062 líneas de adjudicación con CPV principal 71;
  - 3.607 expedientes normalizados con CPV principal 71.
- La normalización básica de nombres produce 355 organismos y 1.990 adjudicatarios en las líneas
  de adjudicación. Estas cifras no sustituyen una resolución de entidades basada en identificadores
  oficiales.
- Se separa una salida BOE específica de líneas de adjudicación:
  `contracts_boe_award_lines_cpv71.parquet`.
- La selección exige tipo de aviso `Contratación` y CPV principal con prefijo 71.
- La deduplicación elimina únicamente repeticiones exactas del mismo anuncio, expediente,
  adjudicatario, importes, objeto y CPV.
- Se conservan varias líneas del mismo expediente cuando representan adjudicatarios o importes
  distintos, porque pueden corresponder a lotes o premios legítimos.
- Resultado sobre el BOE completo disponible:
  - 4.063 líneas de adjudicación antes de deduplicar;
  - 4.062 líneas tras eliminar una repetición exacta;
  - 3.931 anuncios BOE distintos;
  - 3.601 números de expediente distintos;
  - importe adjudicado agregado: 2.182,547 millones de euros.

### Decisiones

- La salida se denomina `award_lines` y no `contracts` para no afirmar que cada fila representa
  necesariamente un contrato independiente.
- No se fuerza la cifra de 3.443 contratos escrita en la memoria. Con el fichero disponible, la
  selección reproducible produce un universo diferente, aunque el importe agregado es cercano a
  los 2.179 millones citados.
- La diferencia se revisará contra la metodología exacta del dataset original y se documentará o
  corregirá en la memoria si no puede reproducirse.

## 20/06/2026

### Hecho

- Se formaliza el modelo analítico mínimo del apartado 5.4 de la propuesta técnica:
  - entidad `CONTRATO` con sus 27 campos obligatorios;
  - entidad `ADJUDICATARIO` con sus 13 campos obligatorios.
- Cada campo declara tipo, responsable, nulabilidad, valores permitidos y descripción.
- Se añade una prueba automática que falla si se elimina u omite cualquier campo exigido.
- El modelo queda documentado en `docs/MODELO_DATOS_ANALITICO.md`.
- El dataset canónico se transforma a dos salidas ajustadas al modelo:
  - `contracts_analytical.parquet`;
  - `suppliers_analytical.parquet`.
- El mapeo reutiliza exclusivamente valores de BOE, PLACE u OpenTender y calcula solo variables
  derivables, como desviación de importe y días de resolución.
- Los campos todavía dependientes de Agent2, Agent3 o Agent4 permanecen nulos.
- La transformación se ejecuta sobre el BOE completo procesado:
  - 7.867 contratos/avisos canónicos tras deduplicación técnica por clave de fuente;
  - 2.225 adjudicatarios agrupados por NIF cuando existe o por nombre normalizado.
- La cobertura confirma que BOE no aporta por sí solo varios campos:
  - código oficial de organismo, NIF del adjudicatario, fecha de adjudicación y número de ofertas
    quedan sin cobertura;
  - los campos de scoring, red y documentos permanecen nulos por pertenecer a otros agentes.
- El nombre de institución del BOE no se reutiliza como `codigo_organismo`; ese campo solo se
  rellenará con un identificador oficial procedente de una fuente fiable.
- El informe `agent1_data_quality_summary.json` incorpora las tres métricas de calidad exigidas
  por la propuesta técnica:
  - completitud de campos OCDS críticos;
  - validez y cobertura de NIF/NIE/CIF de adjudicatarios;
  - coherencia temporal entre publicación y adjudicación.
- Las métricas separan ausencia de dato, dato inválido y fila no evaluable para evitar presentar
  como calidad alta una cobertura insuficiente.
- Los umbrales de referencia quedan registrados en el propio artefacto:
  - completitud OCDS superior al 90 %;
  - identificadores fiscales válidos sobre el total superior al 85 %;
  - coherencia temporal superior al 98 %.
- Se añade una prueba unitaria con fechas coherentes e incoherentes, identificadores válidos,
  inválidos y ausentes.
- Se ejecuta la normalización completa del fichero BOE 2014-2024 con 97.154 líneas:
  - 96.809 filas parseadas;
  - 345 errores de parseo;
  - tasa de éxito de parseo: 99,6449 %;
  - 8.097 avisos con CPV 71.
- El desglose CPV 71 obtenido es:
  - 3.645 avisos de licitación;
  - 4.452 avisos de contratación/adjudicación;
  - 5.055 números de expediente distintos.

### Decisiones

- Una métrica no evaluable o por debajo del objetivo deja el estado global en `warning`, no en
  `error`; `error` se reserva para una salida canónica vacía.
- La validez fiscal se informa tanto sobre el total de contratos como sobre los identificadores
  presentes. El objetivo de la propuesta se contrasta contra el total para no ocultar nulos.
- Esta validación se implementa antes de la corrida completa para que el procesamiento masivo
  produzca evidencia de calidad utilizable en la memoria.
- Los 8.097 registros CPV 71 no se presentan como 8.097 contratos adjudicados. El fichero BOE
  contiene tipos de aviso distintos, lotes y publicaciones sucesivas de un mismo expediente.
  Antes de comparar con los 3.443 contratos adjudicados citados en la memoria debe definirse una
  política reproducible de selección y deduplicación.

### Siguiente paso

- Separar explícitamente avisos de licitación y adjudicación.
- Definir una clave de expediente/lote y una política de deduplicación que permita reproducir el
  universo de contratos adjudicados descrito en la memoria.
- Ejecutar el Agente 1 con las fuentes completas dentro del alcance BOE 2014-2024, PLACE 2024 y
  OpenTender desde la página oficial de OCP, manteniendo el filtrado CPV 71.
- Revisar los resultados reales de estas métricas y documentar cualquier objetivo no alcanzado.
- Resolver la disponibilidad de almacenamiento antes de descargar PLACE: quedan aproximadamente
  4,6 GB libres y el ZIP anual principal ocupa alrededor de 1,8 GB.

## 31/05/2026

### Hecho

- run-agent1 quedo operativo como orquestador minimo de 3 fuentes: BOE, PLACE y OpenTender.
- Cobertura entre fuentes habilitada:
  - `data/processed/agent1_contract_key_coverage.parquet`
  - `data/processed/agent1_contract_key_coverage_preview.csv`
- Reporte de ejecucion unificado:
  - `data/processed/agent1_run_report.json` (sha256, tamano, fecha, versiones de parsers).
- PLACE ahora tiene retry en descarga, `downloaded=False` al fallo final y limpieza de temporal.
- `PARSER_VERSION = "1.0.0"` incorporado en boe, place y opentender.
- `run-batch` implementado como frontera operativa semanal/mensual:
  - comando `procurewatch run-batch`.
  - persistencia de estado en `data/processed/run_batch_state.json`.
  - manifest detallado por ejecución en `data/manifest/batches/<run_mode>/<batch_id>/manifest.json`.
  - lógica idempotente semanal: si no cambia hash/tamaño de fuentes críticas, se salta `run-agent1`.
- documentado stack técnico completo en `docs/00_vision/STACK_TECNICO_PROYECTO.md`.

### Decisiones

- Mantener `Parquet` como almacenamiento base procesado.
- Mantener `CSV` solo como preview humana y auditoria rapida.
- En vez de añadir mas fuentes ahora, estabilizar primero la normalizacion de `contract_key_canon`.
- Priorizar trazabilidad y calidad antes de integrar LLM/heuristicas avanzadas.

### Riesgos

- Posibles falsos negativos en cobertura por diferencias textuales y de formato de fechas entre fuentes.
- El ajuste de normalizacion puede cambiar la tasa de overlap y aparentar mejora sin valor real.
- Faltan pruebas de estabilidad de calidad para toda la corrida end-to-end con pandas en este entorno de pruebas.

### Acciones siguientes

- Ajustar limpieza de texto/fechas para `contract_key_canon` y medir mejora de cobertura.
- Aniadir tests de no-deriva entre ejecuciones para dataset Agent1.
- Integrar el output de Agent1 a estado LangGraph de la capa orquestadora.
- Documentar politicas de normalizacion y exclusiones en `docs/03_agent1_ingesta/PLAN_AGENTE1_PIPELINE.md`.
- Ampliar tests de integración con escenarios de batch (skip/resync semanal y ejecución mensual).

## 01/06/2026 (previsto)

### Objetivo

- Cerrar el bloque de calidad final de Agent1.
- Dejar protocolo de ejecucion reproducible en docs de agente.
- Preparar dataset canonico estricto para Agent2.

## Registro de trazabilidad de documentacion actualizada

- `docs/03_agent1_ingesta/PLAN_AGENTE1_PIPELINE.md` (estado, checklist, fuentes y flujo).
- `docs/02_fuentes/FUENTES_DATOS_Y_ROADMAP.md` (fuentes utiles + priorizacion datos.gob.es).
- `docs/03_agent1_ingesta/SEGUIMIENTO_AGENT1.md` (log de decisiones y riesgos).
- `README.md` (estado tecnico, comandos de control y proximos pasos).
- `data/processed/agent1_run_report.json` (metadatos de corrida).
- `docs/03_agent1_ingesta/PLAN_INGESTA_BATCH_AGENT1.md` (modelo semanal/mensual de refresh y propuesta de integración datos.gob.es).

## Cierre real de sesion 31/05/2026

### Hecho adicional

- PLACE perfiles 2024 procesado con filtrado temprano CPV 71:
  - 633.995 entradas inspeccionadas.
  - 49.918 candidatas CPV 71.
  - 12.611 registros deduplicados CPV 71 cuando se ejecuto solo `profiles`.
- PLACE agregacion 2024 procesado con filtrado temprano CPV 71:
  - 242.265 entradas inspeccionadas.
  - 23.606 candidatas CPV 71.
  - 6.359 registros deduplicados CPV 71 cuando se ejecuto solo `aggregation`.
- `run-agent1` optimizado con cache por fuente:
  - reutiliza `contracts_boe*.parquet`, `contracts_place*.parquet` y `contracts_opentender*.parquet` si coinciden fuentes y reportes.
  - `--force-rebuild` fuerza reconstruccion completa.
- `run-agent1 --year 2024 --cpv-prefix 71` ejecutado correctamente tras optimizacion.
- Tiempo observado de corrida normal con cache: ~23 segundos.
- `agent1_data_quality_summary.json` queda en estado `ok`.
- `agent2_contracts_canonical.parquet` generado con 51.720 filas.
- Tests ejecutados:
  - `python -m unittest tests.test_agent1 tests.test_batch`
  - Resultado historico: 5 tests OK. Ver seguimiento general para la validacion actual.

### Artefactos finales

- `data/processed/agent1_run_report.json`
- `data/processed/agent1_contract_key_coverage.parquet`
- `data/processed/agent1_contract_key_coverage_preview.csv`
- `data/processed/agent1_data_quality_summary.json`
- `data/processed/agent2_contracts_canonical.parquet`
- `data/processed/agent2_contracts_canonical_preview.csv`
- `data/processed/agent2_contracts_canonical_schema.json`

### Siguiente sesion

- Prioridad 1: mejorar matching entre BOE, PLACE y OpenTender; las intersecciones actuales son 0.
- Prioridad 2: fijar pruebas de no-deriva para cobertura y schema canonico.
- Prioridad 3: conectar `agent2_contracts_canonical.parquet` con el primer set de red flags.
