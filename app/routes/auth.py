from datetime import datetime, timezone
from functools import wraps
from urllib.parse import urljoin, urlparse

from flask import Blueprint, current_app, flash, g, redirect, render_template, request, session, url_for

from app.extensions import db
from app.models import (
    Actividad, Avance, Curso, Evidencia, Inscripcion, Role,
    InteraccionIA, SesionTrabajo, Usuario,
)


auth_bp = Blueprint("auth", __name__)


def login_requerido(vista):
    @wraps(vista)
    def vista_protegida(*args, **kwargs):
        if g.usuario is None:
            flash("Inicia sesión para acceder al panel.", "info")
            return redirect(url_for("auth.login", next=request.path))
        return vista(*args, **kwargs)

    return vista_protegida


def admin_requerido(vista):
    @wraps(vista)
    @login_requerido
    def vista_administrativa(*args, **kwargs):
        if g.usuario.rol.nombre != "administrador":
            flash("No tienes permisos para entrar a esa sección.", "error")
            return redirect(url_for("auth.panel"))
        return vista(*args, **kwargs)

    return vista_administrativa


def estudiante_requerido(vista):
    @wraps(vista)
    @login_requerido
    def vista_estudiantil(*args, **kwargs):
        if g.usuario.rol.nombre != "estudiante":
            flash("Esta función corresponde únicamente a estudiantes.", "error")
            return redirect(url_for("auth.panel"))
        return vista(*args, **kwargs)

    return vista_estudiantil


def destino_seguro(destino):
    if not destino:
        return False
    base = urlparse(request.host_url)
    objetivo = urlparse(urljoin(request.host_url, destino))
    return objetivo.scheme in {"http", "https"} and base.netloc == objetivo.netloc


def correo_umg_autorizado(correo):
    if "@" not in correo:
        return False
    dominio = correo.rsplit("@", 1)[1].lower()
    return dominio in current_app.config["UMG_ALLOWED_EMAIL_DOMAINS"]


def inscribir_estudiante_en_cursos_activos(usuario):
    """Garantiza acceso del estudiante a todos los cursos activos."""
    cursos = Curso.query.filter_by(activo=True).all()
    existentes = {
        inscripcion.curso_id: inscripcion
        for inscripcion in Inscripcion.query.filter_by(estudiante_id=usuario.id).all()
    }
    for curso in cursos:
        inscripcion = existentes.get(curso.id)
        if inscripcion is None:
            db.session.add(
                Inscripcion(
                    curso_id=curso.id,
                    estudiante_id=usuario.id,
                    estado="activo",
                )
            )
        elif inscripcion.estado != "activo":
            inscripcion.estado = "activo"
    return len(cursos)


def validar_registro_estudiante(datos):
    errores = []
    if not datos["nombres"] or len(datos["nombres"]) > 100:
        errores.append("Escribe tus nombres.")
    if not datos["apellidos"] or len(datos["apellidos"]) > 100:
        errores.append("Escribe tus apellidos.")
    if not correo_umg_autorizado(datos["correo"]):
        dominios = ", ".join(sorted(current_app.config["UMG_ALLOWED_EMAIL_DOMAINS"]))
        errores.append(f"Usa un correo institucional autorizado de Universidad Mariano Gálvez ({dominios}).")
    if Usuario.query.filter_by(correo=datos["correo"]).first():
        errores.append("Ya existe una cuenta con ese correo. Inicia sesión con tu primera contraseña.")
    if len(datos["password"]) < 8:
        errores.append("La contraseña debe tener al menos 8 caracteres.")
    if datos["password"] != datos["confirmar_password"]:
        errores.append("Las contraseñas no coinciden.")
    return errores


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if g.usuario is not None:
        return redirect(url_for("auth.panel"))

    if request.method == "POST":
        correo = request.form.get("correo", "").strip().lower()
        password = request.form.get("password", "")
        usuario = Usuario.query.filter_by(correo=correo).first()

        if usuario is None or not usuario.verificar_contrasena(password):
            flash("El correo o la contraseña no son correctos.", "error")
        elif not usuario.activo:
            flash("Tu cuenta está desactivada. Comunícate con el administrador.", "error")
        else:
            session.clear()
            session["usuario_id"] = usuario.id
            session["csrf_token"] = __import__("secrets").token_urlsafe(32)
            usuario.ultimo_acceso = datetime.now(timezone.utc)
            if usuario.rol.nombre == "estudiante":
                inscribir_estudiante_en_cursos_activos(usuario)
            db.session.commit()
            flash(f"¡Bienvenida, {usuario.nombres}!", "success")
            siguiente = request.args.get("next")
            return redirect(siguiente if destino_seguro(siguiente) else url_for("auth.panel"))

    return render_template("auth/login.html")


