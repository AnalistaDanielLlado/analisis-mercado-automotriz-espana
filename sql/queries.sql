#EVOLUCION DEL MERCADO
SELECT anio, total
FROM matriculaciones
ORDER BY anio;

#EVOLUCION DEL PARQUE AUTOMOTRIZ
SELECT anio, total
FROM parque
ORDER BY anio;

#RATIO RENOVACION
SELECT m.anio,
       m.total AS matriculaciones,
       p.total AS parque,
       m.total / p.total AS ratio_renovacion
FROM matriculaciones m
JOIN parque p
ON m.anio = p.anio;

#CUOTA COMBUSTIBLE PORCENTAJE
SELECT anio,
       gasolina/total AS cuota_gasolina,
       diesel/total AS cuota_diesel,
       otros/total AS cuota_otros
FROM combustible;

#TOP PROVINCIAS MATRICULACIONES
SELECT provincia, matriculaciones
FROM matriculaciones_provincia
WHERE anio = 2025
ORDER BY matriculaciones DESC;

#PROVINCIAS QUE USAN MAS ELECTRICOS
SELECT provincia, pct_cero
FROM distintivo
ORDER BY pct_cero DESC;

#EVOLUCION ANUAL DEL MERCADO CON CRECIMIENTO INTERANUAL
SELECT 
    anio,
    total,
    LAG(total) OVER (ORDER BY anio) AS total_anio_anterior,
    ROUND(
        (total - LAG(total) OVER (ORDER BY anio)) * 100.0 
        / LAG(total) OVER (ORDER BY anio), 
        2
    ) AS crecimiento_pct
FROM matriculaciones
ORDER BY anio;

#RATIO DE RENOVACION DEL PARQUE
SELECT 
    m.anio,
    m.total AS matriculaciones,
    p.total AS parque,
    ROUND(m.total * 100.0 / p.total, 2) AS ratio_renovacion_pct
FROM matriculaciones m
JOIN parque p 
    ON m.anio = p.anio
ORDER BY m.anio;

#PARTICIPACION POR TIPO DE VEHICULO
SELECT
    anio,
    ROUND(turismos * 100.0 / total, 2) AS pct_turismos,
    ROUND(motocicletas * 100.0 / total, 2) AS pct_motocicletas,
    ROUND(camiones_furgonetas * 100.0 / total, 2) AS pct_camiones_furgonetas,
    ROUND(autobuses * 100.0 / total, 2) AS pct_autobuses
FROM matriculaciones
ORDER BY anio;

#CAMBIO ESTRUCTURAL EN COMBUSTIBLE
SELECT
    anio,
    gasolina,
    diesel,
    otros,
    ROUND(gasolina * 100.0 / total, 2) AS pct_gasolina,
    ROUND(diesel * 100.0 / total, 2) AS pct_diesel,
    ROUND(otros * 100.0 / total, 2) AS pct_otros
FROM combustible
ORDER BY anio;

#AÑO EN QUE "OTROS" SUPERA CIERTO UMBRAL (5%)
SELECT
    anio,
    ROUND(otros * 100.0 / total, 2) AS pct_otros
FROM combustible
WHERE (otros * 100.0 / total) >= 5
ORDER BY anio;

#TOP PROVINIAS POR MATRICULACIONES EN EL ULTIMO AÑO REGISTRADO
SELECT 
    provincia,
    matriculaciones
FROM matriculaciones_provincia
WHERE anio = (SELECT MAX(anio) FROM matriculaciones_provincia)
ORDER BY matriculaciones DESC
LIMIT 10;


#CUOTA PROVINCIAL SOBRE EL MERCADO NACIONAL
SELECT
    mp.provincia,
    mp.anio,
    mp.matriculaciones,
    ROUND(mp.matriculaciones * 100.0 / mt.total, 2) AS cuota_nacional_pct
FROM matriculaciones_provincia mp
JOIN matriculaciones mt
    ON mp.anio = mt.anio
WHERE mp.anio = (SELECT MAX(anio) FROM matriculaciones_provincia)
ORDER BY cuota_nacional_pct DESC
LIMIT 15;

#PROVINCIAS CON MAYOR CRECIMIENTO RECIENTE
WITH base AS (
    SELECT
        provincia,
        anio,
        matriculaciones,
        LAG(matriculaciones) OVER (
            PARTITION BY provincia ORDER BY anio
        ) AS matric_anio_anterior
    FROM matriculaciones_provincia
)
SELECT
    provincia,
    anio,
    matriculaciones,
    matric_anio_anterior,
    ROUND(
        (matriculaciones - matric_anio_anterior) * 100.0 / matric_anio_anterior,
        2
    ) AS crecimiento_pct
