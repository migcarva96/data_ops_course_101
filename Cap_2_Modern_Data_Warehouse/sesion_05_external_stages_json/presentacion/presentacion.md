---
marp: true
theme: dataops
paginate: true
footer: 'SI6010-5979 · Tendencias emergentes en desarrollo de software · Sesión 5'
title: 'Sesión 5: External Stages, JSON y Gobernanza'
author: 'Pos ST1707 — EAFIT'
lang: es
---

<!-- _class: portada -->

<div class="kicker">Capítulo 2 · Modern Data Warehouse</div>

# Sesión 5: External Stages, JSON y Gobernanza

<div class="subtitulo">
No todo dato nace en una tabla. Snowflake también sabe qué hacer cuando no.
</div>

<div class="meta">

**Viernes 21/08/2026** · 18:00–21:00 · Aula 35-203
**Stack:** Snowflake SQL puro — External Stages (S3), `VARIANT`, `LATERAL FLATTEN`, Tasks, RBAC, Dynamic Data Masking

**Objetivo de la sesión** — Ingerir JSON semi-estructurado desde S3 sin definir su esquema de antemano, aplanarlo, orquestar el proceso con Tasks nativas de Snowflake, y proteger la PII resultante con RBAC y Data Masking.

</div>

---

## Schema-on-Write vs. Schema-on-Read

<div class="columnas">
<div>

En la Sesión 4 practicamos **schema-on-write**: antes de que entre un solo byte, declaras columnas y tipos (`CREATE TABLE orders (...)`). Si la fuente cambia, el destino debe cambiar primero — es la disciplina que aprendiste con el schema drift.

**Schema-on-read** invierte el orden: los datos entran tal cual llegan, sin que nadie declare su forma. La estructura se interpreta **cuando alguien consulta**, no cuando el dato aterriza.

Ninguno de los dos es "mejor" en abstracto — resuelven problemas distintos.

</div>
<div>

| | Schema-on-Write | Schema-on-Read |
|---|---|---|
| Se declara | Antes de cargar | Al consultar |
| Fuente | Relacional, estable | JSON/semi-estructurado, cambiante |
| Cambio de forma | `ALTER TABLE` | Nada — el campo nuevo ya está ahí |
| Ejemplo de hoy | Sesión 4 (Neon → RAW) | Sesión 5 (S3 → `VARIANT`) |

<div class="facts">

### Facts

- Mercadeo cambia su export cada campaña — schema-on-write aquí sería un `ALTER TABLE` semanal.

</div>
</div>
</div>

---

## External Stages: Snowflake apuntando fuera de sí mismo

<div class="columnas estrecha-izquierda">
<div>

Un **Internal Stage** vive dentro del storage de Snowflake — subes el archivo con `PUT` y ya es de Snowflake. Un **External Stage** es distinto: es una referencia a un bucket de object storage ajeno (S3, Azure Blob, GCS). Los datos **nunca se mueven** hasta que algo los pide explícitamente.

```sql
CREATE STAGE stg_marketing_leads_s3
  URL = 's3://.../'
  FILE_FORMAT = ff_marketing_json;
```

`LIST @stage` pregunta qué hay, sin traer nada. `SELECT $1 FROM @stage` sí lee el contenido — sin cargarlo a ninguna tabla todavía.

</div>
<div>

<div class="diagrama">
 Snowflake                    S3 (ajeno)
 ┌──────────────┐            ┌──────────┐
 │ External     │  URL  ───▶ │  bucket  │
 │ Stage        │            │  público │
 │ (referencia) │ ◀── LIST   │          │
 └──────────────┘            └──────────┘
      │ COPY INTO
      ▼
 ┌──────────────┐
 │  RAW_LEADS   │  ← aquí sí se mueve el dato
 └──────────────┘
</div>

<div class="facts">

### Facts

- Este bucket es de **solo lectura pública** — sin credenciales en ningún script. En datos reales de empresa, se usa un `STORAGE INTEGRATION` con rol IAM.
- Un `External Stage` es barato: es metadato, no una copia de los datos.

