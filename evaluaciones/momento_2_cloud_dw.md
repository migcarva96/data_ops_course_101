# Momento 2 — Cloud Data Warehouse e Ingesta

**Módulo:** Tendencias emergentes en desarrollo de software (SI6010-5979) · Pos ST1707
**Peso sobre la nota final:** **30 %**
**Capítulo:** 2 — Modern Data Warehouse
**Se sustenta en:** [Sesión 6 — Sustentación Momento 2](../Cap_2_Modern_Data_Warehouse/sesion_06_sustentacion_momento2/) · sábado **22/08/2026**, 08:00–11:00, aula 33-302
**Stack:** Snowflake — arquitectura como código, ELT relacional con `uv`, External Stages
(JSON), Tasks, RBAC y Dynamic Data Masking

---

## 1. Objetivo

Demostrar que el equipo puede **mover datos hacia un Cloud Data Warehouse de forma
programática y gobernada, desde más de una forma de origen** — relacional y
semi-estructurada— y que puede **operar** ese warehouse: orquestar su propia
actualización y proteger lo sensible que contiene.

Al terminar este momento, el equipo debe poder responder con evidencia:

- ¿Cómo llegan los datos de Neon a Snowflake, y quién ejecuta ese proceso?
- ¿Qué pasa si la fuente relacional cambia de esquema sin avisar?
- ¿Cómo entra a Snowflake un dato que no tiene un esquema fijo, y qué se hace con él?
- ¿Quién puede ver qué, y por qué la respuesta no es "todos ven todo"?

---

## 2. Contexto del caso

Este momento, igual que el Momento 1, se hace sobre el **proyecto propio** de cada
equipo — el dominio de negocio y el modelo transaccional definidos entonces, no Parch &
Posey (que en las Sesiones 4 y 5 sigue siendo el ejemplo compartido de clase).

El Momento 1 dejó una base de datos transaccional versionada y desplegada
automáticamente. Pero el equipo analítico no puede consultarla directamente: las queries
pesadas degradan el sistema operacional, y no todo dato relevante para el negocio vive en
esa base relacional — casi siempre hay una segunda fuente, más desordenada, que también
importa (un export de un proveedor, un webhook, un log). El encargo de este momento es
construir **ambos** caminos de ingesta hacia Snowflake, y dejar el resultado operable y
protegido.

> **Este momento parte del entregable del Momento 1.** La fuente relacional es la base de
> datos Neon del proyecto propio del equipo, ya versionada con Flyway.

---

## 3. Alcance

### Incluido en el alcance

**1. Arquitectura de la cuenta Snowflake como código**
   - Warehouse dimensionado apropiadamente (XSMALL con auto-suspend), base de datos y
     esquemas por dominio (al menos uno para datos relacionales, otro para
     semi-estructurados).
   - Un rol de servicio con permisos mínimos para la ingesta — nunca `ACCOUNTADMIN`.

**2. Ingesta relacional** (patrón de la Sesión 4)
   - Script de extracción en Python gestionado con `uv` (`pyproject.toml` + `uv.lock`,
     **no** `pip` ni `requirements.txt` a mano).
   - Extrae de Neon y carga en Snowflake (`write_pandas` u otro método masivo — no
     `INSERT` fila a fila).
   - Detecta **schema drift** antes de cargar (comparar columnas del origen contra las
     del destino) y falla con un mensaje accionable en vez de dejar que la carga reviente
     sin explicación.

**3. Ingesta semi-estructurada** (patrón de la Sesión 5)
   - Al menos **una fuente de datos en JSON** relacionada con el dominio de negocio del
     equipo, que no exista todavía en el modelo relacional del Momento 1 (inventada por el
     equipo si hace falta — ej. un export de un proveedor externo, eventos de un webhook,
     un log de actividad). Debe incluir al menos un **array anidado** que justifique usar
     `LATERAL FLATTEN`.
   - Cargada vía **External Stage** hacia una columna `VARIANT`, sin definir su esquema de
     antemano.
   - Aplanada hacia una tabla de staging con notación de punto y `LATERAL FLATTEN`.
   - Tamaño y complejidad razonables — unos pocos archivos, no un dataset de producción;
     lo que importa es el patrón, no el volumen.

**4. Orquestación nativa con Snowflake Tasks**
   - Un **DAG de al menos dos tareas** (una raíz con `SCHEDULE`, al menos una hija con
     `AFTER`) que encadene ingesta y transformación de al menos una de las dos fuentes.
   - Evidencia de administración real: activar, disparar manualmente, consultar
     `TASK_HISTORY`, y apagar correctamente (sabiendo en qué orden).

