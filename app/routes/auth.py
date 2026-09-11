from datetime import datetime, timezone
from functools import wraps
from urllib.parse import urljoin, urlparse

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from app.extensions import db
from app.models import (
    Actividad, Avance, Curso, Evidencia, Inscripcion,
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
            db.session.commit()
            flash(f"¡Bienvenida, {usuario.nombres}!", "success")
            siguiente = request.args.get("next")
            return redirect(siguiente if destino_seguro(siguiente) else url_for("auth.panel"))

    return render_template("auth/login.html")


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
