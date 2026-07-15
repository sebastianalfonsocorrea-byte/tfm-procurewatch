# Resultado de descarga PLACE/Hacienda 2024

Fecha de ejecucion local: 30/05/2026.

## Fuentes descargadas

| Fuente | Ruta local | Tamano |
|---|---|---:|
| Licitaciones perfiles PLACSP 2024 | `data/raw/place/profiles/licitacionesPerfilesContratanteCompleto3_2024.zip` | 1.792.750.583 bytes |
| Licitaciones agregacion 2024 | `data/raw/place/aggregation/PlataformasAgregadasSinMenores_2024.zip` | 127.929.554 bytes |
| Organos de contratacion | `data/raw/place/buyer_profiles/place_buyer_profiles.xlsx` | 1.688.667 bytes |
| Resumen de datos abiertos PLACE | `data/raw/reference_docs/DGPE_PLACSP_ResumenDatosAbiertos.pdf` | 339.902 bytes |
| Especificacion de sindicacion PLACE | `data/raw/reference_docs/especificacion-sindicacion.pdf` | 2.359.604 bytes |

## Hashes SHA-256

```text
licitacionesPerfilesContratanteCompleto3_2024.zip
2b0bff734c49a423cf34c1d152863963f0ce329f7d8d4b224fa62cd510d6ba43

PlataformasAgregadasSinMenores_2024.zip
73fe8927142466ae26d4d9f9767af72720b8efbee3e4b2ec5496b56f6263aac2
```

## Inspeccion de ZIP

| ZIP | Ficheros Atom/XML | Tamano descomprimido aproximado |
|---|---:|---:|
| Perfiles PLACSP 2024 | 1.302 | 19.028.532.766 bytes |
| Agregacion 2024 | 940 | 2.383.993.640 bytes |

## Decision tecnica

No se debe descomprimir todo el historico en disco. El parser PLACE debe leer los ZIP en streaming
y extraer solo los campos utiles:

- identificador de licitacion;
- URL/detail link;
- expediente;
- estado;
- fecha de actualizacion;
- organo de contratacion;
- NIF/DIR3/ID Plataforma del organo si aparece;
- objeto;
- tipo de contrato;
- procedimiento;
- CPV;
- valor estimado e importe de licitacion;
- resultado, fecha de adjudicacion, adjudicatario;
- numero de ofertas/licidadores si aparece;
- documentos/pliegos.

## Siguiente paso

Construir un parser incremental para `entry` Atom/XML:

```text
ZIP PLACE 2024
  -> iterar .atom sin extraer todo
  -> extraer campos minimos
  -> filtrar CPV 71
  -> deduplicar por id de licitacion usando la ultima actualizacion
  -> guardar data/processed/place_2024_cpv71.parquet
```

Despues cruzaremos con BOE:

```text
contracts_boe_cpv71.parquet
  + place_2024_cpv71.parquet
  + place_buyer_profiles.xlsx
  -> contraste de volumen, importes, organismos, adjudicatarios y documentos
```

## Resultado posterior 31/05/2026

El parser incremental ya esta implementado en `scr/procurewatch/data_sources/place_normalize.py`.

Resultados observados:

| ZIP | Entradas inspeccionadas | Candidatas CPV 71 | Deduplicadas CPV 71 |
|---|---:|---:|---:|
| Perfiles PLACSP 2024 | 633.995 | 49.918 | 12.611 |
| Agregacion 2024 | 242.265 | 23.606 | 6.359 |

La salida operativa consolidada de Agent1 queda en:

```text
data/processed/contracts_place.parquet
data/processed/contracts_place_cpv71.parquet
data/processed/contracts_place_quality.json
```

Nota: cuando se ejecutan ambos ZIPs juntos, la deduplicacion se realiza sobre el conjunto combinado y puede diferir de la suma simple de ejecuciones aisladas.