</div>
</div>
</div>

---

## El tipo `VARIANT`

<div class="columnas">
<div>

`VARIANT` es el tipo de Snowflake que guarda **cualquier estructura JSON** — objetos, arrays, anidamiento arbitrario — en una sola columna, indexada internamente para consultarse casi tan rápido como una columna nativa.

No es texto: Snowflake parsea el JSON al cargarlo y lo guarda en un formato binario columnar propio. Por eso `raw_data:campaign_id` no hace un parseo de texto en cada consulta — ya está estructurado por dentro.

La notación de punto (`:`) navega el árbol; `::TIPO` convierte el resultado (siempre `VARIANT`) a un tipo SQL usable.

</div>
<div>

```json
{
  "campaign_id": "CMP-2026-08A",
  "budget_spent_usd": 1500.5,
  "high_profile_contacts": [
    {"name": "Evelyn Harper", "phone": "..."}
  ]
}
```

```sql
SELECT raw_data:campaign_id::STRING,
       raw_data:budget_spent_usd::FLOAT
FROM RAW_LEADS;
```

<div class="facts">

### Facts

- Sin `::TIPO`, hasta un número sale `VARIANT` — no se suma ni compara.
- Preguntar por una clave que no existe no es error: da `NULL`.

</div>
</div>
</div>

---

## `LATERAL FLATTEN`: el JOIN implícito contra tu propio array

<div class="columnas estrecha-izquierda">
<div>

Imagina cada fila como una **factura**, y un array anidado (`high_profile_contacts`) como sus **ítems**. `LATERAL FLATTEN` es, en esencia, un `JOIN` de la factura contra cada uno de sus propios ítems: multiplica la fila padre una vez por cada elemento del array.

Una campaña con 2 contactos se convierte en 2 filas de salida; con 0 contactos, en 0 filas.

`LATERAL` es lo que permite que `FLATTEN` "vea" la columna de la fila que se está procesando — un `FLATTEN` normal no podría referenciar `raw_data` de esa forma.

</div>
<div>

<div class="diagrama">
 RAW_LEADS (1 fila)
 ┌────────────────────────┐
 │ campaign: CMP-A         │
 │ contacts: [A, B]        │
 └────────────────────────┘
           │ LATERAL FLATTEN
           ▼
 ┌──────────────┬──────────┐
 │ campaign: A  │ contact: A│
 │ campaign: A  │ contact: B│
 └──────────────┴──────────┘
   2 filas, no 1
</div>

<div class="facts">

### Facts

- `FLATTEN(input => raw_data:high_profile_contacts)` expone el array como filas; `value:campo` navega cada elemento.
- Un contacto sin `social_media_handle` no rompe nada: sale `NULL`.

</div>
</div>
</div>

---

## Snowflake Tasks: orquestación sin salir de SQL

<div class="columnas">
<div>

Una **Task** es una sentencia SQL (o un `CALL` a un procedure) que Snowflake ejecuta según un `SCHEDULE` — sin Airflow, sin cron externo, sin infraestructura que mantener aparte.

Encadenar tareas con `AFTER` construye un **DAG**: la tarea hija no tiene reloj propio, se dispara cuando su predecesora termina **con éxito**. Eso es una dependencia lógica, no una coincidencia de horarios.

Hoy: `TASK_INGEST_S3` (raíz, con `SCHEDULE`) → `TASK_FLATTEN_LEADS` (hija, con `AFTER`).

</div>
<div>

<div class="diagrama">
 TASK_INGEST_S3          ← raíz
   SCHEDULE = CRON
   COPY INTO RAW_LEADS
        │
        │ AFTER (si tuvo éxito)
        ▼
 TASK_FLATTEN_LEADS      ← hija
   INSERT INTO
   STG_LEADS_FLATTENED
</div>

<div class="facts">

### Facts

- Una task nace **suspendida**, siempre. Crear el objeto y activarlo son dos decisiones distintas — a propósito.
- El warehouse de una task se cobra igual que cualquier otro: por segundo de cómputo activo.

