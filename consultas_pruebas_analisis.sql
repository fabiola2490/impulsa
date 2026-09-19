-- Datos sintéticos de prueba: no corresponden a participantes reales.
-- Ejecutar en PostgreSQL para verificar el umbral del análisis.

SELECT COUNT(*) AS estudiantes_sinteticos
FROM usuarios
WHERE correo LIKE 'prueba.analisis.%@miumg.edu.gt';

SELECT COUNT(*) AS sesiones_validas
FROM sesiones_trabajo s
JOIN usuarios u ON u.id = s.estudiante_id
WHERE u.correo LIKE 'prueba.analisis.%@miumg.edu.gt'
  AND s.estado = 'finalizada'
  AND s.duracion_segundos > 0;

SELECT COUNT(*) AS interacciones_ia,
       COUNT(DISTINCT i.usuario_id) AS estudiantes_con_ia
FROM interacciones_ia i
JOIN usuarios u ON u.id = i.usuario_id
WHERE u.correo LIKE 'prueba.analisis.%@miumg.edu.gt';

WITH resumen_sesiones AS (
    SELECT estudiante_id,
           COUNT(*) AS sesiones,
           SUM(COALESCE(duracion_segundos, 0)) AS segundos
    FROM sesiones_trabajo
    GROUP BY estudiante_id
), resumen_ia AS (
    SELECT usuario_id, COUNT(*) AS interacciones_ia
    FROM interacciones_ia
    GROUP BY usuario_id
)
SELECT u.correo,
       COALESCE(s.sesiones, 0) AS sesiones,
       COALESCE(i.interacciones_ia, 0) AS interacciones_ia,
       ROUND(COALESCE(s.segundos, 0) / 3600.0, 2) AS horas
FROM usuarios u
LEFT JOIN resumen_sesiones s ON s.estudiante_id = u.id
LEFT JOIN resumen_ia i ON i.usuario_id = u.id
WHERE u.correo LIKE 'prueba.analisis.%@miumg.edu.gt'
ORDER BY u.correo;