**5. Gobernanza: RBAC y protección de datos sensibles**
   - Al menos **dos roles de negocio** distintos (más allá del rol de servicio de
     ingesta), con necesidades de acceso diferentes, y los `GRANT` correspondientes —
     nunca acceso total por defecto.
   - Si el dominio del equipo tiene algún campo sensible o PII (nombre, contacto,
     ubicación, dato financiero...), aplicar una **Masking Policy** sobre al menos una
     columna, demostrando visibilidad distinta según el rol activo.
     - Si la cuenta del equipo no tiene Snowflake Enterprise Edition, **no se penaliza**
       no poder ejecutarlo en vivo — pero sí se evalúa que la política esté **escrita,
       correcta, y explicada**, con evidencia de haber intentado aplicarla (el error de
       la cuenta cuenta como evidencia válida). Ver la nota sobre upgrade de edición más
       abajo.

### Fuera del alcance

- dbt y modelado analítico (Momento 3).
- `STORAGE INTEGRATION` con rol IAM — un bucket de solo lectura (propio o compartido) es
  suficiente para este momento.
- Tokenización, Row Access Policies, u otras herramientas de gobernanza más allá de RBAC y
  Dynamic Data Masking.
- Cualquier capa de visualización.

### Nota sobre Snowflake Enterprise Edition

Los trials de Snowflake permiten actualizar de Standard a Enterprise mediante
`ALTER ACCOUNT ... SET EDITION`, ejecutado desde la **Organization Account** (Snowsight →
*Admin* → *Organization*) — no desde la cuenta que se quiere actualizar. Se recomienda
hacerlo **antes** de empezar este momento si el equipo quiere demostrar la Masking Policy
en vivo. No es obligatorio: ver el criterio de evaluación correspondiente.

---

## 4. Entregables

| # | Entregable | Formato | Dónde |
|---|---|---|---|
| E1 | Scripts SQL de arquitectura Snowflake (warehouse, esquemas, rol de servicio) | `.sql` versionados | `snowflake/setup/` del repositorio |
| E2 | Proyecto Python de extracción relacional con `pyproject.toml` + `uv.lock` | Código | `ingesta/` del repositorio |
| E3 | Detección de schema drift, con evidencia de un caso provocado y su corrección | Código + evidencia | En el repositorio |
| E4 | Scripts de la fuente semi-estructurada: File Format, External Stage, `FLATTEN`, tabla de staging | `.sql` versionados | `snowflake/json/` del repositorio |
| E5 | Scripts del DAG de Tasks + evidencia de `TASK_HISTORY` con al menos una ejecución exitosa | `.sql` + captura | En el repositorio |
| E6 | Scripts de roles y Masking Policy (o el intento documentado, si la edición no alcanza) | `.sql` versionados | En el repositorio |
| E7 | `.env.example` (extracción relacional) — cero credenciales reales en el repositorio | Texto | Raíz del repositorio |
| E8 | Documento de decisiones (1–2 páginas): qué fuente semi-estructurada eligieron y por qué, estrategia de roles | Markdown | `docs/` del repositorio |
| E9 | Sustentación oral | 10 min de exposición + 5 min de preguntas | Sesión 6 — 22/08/2026 |

### Sobre la sustentación (E9)

**Demo en vivo obligatoria.** Cada equipo (los mismos del Momento 1) dispone de 10
minutos:

1. Ejecutar la ingesta relacional y mostrar cómo se comporta ante schema drift.
2. Ejecutar (o disparar manualmente) el DAG de Tasks y mostrar `TASK_HISTORY`.
3. Mostrar la diferencia de visibilidad entre roles sobre el dato protegido — en vivo si
   la cuenta lo permite, o explicando el diseño sobre el código si no.

> ⚠️ **Un pipeline que solo funciona en la máquina de un integrante no cumple el objetivo
> del momento.** Los scripts SQL deben ejecutarse contra la cuenta real de Snowflake del
> equipo, delante del grupo.

---

## 5. Condiciones de entrega

- **Fecha límite de código:** sábado **22/08/2026, 07:00** (una hora antes de la sesión).
- **Modalidad:** mismos equipos del Momento 1. Cambios de equipo deben avisarse con
  anticipación al docente.
- **Entregas tardías:** se califican sobre el 70 % hasta 48 horas después.
- **Cuidado con el trial de Snowflake:** son 30 días. Si iniciaste tu trial antes del
  01/08, verifica que siga vigente el 22/08 y avisa al docente si no lo está.

---

## 6. Rúbrica de evaluación

**Total: 100 puntos** → equivalen al 30 % de la nota final.

### C1. Arquitectura Snowflake como código — 10 puntos

| Nivel | Puntos | Descripción |
|---|---|---|
| Excelente | 9–10 | Setup reproducible desde scripts versionados. Esquemas separados por dominio (relacional vs. semi-estructurado). Rol de servicio con permisos mínimos, no `ACCOUNTADMIN`. |
| Bueno | 6–8 | Setup scriptado y funcional, pero sin separar dominios o con un rol sobre-privilegiado. |
| Suficiente | 3–5 | Objetos creados parcialmente a mano por la UI. |
| Insuficiente | 0–2 | Todo creado por interfaz gráfica, sin scripts. |

### C2. Ingesta relacional y manejo de schema drift — 20 puntos