</div>
</div>
</div>

---

## Task Management: lo que nadie te dice la primera vez

<div class="columnas">
<div>

**Activar un DAG completo de una vez:**
```sql
SELECT SYSTEM$TASK_DEPENDENTS_ENABLE(
  'TASK_INGEST_S3');
```

**Disparar sin esperar el CRON:**
```sql
EXECUTE TASK TASK_INGEST_S3;
```

**Ver qué pasó:**
```sql
SELECT name, state, error_message
FROM TABLE(
  INFORMATION_SCHEMA.TASK_HISTORY())
ORDER BY scheduled_time DESC;
```

</div>
<div>

<div class="aviso">

**El privilegio oculto.** `EXECUTE TASK` es un privilegio de **cuenta**, no de objeto — ser dueño de la task no basta:
```sql
GRANT EXECUTE TASK ON ACCOUNT
  TO ROLE DATAOPS_LOADER;
```

</div>

<div class="facts">

### Facts

- Verificado contra la cuenta real de este curso: **para suspender o alterar cualquier task de un DAG activo, primero hay que suspender la raíz.** Intentarlo al revés falla con el error 091421.
- `TASK_HISTORY` es tu primera parada para depurar — antes que revisar logs de aplicación que no existen aquí.

</div>
</div>
</div>

---

## RBAC: los roles gobiernan, no las personas

<div class="columnas">
<div>

En Snowflake, los privilegios nunca se otorgan a un usuario directamente — se otorgan a un **rol**, y el rol se asigna al usuario. La misma persona puede operar hoy como `ROLE_DATA_ENGINEER` y mañana como `ROLE_BUSINESS_MANAGER`, con visibilidad distinta según cuál tenga activo.

Por defecto, un rol nuevo no ve absolutamente nada — ni siquiera puede usar un warehouse. Cada `GRANT` es una puerta que se abre a propósito; el punto de partida es "todo cerrado".

</div>
<div>

<div class="diagrama">
 USUARIO davillanueva
   ├── ROLE_DATA_ENGINEER    (ve todo)
   ├── ROLE_DATA_ANALYST     (ve parcial)
   └── ROLE_BUSINESS_MANAGER (ve enmascarado)

 USE ROLE X;  ← decide qué ve AHORA
</div>

<div class="facts">

### Facts

- `GRANT ROLE X TO USER Y` asigna el rol; `USE ROLE X` lo activa en la sesión actual.
- Tres roles hoy: ingeniero (opera el pipeline), analista (contexto parcial), gerente de negocio (nunca ve PII cruda).

</div>
</div>
</div>

---

## Dynamic Data Masking: la protección vive con el dato

<div class="columnas">
<div>

Una **Masking Policy** es una función que Snowflake evalúa **al vuelo**, dentro del plan de ejecución de cada query — no existe una segunda copia enmascarada de la tabla en ningún lado. El mismo `SELECT phone FROM tabla` devuelve algo distinto según qué rol esté activo.

La política se ata a la columna una sola vez (`ALTER TABLE ... SET MASKING POLICY`). Desde ese momento, **cualquier** consulta futura —tuya, de un dashboard de BI, de un notebook que ni existe todavía— hereda la protección automáticamente.

</div>
<div>

```sql
CREATE MASKING POLICY mask_phone
  AS (val STRING) RETURNS STRING ->
  CASE
    WHEN CURRENT_ROLE() =
      'ROLE_DATA_ENGINEER' THEN val
    WHEN CURRENT_ROLE() =
      'ROLE_DATA_ANALYST'
      THEN LEFT(val,6)||'-****'
    ELSE '***-***-****'
  END;
```

<div class="aviso">

**Requiere Snowflake Enterprise Edition o superior.** Verificado en la cuenta de este curso (Standard): `CREATE MASKING POLICY` falla con *"Unsupported feature"*. Ver checklist.

</div>
</div>
</div>

---

