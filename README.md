# Impulsa

Plataforma web de tesis para registrar actividad de programacion, sesiones de
trabajo, avances, evidencias, entregas y uso responsable de IA.

## Que incluye esta version

- Flask + PostgreSQL mediante `DATABASE_URL`.
- Login con contrasenas cifradas.
- Registro abierto para estudiantes con correo institucional UMG autorizado.
- Primera contrasena persistente: el estudiante la crea una vez y la vuelve a usar.
- Roles de administrador, docente y estudiante.
- Cursos, actividades, inscripciones, sesiones, pausas, avances y evidencias.
- Asistente integrado con Groq y registro/verificacion de interacciones de IA.
- Regla academica: cada estudiante debe completar al menos 4 sesiones de trabajo
  para declarar una actividad al 100%.
- Archivos listos para Render: `render.yaml` y `Procfile`.

## Variables de entorno

En local se puede copiar `.env.example` a `.env`. En Render se configuran desde
el panel del servicio.

```env
SECRET_KEY=crea_una_clave_larga_y_privada
DATABASE_URL=postgresql://...
GROQ_API_KEY=tu_clave_privada_de_groq
GROQ_MODEL=openai/gpt-oss-120b
UMG_ALLOWED_EMAIL_DOMAINS=miumg.edu.gt,umg.edu.gt,mariano.edu.gt
MIN_SESIONES_TRABAJO=4
REGISTRATION_COURSE_CODE=2490-049-A
MAX_UPLOAD_MB=10
```

No subas `.env` ni claves API al repositorio.

## Instalacion local

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
python -m flask --app run.py run --debug --port 5050
```

Abrir:

- `http://127.0.0.1:5050`
- `http://127.0.0.1:5050/login`
- `http://127.0.0.1:5050/registro`

## Verificaciones

```powershell
flask --app run.py verificar-modelos
flask --app run.py verificar-db
python test_groq_patch.py
```

## Crear el primer administrador

```powershell
flask --app run.py crear-admin
```

El comando solicita nombres, apellidos, correo y contrasena. La contrasena se
almacena unicamente como hash seguro.

## Despliegue en Render

1. Subir el proyecto completo a un repositorio.
2. Crear el servicio desde Render usando `render.yaml`, o configurar:
   - Build command: `pip install -r requirements.txt`
   - Start command: `waitress-serve --listen=0.0.0.0:$PORT run:app`
3. Crear PostgreSQL en Render y asignar `DATABASE_URL`.
4. Configurar `SECRET_KEY`, `GROQ_API_KEY`, `GROQ_MODEL`,
   `UMG_ALLOWED_EMAIL_DOMAINS`, `MIN_SESIONES_TRABAJO` y
   `REGISTRATION_COURSE_CODE`.
5. Crear o migrar las tablas existentes antes de usar la aplicacion.

La base de datos debe contener las tablas actuales de Impulsa. No publiques
capturas con contrasenas ni claves privadas.
