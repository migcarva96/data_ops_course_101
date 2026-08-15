---
marp: true
theme: dataops
paginate: true
footer: 'SI6010-5979 · Tendencias emergentes en desarrollo de software · Sesión 4'
title: 'Sesión 4: ELT hacia Snowflake'
author: 'Pos ST1707 — EAFIT'
lang: es
---

<!-- _class: portada -->

<div class="kicker">Capítulo 2 · Modern Data Warehouse</div>

# Sesión 4: ELT hacia Snowflake

<div class="subtitulo">
Neon es donde el negocio escribe. Snowflake es donde el negocio pregunta.
</div>

<div class="meta">

**Sábado 15/08/2026** · 08:00–11:00 · Aula 34-302
**Stack:** Snowflake · Python (gestionado con `uv`) · Neon.tech como fuente

**Objetivo de la sesión** — Aprovisionar un Data Warehouse en Snowflake y construir el primer proceso **ELT**: extraer las tablas de Parch & Posey desde Neon y cargarlas, sin transformar, en una capa `RAW`.

</div>

---

## OLTP vs. OLAP: dos trabajos distintos

<div class="columnas">
<div>

Neon está optimizado para **transacciones**: insertar una orden, actualizar una cuenta, una fila a la vez, muchísimas veces por segundo. Eso es **OLTP**.

Una pregunta como *"ventas totales por región y trimestre en los últimos tres años"* obliga a escanear millones de filas y agregarlas. Ejecutarla contra el sistema transaccional compite por los mismos recursos que necesita un cliente intentando pagar en ese instante.

**OLAP** existe para separar esas dos cargas: un motor optimizado para escanear y agregar volúmenes grandes, sin tocar el sistema que sostiene la operación diaria.

</div>
<div>

| | OLTP (Neon) | OLAP (Snowflake) |
|---|---|---|
| Operación típica | `INSERT`, `UPDATE` puntual | `SELECT` con `GROUP BY` masivo |
| Optimizado para | Filas individuales | Columnas, agregaciones |
| Lo usa | La aplicación | El analista, el dashboard |

<div class="facts">

### Facts

- Ejecutar analítica pesada sobre el OLTP **degrada la aplicación real** — el motivo de negocio más común para separar cargas.
- No es que uno sea "mejor": son dos herramientas para dos preguntas distintas.

</div>
</div>
</div>

---

## ELT, no ETL

<div class="columnas">
<div>

**ETL** clásico: Extraer → Transformar en un servidor intermedio → Cargar ya limpio.

**ELT**, el patrón moderno: Extraer → Cargar crudo → **Transformar dentro del Data Warehouse.**

¿Por qué invertir el orden? Porque Snowflake tiene un motor de cómputo muchísimo más grande que tu laptop. Transformar *después* de cargar es transformar con los recursos elásticos del warehouse — no con los tuyos.

También significa que **los datos crudos quedan guardados**: si una transformación falla, el original sigue ahí para reprocesar.

</div>
<div>

<div class="diagrama">
 ETL (clásico)
   Neon -E-> [transformar] -L-> DW
             (tu máquina, limitada)

 ELT (moderno)
   Neon -E-> DW.RAW -L, ya adentro-
             transformar ahí, con el
             cómputo de Snowflake
</div>

<div class="facts">

### Facts

- El Capítulo 3 (dbt) es la "T" de ELT — ocurre dentro de Snowflake, sobre lo que cargamos hoy.
- Hoy solo hacemos la "EL". La "T" todavía no existe, y eso es correcto.

</div>
</div>
</div>

---

## Arquitectura de Snowflake: storage y compute separados

<div class="columnas estrecha-izquierda">
<div>

En una base de datos tradicional, el disco que guarda los datos y el motor que los procesa son la misma máquina. Si necesitas más cómputo, escalas *todo* — incluyendo el almacenamiento, que probablemente no lo necesitabas.

Snowflake separa las dos capas:

- **Storage** — una sola copia de los datos, gestionada por Snowflake, independiente de cuánto cómputo uses.
- **Compute** — *warehouses*: clusters que se prenden y apagan bajo demanda, cada uno facturado aparte.

