# Estrategia para fuentes Hacienda / PLACE

## Que estamos incorporando

La pagina de datos abiertos de Hacienda sobre licitaciones de la Plataforma de Contratacion del
Sector Publico agrupa seis conjuntos principales:

1. Licitaciones en perfiles del contratante ubicados en PLACSP, sin contratos menores.
2. Licitaciones publicadas mediante mecanismos de agregacion, sin contratos menores.
3. Contratos menores.
4. Encargos a medios propios.
5. Consultas preliminares de mercado.
6. Perfiles de contratante de organos alojados en PLACSP.

Los cinco primeros se distribuyen como ficheros comprimidos con feeds Atom/XML. El sexto se
distribuye como un XLSX de organos de contratacion.

## Como encaja con BOE

BOE ya nos ha dado una base longitudinal 2014-2024 en CSV. PLACE debe servir para contrastar y
enriquecer, no para sustituirlo todo de golpe.

| Fuente | Uso en ProcureWatch |
|---|---|
| BOE 2014-2024 | Base longitudinal principal ya normalizada. |
| PLACE perfiles | Contraste oficial, documentos, numero de ofertas, adjudicatarios, lotes y mas detalle. |
| PLACE agregacion | Complemento para entidades que publican por agregacion. |
| Contratos menores | Red flags de recurrencia/fraccionamiento potencial. |
| Encargos a medios propios | Contexto de contratacion no competitiva o instrumental. |
| Consultas preliminares | Contexto temprano/documental, mas util para NLP que para scoring v1. |
| OrganosContratacion.xlsx | Normalizacion de compradores y enriquecimiento de organismos. |

## Orden recomendado

No descargamos todo sin mirar. El orden profesional es:

1. Descargar documentacion tecnica y `OrganosContratacion.xlsx`.
2. Descargar una muestra anual, recomendada: 2024.
3. Inspeccionar ZIP y feeds Atom/XML.
4. Construir parser PLACE para campos minimos.
5. Filtrar CPV 71.
6. Cruzar con BOE por URL, expediente, organismo, fecha, CPV e importe.
7. Solo despues ampliar a historico completo.

## Por que no empezar con todo el historico

PLACE publica actualizaciones diarias y una misma licitacion puede aparecer varias veces. Eso
significa que no basta con concatenar XML:

- hay que resolver versiones;
- hay que seguir enlaces `atom:link rel="next"`;
- hay que distinguir altas, actualizaciones y eliminaciones;
- hay que deduplicar por identificador de licitacion/expediente;
- hay que elegir el ultimo estado util para analisis.

Esto es una excelente parte de Data Engineering para el TFM, pero debe hacerse con control.

## Primer contraste viable

Para el primer contraste con BOE CPV 71:

```text
BOE CPV 71 normalizado
  + PLACE perfiles 2024
  + PLACE agregacion 2024
  + OrganosContratacion.xlsx
```

Campos de cruce candidatos:

| Campo BOE | Campo PLACE esperado | Comentario |
|---|---|---|
| `source_url` / `notice_id` | URL o identificador de publicacion | Mejor clave si aparece. |
| `file_number` | numero de expediente | Puede requerir limpieza. |
| `buyer_name` | organo de contratacion | Requiere normalizacion de nombres. |
| `publication_date` | fecha actualizacion/publicacion | No siempre sera la misma. |
| `cpv_code_list` | clasificacion CPV | Muy util para filtrar CPV 71. |
| `estimated_value_eur` | valor estimado/licitacion | Util para validacion. |
| `supplier_name` | adjudicatario | Solo cuando el procedimiento tenga resultado. |

## Que aprendemos aqui

### Data Engineering

Aprendemos a tratar fuentes oficiales reales con Atom/XML, ZIPs historicos, versionado,
deduplicacion y trazabilidad.

### Data Science

Aprendemos a validar si dos fuentes cuentan la misma historia: volumen anual, importes, CPV,
organismos, adjudicatarios y procedimientos.

### Data/AI

Aprendemos a decidir que evidencia necesita el agente explicador. El LLM no "adivina": recibe
datos tabulares contrastados y fragmentos documentales descargados de fuentes oficiales.

## Decision inicial

La primera descarga automatizada debe limitarse a:

- documentacion tecnica PDF;
- `OrganosContratacion.xlsx`;
- ZIP anual 2024 de licitaciones en perfiles;
- ZIP anual 2024 de licitaciones por agregacion;
- opcionalmente ZIP anual 2024 de contratos menores.

Si el tamano es razonable y el parser funciona, se amplia historico.

## Resultado de la primera descarga

Se descargo la muestra 2024 de perfiles y agregacion, mas documentacion tecnica y organos de
contratacion. El resultado esta documentado en `docs/RESULTADO_DESCARGA_PLACE_2024.md`.

La conclusion practica es que PLACE aporta mucho detalle, pero tambien mucho volumen: el ZIP de
perfiles 2024 pesa 1,79 GB comprimido y contiene unos 19 GB descomprimidos. Por tanto, la
estrategia correcta es parser en streaming y filtrado temprano por CPV 71.

## Resultado de procesamiento 31/05/2026

- El parser PLACE ya aplica filtrado temprano por CPV 71 sobre bloques Atom `entry`.
- `profiles` 2024 se proceso completo:
  - 633.995 entradas inspeccionadas.
  - 49.918 candidatas CPV 71.
  - 12.611 registros deduplicados CPV 71 cuando se ejecuto como fuente aislada.
- `aggregation` 2024 se proceso completo:
  - 242.265 entradas inspeccionadas.
  - 23.606 candidatas CPV 71.
  - 6.359 registros deduplicados CPV 71 cuando se ejecuto como fuente aislada.
- `run-agent1` usa ambos ZIPs y materializa:
  - `data/processed/contracts_place.parquet`
  - `data/processed/contracts_place_cpv71.parquet`
  - `data/processed/contracts_place_quality.json`
- El cuello de botella ya no es el parseo PLACE en cada sesion; `run-agent1` reutiliza cache salvo `--force-rebuild`.
