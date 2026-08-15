"""
ELT relacional: Neon (PostgreSQL) -> Snowflake, capa RAW.

Sesión 4 del módulo "Tendencias emergentes en desarrollo de software" (SI6010-5979).

Extrae las tablas de Parch & Posey desde la branch `dev` de Neon y las carga, sin
transformar, en el schema RAW de Snowflake. Es "ELT", no "ETL": la transformación
(capítulo 3, con dbt) ocurre después, dentro de Snowflake — no aquí.

Uso:
    uv run elt_postgres_to_snowflake.py                  # carga las 5 tablas
    uv run elt_postgres_to_snowflake.py --tabla orders    # solo una tabla
    uv run elt_postgres_to_snowflake.py --solo-verificar  # detecta drift, no carga
"""

from __future__ import annotations

import argparse
import os
import sys

import pandas as pd
import psycopg2
import snowflake.connector
from dotenv import load_dotenv
from snowflake.connector.pandas_tools import write_pandas

TABLAS = ["regions", "sales_reps", "accounts", "orders", "web_events"]

# ¿Por qué mapeamos el dtype de pandas a un tipo de Snowflake en vez de usar siempre
# VARCHAR para todo? Porque una columna VARCHAR genérica funciona, pero renuncia a
# cualquier validación en el destino: un total que llega como texto no se detecta hasta
# que algo intenta sumarlo, dos capítulos más adelante. El mapeo es deliberadamente
# aproximado — el tipado fino es trabajo de dbt en capas posteriores, no de la capa RAW.
MAPA_TIPOS_SNOWFLAKE = {
    "int64": "NUMBER",
    "float64": "FLOAT",
    "bool": "BOOLEAN",
    "datetime64[ns]": "TIMESTAMP_NTZ",
    "object": "VARCHAR",
}


# ---------------------------------------------------------------------------
# Extracción — Neon
# ---------------------------------------------------------------------------

def conectar_neon() -> psycopg2.extensions.connection:
    url = os.getenv("NEON_DEV_DATABASE_URL")
    if not url:
        print("ERROR: falta NEON_DEV_DATABASE_URL en .env", file=sys.stderr)
        sys.exit(1)
    return psycopg2.connect(url)


def extraer_tabla(conexion_pg, tabla: str) -> pd.DataFrame:
    # ¿Por qué extraemos con SELECT * y no una lista explícita de columnas? Porque en
    # ELT la extracción no debe saber nada del negocio: decidir qué columnas importan y
    # cómo se llaman se hace después, en Snowflake, con dbt. Un SELECT * también
    # significa que si el equipo de backend agrega una columna en Neon —como vas a
    # provocar tú mismo en el Paso 4 de esta sesión—, la extracción la recoge sola, sin
    # que se toque una sola línea de esta función.
    with conexion_pg.cursor() as cursor:
        cursor.execute(f"SELECT * FROM {tabla}")
        columnas = [c.name.upper() for c in cursor.description]
        filas = cursor.fetchall()
    # Snowflake guarda los identificadores sin comillas en MAYÚSCULA por convención.
    # Si dejáramos los nombres tal como los devuelve Postgres (minúscula), esta misma
    # tabla de comparación de schemas (más abajo) compararía "occurred_at" contra
    # "OCCURRED_AT" y creería que todo es drift. Normalizamos aquí, en el borde de
    # entrada, para que el resto del script no tenga que pensar en mayúsculas o
    # minúsculas nunca más.
    return pd.DataFrame(filas, columns=columnas)


# ---------------------------------------------------------------------------
# Detección de schema drift — lógica pura, sin I/O
# ---------------------------------------------------------------------------
#
# Estas dos funciones no abren ninguna conexión: reciben los datos que necesitan como
# argumentos y devuelven un resultado. Es a propósito. Así se pueden probar con datos
# de ejemplo sin tener una cuenta de Snowflake a mano — y así se probaron, de hecho,
# antes de que este script se entregara para la clase.

def calcular_drift(columnas_dataframe: set[str], columnas_snowflake: set[str]) -> set[str]:
    """Columnas que trae la extracción y que la tabla destino todavía no tiene."""
    return columnas_dataframe - columnas_snowflake


def construir_ddl_evolucion(tabla: str, columnas_nuevas: set[str], df: pd.DataFrame) -> str:
    """Genera el ALTER TABLE que resolvería el drift — para mostrarlo, no para ejecutarlo solo."""
    lineas = []
    for columna in sorted(columnas_nuevas):
        tipo_pandas = str(df[columna].dtype)
        tipo_snowflake = MAPA_TIPOS_SNOWFLAKE.get(tipo_pandas, "VARCHAR")
        lineas.append(f'ALTER TABLE {tabla.upper()} ADD COLUMN "{columna}" {tipo_snowflake};')
    return "\n".join(lineas)