## Checklist pre-taller

<div class="columnas">
<div>

### De sesiones anteriores

<ul class="check">
<li>Warehouse <code>WH_DATAOPS</code> y base de datos <code>PARCH_AND_POSEY</code> de la Sesión 4, ya creados.</li>
<li>Rol <code>DATAOPS_LOADER</code> con tu usuario asignado.</li>
</ul>

### Nuevo en esta sesión

<ul class="check">
<li>Los 3 archivos de <code>data/marketing_leads_*.json</code> subidos a un bucket S3 <strong>de lectura pública</strong> — lo hace el docente, una sola vez.</li>
</ul>

</div>
<div>

<div class="aviso">

**Verifica la edición de tu cuenta ANTES de la Parte D (masking).**

```sql
-- como rol ORGADMIN
SHOW ACCOUNTS;
-- columna EDITION: debe decir
-- ENTERPRISE o superior
```

Si tu cuenta es **Standard** (como la del trial por defecto), la Parte D no correrá en vivo. Sigue el resto del taller igual — es una limitación real de licenciamiento, no un error tuyo, y es en sí misma una lección de gobernanza de proveedor.

</div>
</div>
</div>

---

<!-- _class: seccion -->

<div class="kicker">Parte práctica</div>

## Taller: de un bucket público a datos gobernados

---

## Paso A · Explorar antes de cargar

<div class="columnas estrecha-izquierda">
<div>

`01_setup_stage_and_raw.sql`

```sql
CREATE FILE FORMAT ff_marketing_json
  TYPE = JSON
  STRIP_OUTER_ARRAY = TRUE;

CREATE STAGE stg_marketing_leads_s3
  URL = 's3://.../'
  FILE_FORMAT = ff_marketing_json;

LIST @stg_marketing_leads_s3;

SELECT $1
FROM @stg_marketing_leads_s3
  (FILE_FORMAT => ff_marketing_json)
LIMIT 5;
```

</div>
<div>

<div class="facts">

### Facts

- `STRIP_OUTER_ARRAY = TRUE` es obligatorio aquí: cada archivo es `[ {...}, {...} ]`. Sin esa opción, todo el archivo cargaría como **una sola fila**.
- `LIST` y el `SELECT` directo del stage no mueven nada hacia una tabla — son gratis, en el sentido de que no consumen storage de Snowflake.
- Verificado contra los 3 archivos reales del curso: 5 campañas totales, repartidas en 3 exports semanales.

</div>
</div>
</div>

---

## Paso B · `RAW_LEADS` — la tabla de una sola columna

<div class="columnas">
<div>

```sql
CREATE TABLE RAW_LEADS (
    raw_data       VARIANT,
    _stg_file_name STRING,
    _stg_loaded_at TIMESTAMP_NTZ
      DEFAULT CURRENT_TIMESTAMP()
);

COPY INTO RAW_LEADS
  (raw_data, _stg_file_name,
   _stg_loaded_at)
FROM (
    SELECT $1, METADATA$FILENAME,
           CURRENT_TIMESTAMP()
    FROM @stg_marketing_leads_s3
)
FILE_FORMAT =
  (FORMAT_NAME = ff_marketing_json)
ON_ERROR = ABORT_STATEMENT;
```

</div>
<div>

```text
COPY INTO RAW_LEADS ...

marketing_leads_20260814.json.gz
  LOADED  2 filas
marketing_leads_20260821.json.gz
  LOADED  1 fila
marketing_leads_20260828.json.gz
  LOADED  2 filas

SELECT COUNT(*) FROM RAW_LEADS;
  → 5
```

<div class="facts">

### Facts

- `METADATA$FILENAME` guarda de qué archivo salió cada fila — trazabilidad sin esfuerzo extra.
- Si mercadeo cambiara el formato del JSON mañana, esta tabla **no necesita ningún cambio**.

</div>
</div>
</div>

---

## Paso C · Notación de punto y `LATERAL FLATTEN`

<div class="columnas">
<div>