| Nivel | Puntos | Descripción |
|---|---|---|
| Excelente | 18–20 | Proyecto `uv` reproducible (`pyproject.toml` + `uv.lock`). Carga masiva correcta. Detecta drift **antes** de cargar, con mensaje accionable, demostrado con un caso real provocado y corregido. |
| Bueno | 13–17 | Carga funciona y es reproducible, pero la detección de drift es parcial o no se demuestra con un caso real. |
| Suficiente | 8–12 | Funciona, pero con `requirements.txt` a mano, `pip install`, o sin ningún manejo de drift. |
| Insuficiente | 0–7 | No reproducible, o credenciales hardcodeadas. |

### C3. Ingesta semi-estructurada (External Stage + `VARIANT` + `FLATTEN`) — 20 puntos

| Nivel | Puntos | Descripción |
|---|---|---|
| Excelente | 18–20 | Fuente JSON propia y pertinente al dominio, con al menos un array anidado real. External Stage y File Format correctos. `LATERAL FLATTEN` bien aplicado, con manejo correcto de claves ausentes. Tabla de staging materializada. |
| Bueno | 13–17 | La ingesta funciona, pero la fuente es trivial (sin anidamiento real) o el `FLATTEN` tiene errores menores. |
| Suficiente | 8–12 | Carga los datos como `VARIANT` pero no llega a aplanarlos, o lo hace con consultas ad-hoc no reproducibles. |
| Insuficiente | 0–7 | No hay fuente semi-estructurada, o se cargó como si fuera relacional (columnas fijas desde el inicio). |

### C4. Orquestación con Snowflake Tasks — 20 puntos

| Nivel | Puntos | Descripción |
|---|---|---|
| Excelente | 18–20 | DAG de ≥2 tareas real (root con `SCHEDULE`, hija con `AFTER`). Activación, ejecución manual y apagado demostrados correctamente — incluyendo el orden correcto al suspender. `TASK_HISTORY` consultado como evidencia. |
| Bueno | 13–17 | El DAG existe y corre, pero la administración (activar/apagar) tiene errores no resueltos, o solo hay una tarea (sin dependencia real). |
| Suficiente | 8–12 | Existe una Task suelta, sin DAG, o nunca se ha ejecutado con éxito. |
| Insuficiente | 0–7 | Sin Tasks — la actualización es manual. |

### C5. RBAC y protección de datos sensibles — 20 puntos

| Nivel | Puntos | Descripción |
|---|---|---|
| Excelente | 18–20 | ≥2 roles de negocio con `GRANT`s deliberados y distintos entre sí. Masking Policy aplicada y demostrada con visibilidad diferenciada por rol (o, en cuenta Standard, política escrita y correcta con evidencia clara del intento y del error de edición). |
| Bueno | 13–17 | Los roles existen y tienen acceso diferenciado, pero la protección del dato sensible es incompleta o no se demuestra. |
| Suficiente | 8–12 | Un solo rol además del de servicio, o acceso que no está realmente diferenciado (todos ven lo mismo). |
| Insuficiente | 0–7 | Sin RBAC de negocio — todo opera con el rol de servicio o `ACCOUNTADMIN`. |

### C6. Documentación y sustentación oral — 10 puntos

| Nivel | Puntos | Descripción |
|---|---|---|
| Excelente | 9–10 | `docs/` explica con criterio propio la fuente semi-estructurada elegida y la estrategia de roles. Demo en vivo fluida dentro del tiempo. Responde con solvencia preguntas sobre las decisiones tomadas. |
| Bueno | 6–8 | Documentación y demo presentes, pero descriptivas más que argumentativas. |
| Suficiente | 3–5 | Documentación mínima, o demo con capturas en vez de ejecución en vivo. |
| Insuficiente | 0–2 | No sustenta, o no puede explicar su propio código. |

---

## 7. Recursos

- Sesión 4 — [Ingesta hacia Snowflake](../Cap_2_Modern_Data_Warehouse/sesion_04_ingesta_snowflake/) — patrón de extracción relacional y schema drift.
- Sesión 5 — [External Stages, JSON y gobernanza](../Cap_2_Modern_Data_Warehouse/sesion_05_external_stages_json/) — patrón de ingesta semi-estructurada, Tasks, RBAC y Masking.
- Snowflake — Loading JSON data: https://docs.snowflake.com/en/user-guide/json-basics-load
- Snowflake — `LATERAL FLATTEN`: https://docs.snowflake.com/en/sql-reference/functions/flatten
- Snowflake — Introduction to Tasks: https://docs.snowflake.com/en/user-guide/tasks-intro
- Snowflake — Dynamic Data Masking: https://docs.snowflake.com/en/user-guide/security-column-ddm-intro
- Snowflake — cambiar de edición: https://docs.snowflake.com/en/user-guide/organizations-manage-accounts-editions
- `uv` — gestión de proyectos: https://docs.astral.sh/uv/guides/projects/