Esto ya te resulta familiar: es el mismo principio de **Neon separando cómputo y storage** que vimos en la Sesión 1 — Snowflake lo aplica en el mundo OLAP.

</div>
<div>

<div class="diagrama">
        ┌──────────────┐
        │   STORAGE    │  ← una copia, compartida
        └──────┬───────┘
      ┌────────┼────────┐
 ┌────┴───┐ ┌──┴─────┐ ┌─┴──────┐
 │  WH_A  │ │  WH_B  │ │  WH_C  │  ← compute independiente
 │ XSMALL │ │ MEDIUM │ │ XSMALL │     cada uno se paga por
 └────────┘ └────────┘ └────────┘     separado, se apaga solo
</div>

<div class="facts">

### Facts

- Un warehouse **no** guarda datos: es poder de cómputo que apuntas al storage compartido.
- `AUTO_SUSPEND` apaga el warehouse tras N segundos sin uso — clave para no gastar el crédito del trial en cómputo ocioso.

</div>
</div>
</div>

---

## La capa RAW

<div class="columnas">
<div>

`RAW` es el primer schema que vas a crear: el aterrizaje de los datos **exactamente como llegan** de Neon. Mismos nombres, mismos tipos aproximados, sin `JOIN`, sin renombrar, sin limpiar.

¿Por qué no limpiar de una vez, ya que estamos? Porque si limpias en el camino, pierdes la capacidad de auditar: cuando un número en un dashboard se vea raro dentro de dos capítulos, la primera pregunta va a ser *"¿ya estaba raro en RAW, o se rompió después?"* — y esa pregunta solo se puede responder si RAW existe intacto.

</div>
<div>

<div class="diagrama">
 Neon (OLTP)
   │  extracción cruda (hoy)
   ▼
 RAW           ← estás aquí
   │  transformación (dbt, Cap. 3)
   ▼
 staging / marts
   │
   ▼
 Streamlit
</div>

<div class="facts">

### Facts

- RAW es "sucio" a propósito. No es un defecto del diseño — es el diseño.
- Todo lo que dbt haga en el Capítulo 3 parte de aquí. Si RAW está mal, todo lo de encima hereda el error.

</div>
</div>
</div>

---

## Checklist pre-taller

<div class="columnas">
<div>

### Cuentas

<ul class="check">
<li>Cuenta de <strong>Snowflake</strong> creada — trial gratuito, 30 días / USD 400 en crédito: <code>signup.snowflake.com</code></li>
<li>Sesión iniciada en <strong>Snowsight</strong> (la consola web).</li>
</ul>

### Del Capítulo 1

<ul class="check">
<li>Momento 1 aprobado: tu branch <code>dev</code> de Neon tiene el estado base + las migraciones de la Sesión 2.</li>
<li>Tu <code>.env</code> de la Sesión 1 con <code>NEON_DEV_DATABASE_URL</code> a la mano.</li>
</ul>

</div>
<div>

### Herramientas locales

<ul class="check">
<li><code>uv --version</code> responde.</li>
<li><code>git pull</code> — repositorio actualizado.</li>
</ul>

<div class="aviso">

**Al elegir región y edición en Snowflake, no podrás cambiarlas después.** Cualquier región cercana y la edición *Standard* bastan para este curso — no necesitas *Enterprise*.

</div>

<div class="facts">

### Facts

- No necesitas tarjeta de crédito para el trial.
- El warehouse que crearás hoy se autosuspende — no vas a "gastar" el trial por dejarlo abierto.

</div>
</div>
</div>

---

<!-- _class: seccion -->

<div class="kicker">Parte práctica</div>

## Taller: de Neon a la capa RAW

---

## Paso 1 · Aprovisionar Snowflake

<div class="columnas estrecha-izquierda">
<div>

En Snowsight → **Worksheets** → pega y ejecuta
[`setup_snowflake.sql`](../codigo/setup_snowflake.sql):

```sql
CREATE WAREHOUSE IF NOT EXISTS
  WH_DATAOPS
    WAREHOUSE_SIZE = 'XSMALL'
    AUTO_SUSPEND = 60
    AUTO_RESUME = TRUE;

CREATE DATABASE IF NOT EXISTS
  PARCH_AND_POSEY;

CREATE SCHEMA IF NOT EXISTS
  PARCH_AND_POSEY.RAW;
```

