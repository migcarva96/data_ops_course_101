# Rúbrica — Momento 2: Cloud Data Warehouse e Ingesta

**Sesión:** 6 — sábado 22/08/2026, 08:00–11:00, aula 33-302
**Peso:** 30 % de la nota final · **Total: 100 puntos**
**Modalidad:** mismos equipos del Momento 1, sobre su proyecto propio (no Parch & Posey).

> 📄 **El enunciado completo, con objetivo, alcance, entregables y condiciones de entrega,
> está en [`evaluaciones/momento_2_cloud_dw.md`](../../evaluaciones/momento_2_cloud_dw.md).**
> Este archivo es el resumen operativo de calificación para el día de la sustentación.

---

## Criterios y puntajes

| # | Criterio | Puntos | Qué se busca |
|---|---|---|---|
| C1 | Arquitectura Snowflake como código | **10** | Setup reproducible desde scripts, esquemas separados por dominio, rol de servicio sin `ACCOUNTADMIN`. |
| C2 | Ingesta relacional y schema drift | **20** | Proyecto `uv` reproducible; carga masiva; detección de drift demostrada con un caso real. |
| C3 | Ingesta semi-estructurada | **20** | Fuente JSON propia con array anidado real, vía External Stage + `VARIANT`; `LATERAL FLATTEN` correcto. |
| C4 | Orquestación con Tasks | **20** | DAG de ≥2 tareas real, con `SCHEDULE`/`AFTER`; activar, ejecutar y apagar en el orden correcto; `TASK_HISTORY` como evidencia. |
| C5 | RBAC y protección de datos | **20** | ≥2 roles de negocio con `GRANT`s distintos; Masking Policy aplicada (o intento documentado si la edición no alcanza). |
| C6 | Documentación y sustentación oral | **10** | Decisiones argumentadas por escrito; demo en vivo en 10 min. |
| | **Total** | **100** | |

Los descriptores por nivel (Excelente / Bueno / Suficiente / Insuficiente) de cada
criterio están detallados en la
[sección 6 del enunciado](../../evaluaciones/momento_2_cloud_dw.md#6-rúbrica-de-evaluación).

---

## Checklist rápido de verificación

Antes de calificar, confirmar sobre el repositorio del equipo:

- [ ] El modelo de datos es el proyecto propio del equipo (Momento 1), no Parch & Posey.
- [ ] Los objetos de Snowflake se crean desde scripts versionados, no desde la UI.
- [ ] El proyecto Python de extracción tiene `pyproject.toml` **y** `uv.lock`.
- [ ] Hay evidencia de un caso de schema drift real, detectado antes de romper la carga.
- [ ] La fuente semi-estructurada tiene al menos un array anidado — no es una tabla plana disfrazada de JSON.
- [ ] `LATERAL FLATTEN` produce filas correctas, incluido el manejo de claves ausentes.
- [ ] El DAG de Tasks corrió con éxito al menos una vez — verificar en `TASK_HISTORY`.
- [ ] Apagar el DAG se hizo en el orden correcto (raíz primero) sin errores sin resolver.
- [ ] Hay al menos 2 roles de negocio con acceso realmente diferenciado (no todos ven lo mismo).
- [ ] Si hay Masking Policy: demo en vivo, o evidencia clara del intento y el error de edición.
- [ ] `.env.example` existe y no contiene valores reales.

---

## Logística de la sesión

| Bloque | Duración | Actividad |
|---|---|---|
| Apertura | 15 min | Encuadre y orden de sustentaciones |
| Sustentaciones | ~2 h 15 min | 15 min por equipo (10 exposición + 5 preguntas) |
| Cierre | 30 min | Retroalimentación grupal y puente hacia el Capítulo 3 |

**Requisito técnico:** verificar **vigencia del trial de Snowflake** con anticipación. Un
trial vencido el día de la sustentación no es causal de reprogramación — coordinar con el
docente **antes** si hay riesgo. Si el equipo quiere demostrar Masking en vivo y su cuenta
es Standard, el upgrade a Enterprise (`ALTER ACCOUNT ... SET EDITION`, desde la
Organization Account) debe hacerse con anticipación — no es una acción instantánea que se
pueda improvisar durante la sustentación.
