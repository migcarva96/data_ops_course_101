-- ============================================================================
-- setup_snowflake.sql — Aprovisionamiento de la cuenta, Sesión 4
--
-- Ejecutar UNA VEZ, como ACCOUNTADMIN (o un rol con privilegio CREATE), desde un
-- Worksheet de Snowsight (https://app.snowflake.com -> tu cuenta -> Worksheets).
--
-- Crea: un warehouse pequeño con auto-suspend, la base de datos del caso, el
-- schema RAW donde aterrizan los datos crudos, y un rol de servicio de mínimo
-- privilegio para que el script Python nunca corra como ACCOUNTADMIN.
-- ============================================================================

-- ¿Por qué XSMALL y AUTO_SUSPEND en 60 segundos? Es el warehouse más pequeño que
-- ofrece Snowflake, y sobra para las ~16 000 filas de Parch & Posey. El auto-suspend
-- agresivo importa porque Snowflake cobra por segundo de cómputo ACTIVO: un warehouse
-- que quedó "prendido" por descuido consume crédito del trial aunque nadie lo esté
-- usando — y el trial son 30 días y USD 400, no una tarjeta con límite alto.
CREATE WAREHOUSE IF NOT EXISTS WH_DATAOPS
    WAREHOUSE_SIZE      = 'XSMALL'
    AUTO_SUSPEND        = 60
    AUTO_RESUME         = TRUE
    INITIALLY_SUSPENDED = TRUE
    COMMENT             = 'Warehouse del curso DataOps — Capítulo 2 (sesiones 4 y 5)';

CREATE DATABASE IF NOT EXISTS PARCH_AND_POSEY
    COMMENT = 'Data Warehouse del caso Parch & Posey — Capítulo 2';

-- El schema RAW es intencionalmente "sucio": mismos nombres y tipos que el origen en
-- Neon, sin limpieza ni de-duplicación. Es el punto de partida auditable de todo lo
-- que dbt hará en el Capítulo 3 — si un mart muestra un número raro, la primera
-- pregunta siempre es "¿ya estaba raro en RAW, o se rompió después?".
CREATE SCHEMA IF NOT EXISTS PARCH_AND_POSEY.RAW
    COMMENT = 'Landing zone: datos extraídos de Neon, sin transformar';

-- ----------------------------------------------------------------------------
-- Rol de servicio para el pipeline Python
-- ----------------------------------------------------------------------------

-- El script ELT de este repositorio nunca debe conectarse con ACCOUNTADMIN. Ese rol
-- puede crear y borrar warehouses, usuarios y bases de datos de toda la cuenta — un
-- error en un script (o una credencial filtrada) con ese rol es un incidente de
-- cuenta completa, no un incidente de una tabla.
CREATE ROLE IF NOT EXISTS DATAOPS_LOADER
    COMMENT = 'Rol de servicio para el ELT de la Sesión 4. Sin privilegios de administración.';

GRANT USAGE ON WAREHOUSE WH_DATAOPS TO ROLE DATAOPS_LOADER;
GRANT USAGE ON DATABASE PARCH_AND_POSEY TO ROLE DATAOPS_LOADER;
GRANT USAGE, CREATE TABLE ON SCHEMA PARCH_AND_POSEY.RAW TO ROLE DATAOPS_LOADER;
GRANT SELECT, INSERT, UPDATE, DELETE ON FUTURE TABLES IN SCHEMA PARCH_AND_POSEY.RAW TO ROLE DATAOPS_LOADER;

-- Reemplaza <TU_USUARIO> por tu nombre de usuario de Snowflake (el mismo que usas
-- para iniciar sesión en Snowsight) y ejecuta esta línea para poder usar el rol.
-- GRANT ROLE DATAOPS_LOADER TO USER <TU_USUARIO>;

USE WAREHOUSE WH_DATAOPS;
USE DATABASE PARCH_AND_POSEY;
USE SCHEMA RAW;

-- ----------------------------------------------------------------------------
-- Verificación
-- ----------------------------------------------------------------------------
SHOW WAREHOUSES LIKE 'WH_DATAOPS';
SHOW SCHEMAS IN DATABASE PARCH_AND_POSEY;
SHOW GRANTS TO ROLE DATAOPS_LOADER;
