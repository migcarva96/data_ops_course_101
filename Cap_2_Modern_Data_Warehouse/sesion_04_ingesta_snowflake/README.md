# Sesión 4 — ELT hacia Snowflake

**Capítulo:** 2 — Modern Data Warehouse
**Fecha:** sábado **15/08/2026** · 08:00–11:00 · Aula **34-302**
**Tipo:** contenido
**Stack:** Snowflake · Python gestionado con `uv` · Neon.tech como fuente

---

## Objetivo

Aprovisionar un Data Warehouse en Snowflake y construir el primer proceso **ELT**:
conectar Neon con Snowflake vía Python, extraer las tablas de Parch & Posey desde la
branch `dev`, y cargarlas sin transformar en una capa `RAW`.

### Objetivos específicos

1. Entender la diferencia entre **OLTP y OLAP**, y por qué separar cargas transaccionales
   de cargas analíticas es una decisión de arquitectura, no una preferencia.
2. Entender **ELT vs. ETL** y por qué el patrón moderno transforma *dentro* del warehouse.
3. Aprovisionar Snowflake como código: warehouse, base de datos, schema `RAW` y un rol de
   servicio de mínimo privilegio — nunca `ACCOUNTADMIN`.
4. Construir un script de extracción con `uv`, que lea de Neon y cargue en Snowflake con
   `write_pandas`.
5. Vivir un incidente real de la industria — **schema drift** entre el sistema fuente y el
   Data Warehouse — y resolverlo con el mismo criterio de "detectar antes de fallar" que
   ya aplicamos con Flyway en la Sesión 2.

---

## Prerrequisitos

### Haber completado el Momento 1

Esta sesión asume que tu branch `dev` de Neon tiene el estado base de la Sesión 1 **y**
las migraciones de la Sesión 2 aplicadas (índice compuesto, `web_events.utm_source`,
`fn_calculate_discount`, `sp_process_order`). Verifícalo:

```bash
cd ../../Cap_1_Fundamentos_DataOps/sesion_01_estado_base/codigo
uv run inyeccion_semilla.py --solo-verificar
```

### Cuenta de Snowflake

Crea una cuenta de trial **antes** de esta sesión: https://signup.snowflake.com

- **30 días** o **USD 400** en crédito, lo que se agote primero. No pide tarjeta de
  crédito.
- **Región y edición no se pueden cambiar después de creada la cuenta.** Cualquier región
  cercana y la edición *Standard* bastan — no necesitas *Enterprise* para este curso.

> ⚠️ **Cuida la fecha de activación.** El Momento 2 se sustenta el 22/08/2026. Si activas
> el trial el 15/08, tienes margen de sobra; si lo activas antes, corres el riesgo de que
> expire antes de la sustentación.

### Herramientas locales

```bash
uv --version   # gestor de proyectos Python del curso
git pull       # repositorio actualizado
```

> 🪟 **En Windows**, todos los comandos van en **Git Bash**, no en PowerShell ni CMD. Ver
> [WINDOWS_USERS.md](../../WINDOWS_USERS.md).

---

## Contenido de la carpeta

| Ruta | Qué es |
|---|---|
| [presentacion/presentacion.md](presentacion/presentacion.md) | Presentación en Marp (15 slides) |
| [codigo/setup_snowflake.sql](codigo/setup_snowflake.sql) | Aprovisionamiento: warehouse, base de datos, schema `RAW`, rol de servicio |
| [codigo/elt_postgres_to_snowflake.py](codigo/elt_postgres_to_snowflake.py) | Script de extracción y carga |
| [codigo/.env.example](codigo/.env.example) | Plantilla de variables de entorno — cópiala a `.env` |
| [codigo/pyproject.toml](codigo/pyproject.toml) | Proyecto `uv` y sus dependencias |

---

## Guion del taller

### 1. Aprovisionar Snowflake

En Snowsight → **Worksheets**, pega y ejecuta
[`setup_snowflake.sql`](codigo/setup_snowflake.sql). Crea:

- Warehouse `WH_DATAOPS` (XSMALL, auto-suspend a 60s).
- Base de datos `PARCH_AND_POSEY` y schema `RAW`.
- Rol de servicio `DATAOPS_LOADER`, con permisos mínimos — el script Python nunca se
  conecta como `ACCOUNTADMIN`.

No olvides descomentar y editar la línea `GRANT ROLE DATAOPS_LOADER TO USER <tu_usuario>;`
con tu usuario real.

### 2. Proyecto Python

```bash
cd Cap_2_Modern_Data_Warehouse/sesion_04_ingesta_snowflake/codigo
uv sync
cp .env.example .env
```

Completa en `.env`: `NEON_DEV_DATABASE_URL` (la misma de siempre) y las cuatro variables
`SNOWFLAKE_*` — el identificador de cuenta está en Snowsight → tu perfil → *Account*.

