import click
import os
import secrets
from flask import Flask, abort, g, request, session
from markdown_it import MarkdownIt
from markupsafe import Markup
from sqlalchemy import text
from werkzeug.security import generate_password_hash

from config import Config
from app.extensions import db


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_UPLOAD_MB", "10")) * 1024 * 1024
    app.config.setdefault("UPLOAD_FOLDER", os.path.join(app.instance_path, "uploads"))
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)

    markdown = MarkdownIt("commonmark", {"html": False, "linkify": False})

    @app.template_filter("markdown_seguro")
    def markdown_seguro(texto):
        """Presenta Markdown sin permitir HTML introducido por el modelo."""
        return Markup(markdown.render(texto or ""))

    @app.template_filter("duracion_legible")
    def duracion_legible(segundos):
        """Muestra tiempos cortos sin redondearlos incorrectamente a 0.0 horas."""
        total = max(0, int(segundos or 0))
        if total < 60:
            return f"{total} s"
        horas, resto = divmod(total, 3600)
        minutos = resto // 60
        if horas and minutos:
            return f"{horas} h {minutos} min"
        if horas:
            return f"{horas} h"
        return f"{minutos} min"

    from app.models import Role, Usuario
    from app.routes.admin import admin_bp
    from app.routes.auth import auth_bp
    from app.routes.cursos import cursos_bp
    from app.routes.trabajo import trabajo_bp
    from app.routes.ia import ia_bp
    from app.routes.main import main_bp
    from app.routes.reportes import reportes_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(cursos_bp)
    app.register_blueprint(trabajo_bp)
    app.register_blueprint(ia_bp)
    app.register_blueprint(reportes_bp)

    @app.before_request
    def cargar_usuario_actual():
        usuario_id = session.get("usuario_id")
        g.usuario = db.session.get(Usuario, usuario_id) if usuario_id else None

    @app.context_processor
    def compartir_usuario_actual():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(32)
        return {
            "usuario_actual": g.get("usuario"),
            "csrf_token": session["csrf_token"],
        }

    @app.before_request
    def validar_csrf():
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            token = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
            if not token or not secrets.compare_digest(token, session.get("csrf_token", "")):
                abort(400, description="La solicitud expiró. Actualiza la página e inténtalo de nuevo.")

    @app.errorhandler(413)
    def archivo_demasiado_grande(_error):
        return "El archivo supera el límite permitido de 10 MB.", 413

    @app.cli.command("verificar-db")
    def verificar_db():
        """Comprueba la conexión sin crear ni modificar tablas."""
        nombre = db.session.execute(text("SELECT current_database()"))
        click.echo(f"Conexión correcta con: {nombre.scalar_one()}")

    @app.cli.command("verificar-modelos")
    def verificar_modelos():
        """Comprueba que Flask tenga mapeadas las 19 tablas de Impulsa."""
        tablas = sorted(db.metadata.tables)
        click.echo(f"Modelos cargados: {len(tablas)}")
        for tabla in tablas:
            click.echo(f"- {tabla}")

    @app.cli.command("crear-admin")
    @click.option("--nombres", prompt="Nombres")
    @click.option("--apellidos", prompt="Apellidos")
    @click.option("--correo", prompt="Correo")
    @click.password_option(confirmation_prompt=True)
    def crear_admin(nombres, apellidos, correo, password):
        """Crea el primer administrador con contraseña cifrada."""
        correo = correo.strip().lower()
        if Usuario.query.filter_by(correo=correo).first():
            raise click.ClickException("Ya existe un usuario con ese correo.")

        rol = Role.query.filter_by(nombre="administrador").first()
        if rol is None:
            raise click.ClickException("No existe el rol administrador en la base de datos.")

        usuario = Usuario(
            rol_id=rol.id,
            nombres=nombres.strip(),
            apellidos=apellidos.strip(),
            correo=correo,
            contrasena_hash=generate_password_hash(password),
            activo=True,
        )
        db.session.add(usuario)
        db.session.commit()
        click.echo(f"Administrador creado correctamente: {correo}")

    return app
