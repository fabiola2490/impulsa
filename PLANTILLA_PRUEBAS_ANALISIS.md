# Plantilla de pruebas del análisis

Los registros generados por esta plantilla son sintéticos y sirven únicamente para comprobar el funcionamiento técnico de PostgreSQL, Impulsa y sus reportes. No deben presentarse como respuestas o resultados reales de estudiantes.

## Generar los datos

Desde el Shell del servicio web en Render:

```bash
flask --app run.py generar-datos-analisis --confirmar
```

El comando crea o reemplaza solamente las cuentas `prueba.analisis.01@miumg.edu.gt` a `prueba.analisis.20@miumg.edu.gt`.

- Contraseña temporal común: la que se escriba de forma oculta al ejecutar el comando.
- Estudiantes: 20
- Sesiones finalizadas: 80
- Interacciones de IA: 40
- Evidencias sintéticas: 20

## Revisar en Impulsa

1. Iniciar sesión como administradora o docente.
2. Abrir `https://impulsa-c4c4.onrender.com/reportes`.
3. Seleccionar el curso usado por el comando.
4. Verificar el bloque **Umbral para el análisis del asistente**.
5. Revisar **Seguimiento por estudiante** e **Interacciones registradas con el asistente**.

## Revisar en PostgreSQL y Visual Studio Code

Abrir `consultas_pruebas_analisis.sql` en Visual Studio Code y ejecutar cada consulta contra PostgreSQL. Los resultados esperados son 20 estudiantes, 80 sesiones, 40 interacciones y al menos 15 estudiantes distintos con uso de IA.
