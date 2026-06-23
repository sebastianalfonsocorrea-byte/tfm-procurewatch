# Resultado del primer pipeline BOE

Fecha de ejecucion local: 30/05/2026.

## Entrada

Archivo raw:

```text
data/raw/licitaciones_contrataciones_BOE_2014_2024-2(in).csv
```

Tamano: 72.082.897 bytes.

Hash SHA-256:

```text
b7f0aec55369091eaed0f37b7c51e0fdc6f06e87648289ae15d94add8d64a552
```

## Salidas generadas

```text
data/processed/contracts_boe.parquet
data/processed/contracts_boe_cpv71.parquet
data/processed/contracts_boe_cpv71_preview.csv
data/processed/data_quality_report.json
```

## Resultado de calidad

| Metrica | Valor |
|---|---:|
| Filas raw de datos | 97.155 |
| Filas parseadas | 96.801 |
| Errores de parseo | 354 |
| Tasa de exito | 99,64 % |
| Filas reparadas por columnas irregulares | 24.389 |
| Lineas con caracteres reemplazados por codificacion | 85 |
| Registros CPV 71 detectados | 8.097 |

## Lectura del resultado

El CSV raw no es un CSV limpio: combina comas, comillas y separadores `;` de relleno. Por eso se
implemento un parser especifico que:

- elimina relleno final de `;`;
- repara filas envueltas en comillas;
- reconstruye institucion, organismo y expediente antes de la fecha;
- identifica procedimiento y ambito geografico;
- repara importes europeos;
- extrae codigos CPV desde texto;
- separa el subconjunto CPV 71.

La tasa de exito es suficiente para avanzar a EDA, red flags y grafo inicial. Las 354 filas no
parseadas quedan registradas en `data_quality_report.json` para revisarlas si alguna afecta a los
casos finales seleccionados.

## Distribucion principal

Tipos de registro:

| Tipo | Filas |
|---|---:|
| Contratacion | 62.765 |
| Licitacion | 34.036 |

Procedimientos principales:

| Procedimiento | Filas |
|---|---:|
| Abierto | 81.077 |
| Negociado sin publicidad | 7.312 |
| No disponible | 5.371 |
| Negociado con publicidad | 2.078 |
| Restringido | 916 |

CPV 71:

| Tipo | Filas |
|---|---:|
| Contratacion | 4.452 |
| Licitacion | 3.645 |

## Siguiente paso

Construir el primer modulo de analisis sobre `contracts_boe_cpv71.parquet`:

1. EDA basico: volumen anual, importes, top organismos, top adjudicatarios.
2. Primeras red flags implementables con los campos existentes.
3. Dataset de salida `data/processed/red_flags_cpv71.parquet`.

## Actualizacion 31/05/2026

BOE queda integrado dentro de Agent1 junto con PLACE y OpenTender.

Artefactos actuales relacionados:

```text
data/processed/contracts_boe.parquet
data/processed/contracts_boe_cpv71.parquet
data/processed/data_quality_report.json
data/processed/agent1_run_report.json
data/processed/agent2_contracts_canonical.parquet
```

La siguiente tarea sobre BOE ya no es parseo base, sino mejorar su alineacion con PLACE/OpenTender en `contract_key_canon` y derivar primeras red flags desde el canonico Agent2.