`02_flatten_query_exploration.sql`

```sql
SELECT
  raw_data:campaign_id::STRING,
  raw_data:budget_spent_usd::FLOAT,
  c.value:name::STRING,
  c.value:phone::STRING,
  c.value:social_media_handle::STRING
FROM RAW_LEADS,
     LATERAL FLATTEN(
       input => raw_data:
         high_profile_contacts) c;
```

</div>
<div>

```text
CMP-2026-08A | Evelyn Harper
  +1-555-0198 | NULL
CMP-2026-08A | Marcus Vance
  +1-555-0299 | NULL
CMP-2026-08B | Sarah Jenkins
  +1-555-0881 | @sjenkins_tech
```

<div class="facts">

### Facts

- Verificado con los datos reales: los contactos del primer export (14/08) no tienen `social_media_handle` — sale `NULL`, la query no falla.
- 5 campañas → 6 filas de contacto (una campaña trae 2 contactos).

</div>
</div>
</div>

---

## Paso D · Materializar `STG_LEADS_FLATTENED`

<div class="columnas estrecha-izquierda">
<div>

```sql
CREATE TABLE STG_LEADS_FLATTENED (
    campaign_id STRING,
    contact_name STRING,
    phone STRING,
    social_media_handle STRING,
    -- ...
);

INSERT INTO STG_LEADS_FLATTENED (...)
SELECT ...
FROM RAW_LEADS,
     LATERAL FLATTEN(
       input => raw_data:
         high_profile_contacts) c;
```

</div>
<div>

<div class="facts">

### Facts

- ¿Por qué no dejar esto como una vista? Porque cada consulta reescanearía y reaplanaría **todo** `RAW_LEADS` de nuevo — barato hoy, con 5 campañas; caro a escala.
- Esta tabla es la que va a proteger la Masking Policy más adelante.

</div>
</div>
</div>

---

## Paso E · El DAG — crear y activar

<div class="columnas">
<div>

`03_tasks_and_dag_management.sql`

```sql
GRANT EXECUTE TASK ON ACCOUNT
  TO ROLE DATAOPS_LOADER;

CREATE TASK TASK_INGEST_S3
  WAREHOUSE = WH_DATAOPS
  SCHEDULE = 'USING CRON 0 * * * *
    America/Bogota'
AS COPY INTO RAW_LEADS (...) FROM (...);

CREATE TASK TASK_FLATTEN_LEADS
  WAREHOUSE = WH_DATAOPS
  AFTER TASK_INGEST_S3
AS INSERT OVERWRITE INTO
     STG_LEADS_FLATTENED (...) SELECT ...;
```

</div>
<div>

```sql
SHOW TASKS;
-- ambas: suspended

SELECT SYSTEM$TASK_DEPENDENTS_ENABLE(
  'TASK_INGEST_S3');

SHOW TASKS;
-- ambas: started

EXECUTE TASK TASK_INGEST_S3;
```

<div class="facts">

### Facts

- Verificado en vivo: `TASK_INGEST_S3` corre, y al terminar con éxito dispara automáticamente `TASK_FLATTEN_LEADS` — sin ningún `SCHEDULE` propio en la hija.

</div>
</div>
</div>

---

## Paso E · Apagar el DAG (el orden importa, y al revés de lo esperado)

<div class="columnas estrecha-izquierda">
<div>

```sql
-- Esto FALLA si TASK_INGEST_S3
-- sigue activa:
ALTER TASK TASK_FLATTEN_LEADS SUSPEND;
-- ERROR 091421: Unable to update
-- graph ... root task is not
-- suspended.

-- Orden correcto: la RAÍZ primero
ALTER TASK TASK_INGEST_S3 SUSPEND;
ALTER TASK TASK_FLATTEN_LEADS SUSPEND;

-- Y solo ahora se puede reprogramar
ALTER TASK TASK_INGEST_S3
  SET SCHEDULE = 'USING CRON
    0 */6 * * * America/Bogota';
```

</div>
<div>

<div class="aviso">

