# Sesión 5 — External Stages, JSON y Gobernanza

**Capítulo:** 2 — Modern Data Warehouse
**Fecha:** viernes **21/08/2026** · 18:00–21:00 · Aula **35-203**
**Tipo:** contenido
**Stack:** Snowflake SQL puro — External Stages (S3), `VARIANT`, `LATERAL FLATTEN`, Tasks, RBAC, Dynamic Data Masking

---

## Objetivo

Ingerir JSON semi-estructurado desde un bucket S3 sin definir su esquema de antemano
(**schema-on-read**), aplanarlo con `LATERAL FLATTEN`, orquestar el proceso completo con
**Tasks** nativas de Snowflake (sin Airflow ni scripts externos), y proteger la PII
resultante con **RBAC** y **Dynamic Data Masking**.

Todo el taller se ejecuta directamente en Snowsight — **no hay Python en esta sesión.**

### Objetivos específicos

1. Distinguir **schema-on-write** (Sesión 4) de **schema-on-read** (hoy), y cuándo cada
   uno es la herramienta correcta.
2. Crear un **External Stage** apuntando a un bucket S3, y entender qué lo diferencia de
   un Internal Stage.
3. Cargar JSON en una columna `VARIANT` y consultarlo con notación de punto y
   `LATERAL FLATTEN`.
4. Construir un **DAG de dos tareas** (root + child) con Snowflake Tasks, y administrar su
   ciclo de vida completo: activar, ejecutar, depurar, apagar, reprogramar.
5. Aplicar **RBAC** de negocio (tres roles con necesidades distintas) y una
   **Masking Policy** que cambia lo que cada rol ve del mismo dato.

---

## Prerrequisitos

### De la Sesión 4

- Warehouse `WH_DATAOPS` y base de datos `PARCH_AND_POSEY` ya creados.
- Rol `DATAOPS_LOADER` con tu usuario asignado.

### 🔴 Bucket S3 público — lo hace el docente, una sola vez

Los tres archivos de [`data/marketing_leads_*.json`](../../data/) deben estar disponibles
en `s3://data-ops-course-marketing-leads-2026/` con **lectura pública anónima** — sin esto,
el Paso A del taller no tiene qué explorar. Ver el detalle exacto (comandos AWS CLI y
política de bucket) en [`TESTING_PLAN_E2E.md`](../../TESTING_PLAN_E2E.md), sección 5.

> ⚠️ Un bucket público de solo lectura es aceptable aquí porque el dataset es sintético y
> de curso. **Nunca** se hace esto con datos reales de una empresa — para eso existe
> `STORAGE INTEGRATION` con rol IAM, mencionado pero no implementado hoy (fuera de alcance
> deliberado, para no convertir la sesión en un curso de IAM de AWS).

### 🔴 Snowflake Enterprise Edition — solo para la Parte F (Masking)

Verificado contra la cuenta real de este curso: **`CREATE MASKING POLICY` requiere
Enterprise Edition o superior.** La cuenta creada en la Sesión 4 es Standard (siguiendo la
recomendación de esa sesión, que no anticipaba esta necesidad).

Verifica tu edición **antes de la clase**:

```sql
-- conectado con el rol ORGADMIN
SHOW ACCOUNTS;
-- columna EDITION: debe decir ENTERPRISE (o BUSINESS_CRITICAL)
```

Si tu cuenta es Standard, el resto del taller (Partes A–E) funciona igual — solo la
demostración en vivo de la Parte F queda bloqueada. Ver alternativas en
[`TESTING_PLAN_E2E.md`](../../TESTING_PLAN_E2E.md), sección 5.4.

### Herramientas

Ninguna nueva — todo corre en Snowsight, en el navegador.

---

## Contenido de la carpeta

| Ruta | Qué es |
|---|---|
| [presentacion/presentacion.md](presentacion/presentacion.md) | Presentación en Marp (20 slides) |
| `codigo/01_setup_stage_and_raw.sql` | File Format, External Stage, tabla `RAW_LEADS`, primer `COPY INTO` |
| `codigo/02_flatten_query_exploration.sql` | Notación de punto, `LATERAL FLATTEN`, tabla `STG_LEADS_FLATTENED` |
| `codigo/03_tasks_and_dag_management.sql` | DAG de dos tareas, `EXECUTE TASK`, `TASK_HISTORY`, administración |
| `codigo/04_rbac_and_masking.sql` | Tres roles, una Masking Policy, demo de visibilidad diferenciada |

> 🚧 **Los 4 scripts se entregan uno por uno, antes de cada bloque del taller** — no están
> en el repositorio todavía a propósito. Ya están escritos y verificados contra Snowflake
> real; se revelan progresivamente en clase en vez de estar disponibles desde el día uno.