FROM base
WHERE anio = (SELECT MAX(anio) FROM matriculaciones_provincia)
  AND matric_anio_anterior IS NOT NULL
ORDER BY crecimiento_pct DESC
LIMIT 15;


#PROVINCIAS CON MAYOR PENETRACION ELECTRICOS (PARQUE)
SELECT
    provincia,
    cero,
    total,
    ROUND(pct_cero * 100, 2) AS pct_cero
FROM distintivo
ORDER BY pct_cero DESC
LIMIT 15;

#PROVINCIAS CON MAYOR PESO DE HIBRIDOS Y ELECTRICOS
SELECT
    provincia,
    cero,
    eco,
    total,
    ROUND((cero + eco) * 100.0 / total, 2) AS pct_baja_emision
FROM distintivo
ORDER BY pct_baja_emision DESC
LIMIT 15;

#GAP ENTRE PROVINCIAS ELECTRIFICADAS Y ENVEJECIDAS
SELECT
    provincia,
    ROUND(pct_cero * 100, 2) AS pct_cero,
    ROUND(pct_eco * 100, 2) AS pct_eco,
    ROUND(pct_sin * 100, 2) AS pct_sin,
    ROUND((pct_cero + pct_eco - pct_sin) * 100, 2) AS indice_transicion
FROM distintivo
ORDER BY indice_transicion DESC;

#COMPARACION ENTRE CRECIMIENTO PARQUE Y CRECIMIENTO MATRICULACION
WITH base AS (
    SELECT
        m.anio,
        m.total AS matric_total,
        p.total AS parque_total,
        LAG(m.total) OVER (ORDER BY m.anio) AS matric_prev,
        LAG(p.total) OVER (ORDER BY p.anio) AS parque_prev
    FROM matriculaciones m
    JOIN parque p
        ON m.anio = p.anio
)
SELECT
    anio,
    ROUND((matric_total - matric_prev) * 100.0 / matric_prev, 2) AS crecimiento_matric_pct,
    ROUND((parque_total - parque_prev) * 100.0 / parque_prev, 2) AS crecimiento_parque_pct
FROM base
WHERE matric_prev IS NOT NULL
ORDER BY anio;

#PESO DEL DIESEL FRENTE A GASOLINA EN AÑOS CLAVES OBSERVADOS
SELECT
    anio,
    ROUND(diesel * 100.0 / total, 2) AS pct_diesel,
    ROUND(gasolina * 100.0 / total, 2) AS pct_gasolina,
    ROUND(otros * 100.0 / total, 2) AS pct_otros
FROM combustible
WHERE anio IN (1995, 2000, 2005, 2010, 2015, 2020, 2025)
ORDER BY anio;

#MEDIA DE MATRICULACIONES POR PROVINCIA Y DISPERSION
SELECT
    anio,
    ROUND(AVG(matriculaciones), 2) AS media_provincial,
    MIN(matriculaciones) AS min_provincial,
    MAX(matriculaciones) AS max_provincial
FROM matriculaciones_provincia
GROUP BY anio
ORDER BY anio;

#TOP PROVINCIAS ACUMULADAS Y CONCENTRACION DE MERCADO
WITH ranking AS (
    SELECT
        provincia,
        matriculaciones,
        ROW_NUMBER() OVER (ORDER BY matriculaciones DESC) AS rn
    FROM matriculaciones_provincia
    WHERE anio = (SELECT MAX(anio) FROM matriculaciones_provincia)
)
SELECT
    SUM(CASE WHEN rn <= 5 THEN matriculaciones ELSE 0 END) AS top_5,
    SUM(CASE WHEN rn <= 10 THEN matriculaciones ELSE 0 END) AS top_10,
    SUM(matriculaciones) AS total_nacional
FROM ranking;

#RESUMEN ULTIMO AÑO 
SELECT
    m.anio,
    m.total AS matriculaciones_totales,
    p.total AS parque_total,
    ROUND(m.total * 100.0 / p.total, 2) AS ratio_renovacion_pct,
    ROUND(c.gasolina * 100.0 / c.total, 2) AS pct_gasolina,
    ROUND(c.diesel * 100.0 / c.total, 2) AS pct_diesel,
    ROUND(c.otros * 100.0 / c.total, 2) AS pct_otros
FROM matriculaciones m
JOIN parque p ON m.anio = p.anio
JOIN combustible c ON m.anio = c.anio
WHERE m.anio = (SELECT MAX(anio) FROM matriculaciones);