# ---------------------------------------------------------------------------
# Snowflake — I/O
# ---------------------------------------------------------------------------

def conectar_snowflake() -> snowflake.connector.SnowflakeConnection:
    # ¿Por qué fijar warehouse/database/schema/role explícitamente en la conexión, y no
    # dejar que cada quien tenga un default configurado en su usuario de Snowflake?
    # Porque cada sentencia corre en el contexto de la sesión activa. Si lo dejamos
    # implícito, el script funciona hoy en tu cuenta —donde configuraste ese default a
    # mano— y falla en la de tu compañero de equipo, que nunca lo configuró, sin que
    # cambie una sola línea de código. Ser explícitos aquí es lo que hace el script
    # reproducible entre máquinas distintas.
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        database=os.environ["SNOWFLAKE_DATABASE"],
        schema=os.environ.get("SNOWFLAKE_SCHEMA", "RAW"),
        role=os.environ.get("SNOWFLAKE_ROLE"),
    )


def columnas_existentes_en_snowflake(conexion_sf, esquema: str, tabla: str) -> set[str]:
    with conexion_sf.cursor() as cursor:
        cursor.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = %s AND table_name = %s",
            (esquema.upper(), tabla.upper()),
        )
        return {fila[0] for fila in cursor.fetchall()}


def cargar_tabla(conexion_sf, tabla: str, df: pd.DataFrame, esquema: str) -> int:
    existentes = columnas_existentes_en_snowflake(conexion_sf, esquema, tabla)

    if existentes:
        drift = calcular_drift(set(df.columns), existentes)
        if drift:
            # Fallar aquí, con un mensaje claro y el DDL ya redactado, es preferible a
            # dejar que write_pandas explote más abajo con un "invalid identifier" que
            # no dice en qué tabla, ni qué columna, ni qué hacer al respecto. El error
            # es el mismo problema; el mensaje es la diferencia entre 10 segundos de
            # diagnóstico y 20 minutos leyendo logs de Snowflake.
            ddl = construir_ddl_evolucion(tabla, drift, df)
            raise RuntimeError(
                f"\nSchema drift detectado en {tabla.upper()}: la fuente en Neon trae "
                f"columna(s) nueva(s) que Snowflake no tiene todavía: {sorted(drift)}.\n\n"
                f"Aplica esto en un Worksheet de Snowsight y vuelve a correr el script:\n\n"
                f"{ddl}\n"
            )

    exito, _, num_filas, _ = write_pandas(
        conexion_sf,
        df,
        table_name=tabla.upper(),
        auto_create_table=True,
        overwrite=True,
    )
    if not exito:
        raise RuntimeError(f"write_pandas reportó fallo al cargar {tabla}")
    return num_filas


# ---------------------------------------------------------------------------
# Orquestación
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="ELT de Neon hacia la capa RAW de Snowflake.")
    parser.add_argument("--tabla", choices=TABLAS, help="Cargar solo esta tabla.")
    parser.add_argument(
        "--solo-verificar",
        action="store_true",
        help="Extrae y compara schemas, pero no escribe nada en Snowflake.",
    )
    argumentos = parser.parse_args()

    load_dotenv()
    tablas = [argumentos.tabla] if argumentos.tabla else TABLAS
    esquema = os.environ.get("SNOWFLAKE_SCHEMA", "RAW")

    conexion_pg = conectar_neon()
    conexion_sf = conectar_snowflake()
    try:
        for tabla in tablas:
            print(f"Extrayendo {tabla} desde Neon...")
            df = extraer_tabla(conexion_pg, tabla)
            print(f"  {len(df)} filas · columnas: {list(df.columns)}")

            if argumentos.solo_verificar:
                existentes = columnas_existentes_en_snowflake(conexion_sf, esquema, tabla)
                drift = calcular_drift(set(df.columns), existentes) if existentes else set()
                estado = f"DRIFT: {sorted(drift)}" if drift else "sin drift"
                print(f"  [verificación] {estado}")
                continue

            num_filas = cargar_tabla(conexion_sf, tabla, df, esquema)
            print(f"  OK -> {num_filas} filas en {esquema}.{tabla.upper()}")

        return 0
    except RuntimeError as error:
        print(f"\nERROR: {error}", file=sys.stderr)
        return 1
    finally:
        conexion_pg.close()
        conexion_sf.close()


if __name__ == "__main__":
    sys.exit(main())
