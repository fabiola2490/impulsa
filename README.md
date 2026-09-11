# Impulsa

Plataforma académica en Python y Flask para cursos, actividades, sesiones de
trabajo, avances, evidencias y registro del uso de inteligencia artificial.

## Estado

Código preparado para revisión y publicación. **No desplegar todavía para uso
real:** el almacenamiento de evidencias sigue siendo local. En Render gratuito
esos archivos no son persistentes. Falta integrar almacenamiento privado externo,
migrar la base de datos existente y comprobar la aplicación desplegada.

Este repositorio no incluye cuentas, contraseñas, base de datos, evidencias ni
scripts privados de restauración. No proporciona usuarios predeterminados.

## Desarrollo

Requiere Python 3.12 y PostgreSQL con el esquema de Impulsa.

1. Crear un entorno virtual e instalar `requirements.txt`.
2. Copiar `.env.example` a `.env` y configurar valores privados.
3. Ejecutar `python -m flask --app run verificar-db` para comprobar la conexión.
4. Iniciar con `python -m waitress --listen=127.0.0.1:5050 run:app`.

Nunca recrear ni sobrescribir la base existente para probar el código.

## Pruebas sin datos reales

`python -m unittest test_groq_patch test_publicacion`

Estas pruebas no certifican la migración ni el rendimiento en la nube.

## Preparación de Render (pendiente)

- Servicio Python; comando de instalación: `pip install -r requirements.txt`.
- Inicio: `waitress-serve --listen=0.0.0.0:$PORT --threads=8 run:app`.
- Guardar SECRET_KEY y DATABASE_URL solo en las variables privadas del servidor.
- Usar PostgreSQL con SSL y almacenamiento privado persistente de evidencias.
- Cambiar las contraseñas de demostración antes de permitir acceso externo.
- Probar permisos, carga/descarga y persistencia después de un reinicio.

No publicar archivos `.env`, copias de seguridad ni listados de estudiantes.