@auth_bp.route("/registro", methods=["GET", "POST"])
def registro():
    if g.usuario is not None:
        return redirect(url_for("auth.panel"))

    if request.method == "POST":
        datos = {
            "nombres": request.form.get("nombres", "").strip(),
            "apellidos": request.form.get("apellidos", "").strip(),
            "correo": request.form.get("correo", "").strip().lower(),
            "carnet": request.form.get("carnet", "").strip() or None,
            "password": request.form.get("password", ""),
            "confirmar_password": request.form.get("confirmar_password", ""),
        }
        errores = validar_registro_estudiante(datos)
        rol = Role.query.filter_by(nombre="estudiante").first()
        if rol is None:
            errores.append("El rol estudiante no existe todavía en la base de datos.")
        if Curso.query.filter_by(activo=True).count() == 0:
            errores.append("No hay cursos activos disponibles. Comunícate con la administración.")

        if not errores:
            usuario = Usuario(
                rol_id=rol.id,
                nombres=datos["nombres"],
                apellidos=datos["apellidos"],
                correo=datos["correo"],
                carnet=datos["carnet"],
                activo=True,
            )
            usuario.establecer_contrasena(datos["password"])
            db.session.add(usuario)
            db.session.flush()
            inscribir_estudiante_en_cursos_activos(usuario)
            db.session.commit()
            session.clear()
            session["usuario_id"] = usuario.id
            session["csrf_token"] = __import__("secrets").token_urlsafe(32)
            flash(
                "Cuenta creada e inscripción completada. Conserva esta contraseña para futuros ingresos.",
                "success",
            )
            return redirect(url_for("auth.panel"))

        for error in errores:
            flash(error, "error")

    return render_template(
        "auth/registro.html",
        dominios=sorted(current_app.config["UMG_ALLOWED_EMAIL_DOMAINS"]),
    )


@auth_bp.get("/panel")
@login_requerido
def panel():
    rol = g.usuario.rol.nombre
    if rol == "estudiante":
        inscripciones = Inscripcion.query.filter_by(
            estudiante_id=g.usuario.id, estado="activo"
        ).all()
        cursos_ids = [item.curso_id for item in inscripciones]
        cursos = (
            Curso.query.filter(Curso.id.in_(cursos_ids), Curso.activo.is_(True)).all()
            if cursos_ids else []
        )
        cursos_ids = [item.id for item in cursos]
        cursos_por_id = {item.id: item for item in cursos}
        actividades = (
            Actividad.query.filter(
                Actividad.curso_id.in_(cursos_ids),
                Actividad.estado == "publicada",
            ).order_by(Actividad.fecha_entrega.asc()).all()
            if cursos_ids else []
        )
        actividades_ids = [item.id for item in actividades]
        sesiones = SesionTrabajo.query.filter_by(estudiante_id=g.usuario.id).all()
        sesiones_finalizadas = [item for item in sesiones if item.estado == "finalizada"]
        avances = Avance.query.filter_by(estudiante_id=g.usuario.id).order_by(
            Avance.registrado_en.asc()
        ).all()
        ultimo_avance = {}
        for avance in avances:
            ultimo_avance[avance.actividad_id] = avance

        avance_general = (
            sum(float(ultimo_avance[item.id].porcentaje_declarado)
                if item.id in ultimo_avance else 0 for item in actividades)
            / len(actividades)
            if actividades else 0
        )
        interacciones = InteraccionIA.query.filter_by(usuario_id=g.usuario.id).all()
        evidencias = Evidencia.query.filter_by(estudiante_id=g.usuario.id).all()
        pendientes = [
            {
                "actividad": item,
                "curso": cursos_por_id.get(item.curso_id),
                "avance": float(ultimo_avance[item.id].porcentaje_declarado)
                if item.id in ultimo_avance else 0,
            }
            for item in actividades
            if item.id not in ultimo_avance
            or float(ultimo_avance[item.id].porcentaje_declarado) < 100
        ][:4]
        sesion_activa = next(
            (item for item in sesiones if item.estado in {"activa", "pausada"}), None
        )
        metricas = {
            "cursos": len(cursos),
            "actividades": len(actividades),
            "sesiones": len(sesiones),
            "sesiones_finalizadas": len(sesiones_finalizadas),
            "sesiones_minimas": current_app.config["MIN_SESIONES_TRABAJO"],
            "segundos": sum(item.duracion_segundos or 0 for item in sesiones),
            "avance": round(avance_general, 1),
            "evidencias": len(evidencias),
            "ia_total": len(interacciones),
            "ia_verificadas": sum(
                item.estado in {"completada", "fallida"} for item in interacciones
            ),
        }
        return render_template(
            "panel.html", metricas=metricas, pendientes=pendientes,
            sesion_activa=sesion_activa,
        )

    if rol == "docente":
        cursos = Curso.query.filter_by(docente_id=g.usuario.id).all()
        cursos_ids = [item.id for item in cursos]
        actividades = (
            Actividad.query.filter(Actividad.curso_id.in_(cursos_ids)).all()
            if cursos_ids else []
        )
        actividades_ids = [item.id for item in actividades]
        inscritos = (
            Inscripcion.query.filter(
                Inscripcion.curso_id.in_(cursos_ids), Inscripcion.estado == "activo"
            ).all() if cursos_ids else []
        )
        sesiones = (
            SesionTrabajo.query.filter(SesionTrabajo.actividad_id.in_(actividades_ids)).all()
            if actividades_ids else []
        )
        avances_ids = [
            item.id for item in Avance.query.filter(
                Avance.actividad_id.in_(actividades_ids)
            ).all()
        ] if actividades_ids else []
        metricas = {
            "cursos": len(cursos),
            "estudiantes": len({item.estudiante_id for item in inscritos}),
            "sesiones": len(sesiones),
            "evidencias": Evidencia.query.filter(
                Evidencia.avance_id.in_(avances_ids)
            ).count() if avances_ids else 0,
        }
        return render_template("panel.html", metricas=metricas)

    metricas = {
        "usuarios": Usuario.query.count(),
        "cursos": Curso.query.count(),
        "sesiones": SesionTrabajo.query.count(),
        "evidencias": Evidencia.query.count(),
    }
    return render_template("panel.html", metricas=metricas)


@auth_bp.post("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada correctamente.", "info")
    return redirect(url_for("main.inicio"))