**Esto no es teoría — es el error exacto que produjo la cuenta real de este curso.** Mientras la raíz de un DAG está activa, Snowflake bloquea cualquier cambio estructural sobre ella o sus tareas dependientes.

</div>

<div class="facts">

### Facts

- La regla completa: para **activar** un DAG, el orden no importa. Para **modificar o apagar** uno activo, la raíz va primero, siempre.

</div>
</div>
</div>

---

## Paso F · Tres roles, un teléfono

<div class="columnas">
<div>

`04_rbac_and_masking.sql`

```sql
CREATE ROLE ROLE_DATA_ENGINEER;
CREATE ROLE ROLE_DATA_ANALYST;
CREATE ROLE ROLE_BUSINESS_MANAGER;

GRANT USAGE ON WAREHOUSE WH_DATAOPS
  TO ROLE ROLE_DATA_ENGINEER;
-- (... USAGE en DB, schema,
--  SELECT en la tabla, x3 roles)

GRANT ROLE ROLE_DATA_ENGINEER
  TO USER <tu_usuario>;
-- (x3 roles)
```

</div>
<div>

<div class="facts">

### Facts

- Verificado: sin la Masking Policy activa, los tres roles ven el mismo teléfono completo — es exactamente el "antes" que motiva el resto del ejercicio.
- Un rol recién creado no ve nada hasta que se le otorga cada privilegio, uno por uno.

</div>
</div>
</div>

---

## Paso F · La máscara, en vivo

<div class="columnas">
<div>

```sql
CREATE MASKING POLICY mask_phone
  AS (val STRING) RETURNS STRING ->
  CASE
    WHEN CURRENT_ROLE() =
      'ROLE_DATA_ENGINEER' THEN val
    WHEN CURRENT_ROLE() =
      'ROLE_DATA_ANALYST'
      THEN LEFT(val,6) || '-****'
    ELSE '***-***-****'
  END;

ALTER TABLE STG_LEADS_FLATTENED
  MODIFY COLUMN phone
  SET MASKING POLICY mask_phone;
```

</div>
<div>

```sql
USE ROLE ROLE_DATA_ENGINEER;
SELECT phone FROM STG_LEADS_FLATTENED;
-- +1-555-0198  (completo)

USE ROLE ROLE_DATA_ANALYST;
SELECT phone FROM STG_LEADS_FLATTENED;
-- +1-555-****  (parcial)

USE ROLE ROLE_BUSINESS_MANAGER;
SELECT phone FROM STG_LEADS_FLATTENED;
-- ***-***-****  (nada)
```

<div class="aviso">

Mismo `SELECT`, tres resultados. La lógica vive en la política, no en quien pregunta.

</div>
</div>
</div>

---

<!-- _class: cierre -->

## Conclusiones

<div class="columnas">
<div>

### Lo que cambió hoy

- De declarar el schema antes (Sesión 4) a interpretarlo al leer — dos herramientas legítimas, no una evolución de la otra.
- Un DAG completo corriendo **dentro** de Snowflake, sin infraestructura externa.
- La PII protegida en el dato mismo, no en la disciplina de quien escribe cada query.

### Las reglas que te llevas

1. `VARIANT` + `FLATTEN` = flexibilidad hoy, costo después.
2. DAG activo: suspende la raíz primero, siempre.
3. Masking: cada consumidor nuevo hereda la regla.

</div>
<div>

<div class="aviso">

**Esto alimenta el Momento 2.** El bucket S3, el DAG y las políticas de esta sesión están sobre Parch & Posey, el ejemplo de clase. Para tu entregable, aplica el mismo patrón —si tu dominio propio tiene algún dato semi-estructurado o PII que proteger— sobre el proyecto de tu equipo.

</div>

### Próxima sesión

**22/08 · Sustentación Momento 2.** Demo en vivo de tu pipeline completo: extracción relacional, ingesta gobernada, y ahora también las decisiones de gobernanza que tomaste sobre tus propios datos.

</div>
</div>