### 3. Primera carga

```bash
uv run elt_postgres_to_snowflake.py --solo-verificar   # sin escribir nada
uv run elt_postgres_to_snowflake.py                    # carga las 5 tablas
```

Salida esperada para cada tabla: filas extraídas de Neon, columnas normalizadas a
mayúscula, y confirmación de la carga en `RAW`.

### 4. Provocar schema drift (a propósito)

Simula lo que haría el equipo de backend sin avisarte — desde `psql` (vía Docker, sin
instalar nada) o el SQL Editor de Neon sobre `dev`:

```bash
CONN="$(grep '^NEON_DEV_DATABASE_URL=' .env | cut -d= -f2-)"
docker run --rm postgres:16-alpine psql "$CONN" \
  -c "ALTER TABLE orders ADD COLUMN discount_code VARCHAR(20);"
```

Vuelve a correr el ELT:

```bash
uv run elt_postgres_to_snowflake.py
```

El script se detiene **antes** de tocar Snowflake, con un mensaje que incluye el DDL
exacto para corregirlo — no con el `invalid identifier` críptico que vería un pipeline sin
esta verificación.

### 5. Roll forward en Snowflake

Copia el `ALTER TABLE` que imprimió el script, pégalo en un Worksheet de Snowsight, y
vuelve a correr el ELT — sin tocar una línea de código:

```bash
uv run elt_postgres_to_snowflake.py
```

---

## Decisiones de diseño del script

Vale la pena leer [`elt_postgres_to_snowflake.py`](codigo/elt_postgres_to_snowflake.py)
completo. Los puntos que se discuten en clase:

| Decisión | Por qué |
|---|---|
| **`SELECT *`** en la extracción, no una lista de columnas | La extracción no debe saber nada del negocio. También es lo que permite que el script "sobreviva" a un `ALTER TABLE` en el origen sin cambiar código. |
| **Normalizar columnas a mayúscula** al extraer | Snowflake guarda identificadores sin comillas en mayúscula. Comparar minúscula contra mayúscula haría creer que todo es drift. |
| **Detectar drift antes de llamar a `write_pandas`** | Fallar con un mensaje propio y el DDL ya redactado es mejor que dejar que Snowflake falle tres capas más abajo con "invalid identifier". |
| **Generar el DDL, no ejecutarlo solo** | Alterar un schema de producción sin que nadie lo revise es su propio riesgo — el mismo principio del rol de servicio sin privilegios de administración. |
| **Rol `DATAOPS_LOADER`, nunca `ACCOUNTADMIN`** | Un error en el script (o una credencial filtrada) con ese rol es un incidente de cuenta completa, no de una tabla. |
| **`pandas>=2.1.2,<3.0.0`** fijado explícitamente | `write_pandas` necesita el extra `snowflake-connector-python[pandas]` (trae `pyarrow`), y ese extra exige `pandas<3.0.0`. Sin el límite superior, `uv add` instala la última pandas (3.x), incompatible, y el conector falla en tiempo de ejecución con `MissingDependencyError`. |

---

## Relación con el Momento Evaluativo 2

Lo que se construye hoy es el punto de partida del
[Momento 2 — Cloud DW e Ingesta](../../evaluaciones/momento_2_cloud_dw.md) (30 % de la
nota final, se sustenta el **sábado 22/08/2026**).

El pipeline de hoy corre sobre **Parch & Posey**, como ejemplo compartido de clase. Para
tu entregable evaluativo, repites este mismo patrón —aprovisionamiento como código, ELT
con `uv`, manejo de schema drift— sobre el **proyecto propio** de tu equipo, el mismo
dominio de negocio y modelo transaccional del Momento 1.

Lo que todavía falta para el entregable completo lo cubre la Sesión 5: ingesta de datos
semi-estructurados (no todo en tu dominio va a venir en forma relacional), orquestación
nativa con Tasks, y gobernanza sobre lo que resulte sensible.

---

## Renderizar la presentación

```bash
# desde la raíz del repositorio
npx @marp-team/marp-cli@latest \
  Cap_2_Modern_Data_Warehouse/sesion_04_ingesta_snowflake/presentacion/presentacion.md --pdf
```

---

## Próxima sesión

**[Sesión 5 — External Stages, JSON y gobernanza](../sesion_05_external_stages_json/)** ·
21/08/2026. Hoy resolvimos datos relacionales con schema fijo. La Sesión 5 cambia de
paradigma: datos semi-estructurados (JSON de mercadeo) que aterrizan en un `VARIANT` sin
esquema previo, se aplanan con `LATERAL FLATTEN`, se orquestan con Tasks nativas de
Snowflake, y se protegen con RBAC y Dynamic Data Masking sobre la PII.