No hay carpeta `.env` ni proyecto `uv` en esta sesión — es SQL puro, sin credenciales de
Python que gestionar.

---

## Guion del taller

Ejecutar los 4 scripts en Snowsight, en orden, cada uno completo antes de pasar al
siguiente.

### Paso A–B · `01_setup_stage_and_raw.sql`

Crea el File Format (`STRIP_OUTER_ARRAY = TRUE`, porque cada archivo es un array JSON),
el External Stage, explora el bucket con `LIST` y `SELECT $1` sin cargar nada, y finalmente
crea `RAW_LEADS` y ejecuta el primer `COPY INTO`.

### Paso C–D · `02_flatten_query_exploration.sql`

Notación de punto para los campos planos de cada campaña; `LATERAL FLATTEN` para
desenrollar el array `high_profile_contacts` en una fila por contacto. Cierra
materializando el resultado en `STG_LEADS_FLATTENED`.

### Paso E · `03_tasks_and_dag_management.sql`

Otorga `EXECUTE TASK`, crea el DAG (`TASK_INGEST_S3` → `TASK_FLATTEN_LEADS`), lo activa con
`SYSTEM$TASK_DEPENDENTS_ENABLE`, lo dispara manualmente, consulta `TASK_HISTORY`, y lo
apaga — en ese orden, porque el orden de apagado **no es libre** (ver más abajo).

### Paso F · `04_rbac_and_masking.sql`

Crea `ROLE_DATA_ENGINEER`, `ROLE_DATA_ANALYST`, `ROLE_BUSINESS_MANAGER`; antes de aplicar
la Masking Policy, confirma que los tres ven el mismo teléfono. Luego crea `mask_phone` y
repite la consulta con cada rol activo — el mismo `SELECT`, tres resultados distintos.

**Antes de reemplazar `<TU_USUARIO>`** en los `GRANT ROLE ... TO USER`, edítalo con tu
usuario real de Snowflake.

---

## Hallazgos verificados contra Snowflake real

Todo lo que sigue se comprobó ejecutando los 4 scripts contra la cuenta real de este curso
(sustituyendo temporalmente el stage externo por uno interno con los mismos 3 archivos,
mientras el bucket público se termina de configurar) — no son advertencias teóricas.

| Hallazgo | Detalle |
|---|---|
| Orden de propiedades en `CREATE TASK` | `COMMENT` debe declararse **antes** de `AFTER`, no después — si no, error de sintaxis. |
| Apagar un DAG activo | `ALTER TASK <hija> SUSPEND` (o `ALTER TASK <raíz> SET SCHEDULE`) falla con el error 091421 mientras la raíz siga `started`. Hay que suspender la raíz primero, siempre. |
| Activar un DAG | El orden **no** está restringido de la misma forma — `SYSTEM$TASK_DEPENDENTS_ENABLE('<raíz>')` lo resuelve de un solo golpe de todas formas. |
| `EXECUTE TASK` | Privilegio de **cuenta**, no de objeto. Ser dueño de la task no basta — hace falta `GRANT EXECUTE TASK ON ACCOUNT`. |
| `MASKING POLICY` | Falla con `000002 (0A000): Unsupported feature` en Snowflake Standard Edition. Todo el resto del script (roles, grants, `USE ROLE`) funciona sin Enterprise. |
| `LATERAL FLATTEN` sobre datos reales | Los contactos del export del 14/08 no tienen `social_media_handle`; los del 21/08 y 28/08 sí. La consulta no falla — la columna sale `NULL` donde falta. |

---

## Relación con el Momento Evaluativo 2

El pipeline de hoy corre sobre **Parch & Posey** y un dataset de mercadeo de ejemplo, como
material de clase. El [Momento 2 — Cloud DW e Ingesta](../../evaluaciones/momento_2_cloud_dw.md)
(30 % de la nota final, se sustenta el **sábado 22/08/2026**) exige repetir **el mismo
patrón de las Sesiones 4 y 5** —arquitectura como código, extracción relacional con `uv`,
ingesta de al menos una fuente semi-estructurada vía External Stage, orquestación con
Tasks, y gobernanza con RBAC y Masking— sobre el **proyecto propio** de cada equipo, no
sobre Parch & Posey. Ver el enunciado completo para el detalle exacto de cada criterio.

---

## Renderizar la presentación

```bash
# desde la raíz del repositorio
npx @marp-team/marp-cli@latest \
  Cap_2_Modern_Data_Warehouse/sesion_05_external_stages_json/presentacion/presentacion.md --pdf
```

---

## Próxima sesión

**[Sesión 6 — Sustentación Momento 2](../sesion_06_sustentacion_momento2/)** · 22/08/2026.
Demo en vivo del pipeline completo de tu equipo: extracción relacional (Sesión 4) e ingesta
gobernada, sobre el proyecto propio definido en el Momento 1.