</div>
<div>

El script también crea un **rol de servicio** (`DATAOPS_LOADER`) con permisos mínimos — nunca conectes el script Python como `ACCOUNTADMIN`: ese rol puede borrar la cuenta entera, no solo una tabla.

```sql
GRANT ROLE DATAOPS_LOADER
  TO USER <tu_usuario>;
```

<div class="facts">

### Facts

- `AUTO_SUSPEND = 60`: el warehouse se apaga tras 60s sin uso. Snowflake cobra por segundo de cómputo activo.
- Región y edición **no se pueden cambiar después** de creada la cuenta.

</div>
</div>
</div>

---

## Paso 2 · Proyecto Python con `uv`

<div class="columnas">
<div>

```bash
cd Cap_2_Modern_Data_Warehouse/\
sesion_04_ingesta_snowflake/codigo

uv sync
```

Si arrancaras de cero, así se creó este proyecto:

```bash
uv init --python 3.12

uv add snowflake-connector-python \
       pandas psycopg2-binary \
       python-dotenv
```

</div>
<div>

Configura las credenciales:

```bash
cp .env.example .env
```

Completa en `.env`:
- `NEON_DEV_DATABASE_URL` (la misma de siempre)
- `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PASSWORD`

<div class="facts">

### Facts

- El "Account identifier" está en Snowsight → tu perfil → *Account*. No es el nombre de usuario.
- `uv.lock` se versiona; `.env` no — ya conoces la regla desde la Sesión 1.

</div>
</div>
</div>

---

<!-- _class: compacta -->

## Paso 3 · El script — extracción

De `elt_postgres_to_snowflake.py`. La extracción no sabe nada del negocio:

```python
def extraer_tabla(conexion_pg, tabla: str) -> pd.DataFrame:
    # ¿Por qué extraemos con SELECT * y no una lista explícita de columnas? Porque en
    # ELT la extracción no debe saber nada del negocio: decidir qué columnas importan y
    # cómo se llaman se hace después, en Snowflake, con dbt. Un SELECT * también
    # significa que si el equipo de backend agrega una columna en Neon —como vas a
    # provocar tú mismo en el Paso 4—, la extracción la recoge sola, sin que se toque
    # una sola línea de esta función.
    with conexion_pg.cursor() as cursor:
        cursor.execute(f"SELECT * FROM {tabla}")
        columnas = [c.name.upper() for c in cursor.description]
        filas = cursor.fetchall()
    return pd.DataFrame(filas, columns=columnas)
```

```bash
uv run elt_postgres_to_snowflake.py
```

---

## Paso 3 · El script — carga

<div class="columnas">
<div>

La carga usa `write_pandas`: sube el DataFrame a un stage interno y lo copia a la tabla en un solo paso masivo — no fila por fila.

```python
write_pandas(
    conexion_sf, df,
    table_name=tabla.upper(),
    auto_create_table=True,
    overwrite=True,
)
```

`auto_create_table=True` crea la tabla si no existe, con los tipos que infiere del DataFrame. `overwrite=True` trunca y recarga completo — la estrategia más simple, correcta para esta sesión.

</div>
<div>

```text
Extrayendo orders desde Neon...
  6912 filas · columnas:
  ['ID', 'ACCOUNT_ID', 'OCCURRED_AT', ...]
  OK -> 6912 filas en RAW.ORDERS
```

<div class="facts">

### Facts

- Snowflake guarda los identificadores en **MAYÚSCULA** por convención — por eso el script normaliza las columnas al extraer.
- La estrategia "truncar y recargar completo" no escala a millones de filas — la Sesión 5 introduce alternativas.

</div>
</div>
</div>

---

## Paso 4 · El escenario: schema drift

<div class="columnas">
<div>

Tu pipeline corrió bien toda la semana. El viernes, sin avisarte, el equipo de backend agrega una columna a `orders` en producción:

```sql
ALTER TABLE orders
  ADD COLUMN discount_code VARCHAR(20);
```

Lunes en la mañana, corres el ELT como siempre:

```bash
uv run elt_postgres_to_snowflake.py
```

Y en un pipeline **frágil** —uno que llama a `write_pandas` directo, sin verificar nada antes—, esto es lo que revienta:

</div>
<div>

```text
002023 (42601): SQL compilation
error: error line 1 at position 45
invalid identifier 'DISCOUNT_CODE'
```

<div class="aviso">

**Incidente real de la industria.** El equipo de Data no controla el schema de origen — lo controla backend, con su propio calendario.

</div>

<div class="facts">

### Facts

- `write_pandas` lista las columnas del DataFrame en el `COPY INTO`. Si a la tabla le falta una, Snowflake rechaza todo.
- El error dice "identificador inválido", no "falta una columna" — hay que saber traducirlo.

</div>
</div>
</div>

---

## Paso 5 · La solución DataOps: detectar antes de fallar

<div class="columnas estrecha-izquierda">
<div>

El script de este repositorio no espera a que Snowflake reviente. Antes de cargar, compara las columnas del DataFrame contra las que ya existen en la tabla destino:

```python
existentes = columnas_existentes_en_snowflake(
    conexion_sf, esquema, tabla)
drift = calcular_drift(
    set(df.columns), existentes)

if drift:
    ddl = construir_ddl_evolucion(
        tabla, drift, df)
    raise RuntimeError(...)
```

</div>
<div>

```text
ERROR: Schema drift detectado en
ORDERS: la fuente en Neon trae
columna(s) nueva(s): ['DISCOUNT_CODE'].

Aplica esto en Snowsight y vuelve
a correr el script:

ALTER TABLE ORDERS ADD COLUMN
  "DISCOUNT_CODE" VARCHAR;
```

<div class="facts">

### Facts

- El script **genera el DDL exacto** — no lo ejecuta solo. Alterar un schema de producción sin que nadie lo revise es su propio riesgo.
- El "ajuste al script" no fue agregar una columna a mano: fue enseñarle a **detectar y explicar**, no a fallar en silencio tres capas más abajo.
</div>
</div>
</div>

---

## Paso 6 · Cerrar el ciclo

<div class="columnas">
<div>

Con el DDL en la mano, lo aplicas en Snowsight:

```sql
ALTER TABLE ORDERS ADD COLUMN
  "DISCOUNT_CODE" VARCHAR;
```

Y vuelves a correr el mismo comando de siempre — **sin tocar el script**:

```bash
uv run elt_postgres_to_snowflake.py
```

</div>
<div>

```text
Extrayendo orders desde Neon...
  6912 filas · columnas:
  [..., 'DISCOUNT_CODE']
  OK -> 6912 filas en RAW.ORDERS
```

<div class="facts">

### Facts

- El schema del Data Warehouse **también evoluciona** — igual que el de Neon en el Capítulo 1, solo que aquí el disparador es una tabla de origen, no un negocio.
- Nota lo que NO cambió: el código Python. Gracias al `SELECT *` del Paso 3, la única pieza que evolucionó fue el DDL de Snowflake.

</div>
</div>
</div>

---

<!-- _class: cierre -->

## Conclusiones

<div class="columnas">
<div>

### Lo que construiste hoy

- Un Data Warehouse en Snowflake, con storage y compute separados.
- Un proceso **ELT** real: extraer de Neon, cargar crudo en `RAW`.
- La experiencia de un fallo de producción real —schema drift— y cómo un pipeline bien diseñado lo convierte en un mensaje claro, no en un stack trace de tres capas.

### La regla que te llevas

**Detecta antes de fallar, y que el error diga qué hacer.** La misma disciplina de la Sesión 2 (Flyway validando antes de migrar), aplicada al límite entre dos sistemas que no se hablan.

</div>
<div>

<div class="aviso">

**Esto alimenta el Momento 2.** El pipeline de hoy corre sobre Parch & Posey como ejemplo de clase — para tu entregable evaluativo, repites este mismo patrón sobre el modelo propio de tu equipo.

</div>

### Próxima sesión

**21/08 · Internal Stages e idempotencia.** Hoy cargamos con `write_pandas` y `overwrite=True` — funciona, pero no escala ni es idempotente de verdad. La Sesión 5 resuelve ambas cosas con `PUT` + `COPY INTO`, una bitácora de ejecución y validaciones automatizadas.

</div>
</div>
