import hashlib
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from flask import (
    Blueprint, current_app, flash, g, redirect, render_template,
    request, send_from_directory, url_for,
)
from urllib.parse import urlparse
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import Actividad, Avance, Curso, Evidencia, Inscripcion, Pausa, SesionTrabajo
from app.routes.auth import estudiante_requerido


trabajo_bp = Blueprint("trabajo", __name__, url_prefix="/trabajo")
EXTENSIONES_PERMITIDAS = {"png", "jpg", "jpeg", "pdf", "doc", "docx", "zip", "txt"}


def ahora():
    return datetime.now(timezone.utc)


def actividad_autorizada(actividad_id):
    actividad = db.get_or_404(Actividad, actividad_id)
    curso = db.session.get(Curso, actividad.curso_id)
    inscripcion = Inscripcion.query.filter_by(
        curso_id=curso.id, estudiante_id=g.usuario.id, estado="activo"
    ).first()
    if not inscripcion or not curso.activo or actividad.estado != "publicada":
        flash("La actividad no está disponible para tu cuenta.", "error")
        return None, None
    return actividad, curso


def sesion_del_estudiante(sesion_id, actividad_id=None):
    sesion = db.get_or_404(SesionTrabajo, sesion_id)
    if sesion.estudiante_id != g.usuario.id:
        return None
    if actividad_id is not None and sesion.actividad_id != actividad_id:
        return None
    return sesion


def cerrar_pausa_abierta(sesion, momento):
    pausa = Pausa.query.filter_by(sesion_id=sesion.id, fin=None).first()
    if pausa:
        pausa.fin = momento
        pausa.duracion_segundos = max(0, int((momento - pausa.inicio).total_seconds()))
        sesion.pausas_segundos = (sesion.pausas_segundos or 0) + pausa.duracion_segundos
    return pausa


def sesiones_finalizadas_actividad(actividad_id):
    return SesionTrabajo.query.filter_by(
        estudiante_id=g.usuario.id,
        actividad_id=actividad_id,
        estado="finalizada",
    ).count()


@trabajo_bp.get("/actividades/<int:actividad_id>")
@estudiante_requerido
def actividad(actividad_id):
    actividad, curso = actividad_autorizada(actividad_id)
    if actividad is None:
        return redirect(url_for("cursos.lista"))
    sesion_activa = SesionTrabajo.query.filter(
        SesionTrabajo.estudiante_id == g.usuario.id,
        SesionTrabajo.actividad_id == actividad.id,
        SesionTrabajo.estado.in_(["activa", "pausada"]),
    ).order_by(SesionTrabajo.inicio.desc()).first()
    pausa_abierta = None
    if sesion_activa:
        pausa_abierta = Pausa.query.filter_by(sesion_id=sesion_activa.id, fin=None).first()
    sesiones = SesionTrabajo.query.filter_by(
        estudiante_id=g.usuario.id, actividad_id=actividad.id
    ).order_by(SesionTrabajo.inicio.desc()).limit(10).all()
    sesiones_finalizadas = sesiones_finalizadas_actividad(actividad.id)
    avances = Avance.query.filter_by(
        estudiante_id=g.usuario.id, actividad_id=actividad.id
    ).order_by(Avance.registrado_en.desc()).limit(10).all()
    return render_template(
        "trabajo/actividad.html", actividad=actividad, curso=curso,
        sesion_activa=sesion_activa, pausa_abierta=pausa_abierta,
        sesiones=sesiones, avances=avances,
        sesiones_finalizadas=sesiones_finalizadas,
        sesiones_minimas=current_app.config["MIN_SESIONES_TRABAJO"],
    )


@trabajo_bp.post("/actividades/<int:actividad_id>/iniciar")
@estudiante_requerido
def iniciar(actividad_id):
    actividad, _ = actividad_autorizada(actividad_id)
    if actividad is None:
        return redirect(url_for("cursos.lista"))
    objetivo = request.form.get("objetivo", "").strip()
    if not objetivo:
        flash("Escribe el objetivo de la sesión.", "error")
        return redirect(url_for("trabajo.actividad", actividad_id=actividad.id))
    existente = SesionTrabajo.query.filter(
        SesionTrabajo.estudiante_id == g.usuario.id,
        SesionTrabajo.estado.in_(["activa", "pausada"]),
    ).first()
    if existente:
        flash("Ya tienes una sesión abierta. Finalízala antes de iniciar otra.", "error")
        return redirect(url_for("trabajo.actividad", actividad_id=existente.actividad_id))
    sesion = SesionTrabajo(
        estudiante_id=g.usuario.id, actividad_id=actividad.id,
        inicio=ahora(), objetivo=objetivo, estado="activa", pausas_segundos=0,
    )
    db.session.add(sesion)
    db.session.commit()
    flash("Sesión iniciada. ¡Éxitos con tu objetivo!", "success")
    return redirect(url_for("trabajo.actividad", actividad_id=actividad.id))


@trabajo_bp.post("/sesiones/<int:sesion_id>/pausar")
@estudiante_requerido
def pausar(sesion_id):
    sesion = sesion_del_estudiante(sesion_id)
    if sesion is None:
        flash("La sesión no está disponible.", "error")
        return redirect(url_for("cursos.lista"))
    if sesion.estado != "activa":
        flash("La sesión no puede pausarse.", "error")
    elif Pausa.query.filter_by(sesion_id=sesion.id, fin=None).first():
        flash("La sesión ya está pausada.", "error")
    else:
        db.session.add(Pausa(sesion_id=sesion.id, inicio=ahora()))
        sesion.estado = "pausada"
        db.session.commit()
        flash("Sesión pausada.", "info")
    return redirect(url_for("trabajo.actividad", actividad_id=sesion.actividad_id))


@trabajo_bp.post("/sesiones/<int:sesion_id>/continuar")
@estudiante_requerido
def continuar(sesion_id):
    sesion = sesion_del_estudiante(sesion_id)
    if sesion is None:
        flash("La sesión no está disponible.", "error")
        return redirect(url_for("cursos.lista"))
    if sesion.estado != "pausada":
        flash("La sesión no puede continuar.", "error")
    else:
        cerrar_pausa_abierta(sesion, ahora())
        sesion.estado = "activa"
        db.session.commit()
        flash("Sesión reanudada.", "success")
    return redirect(url_for("trabajo.actividad", actividad_id=sesion.actividad_id))


@trabajo_bp.post("/sesiones/<int:sesion_id>/finalizar")
@estudiante_requerido
def finalizar(sesion_id):
    sesion = sesion_del_estudiante(sesion_id)
    if sesion is None or sesion.estado not in {"activa", "pausada"}:
        flash("La sesión ya fue finalizada o no está disponible.", "error")
        return redirect(url_for("cursos.lista"))
    fin = ahora()
    cerrar_pausa_abierta(sesion, fin)
    sesion.fin = fin
    sesion.resumen = request.form.get("resumen", "").strip() or None
    sesion.duracion_segundos = max(
        0, int((fin - sesion.inicio).total_seconds()) - (sesion.pausas_segundos or 0)
    )
    sesion.estado = "finalizada"
    db.session.commit()
    flash("Sesión finalizada. Registra el avance conseguido.", "success")
    return redirect(url_for("trabajo.registrar_avance", sesion_id=sesion.id))


@trabajo_bp.route("/sesiones/<int:sesion_id>/avance", methods=["GET", "POST"])
@estudiante_requerido
def registrar_avance(sesion_id):
    sesion = sesion_del_estudiante(sesion_id)
    if sesion is None or sesion.estado != "finalizada":
        flash("Primero debes finalizar la sesión.", "error")
        return redirect(url_for("cursos.lista"))
    actividad, curso = actividad_autorizada(sesion.actividad_id)
    if actividad is None:
        return redirect(url_for("cursos.lista"))
    existente = Avance.query.filter_by(sesion_id=sesion.id).first()
    if existente:
        flash("Esta sesión ya tiene un avance registrado.", "info")
        return redirect(url_for("trabajo.actividad", actividad_id=actividad.id))
    if request.method == "POST":
        descripcion = request.form.get("descripcion", "").strip()
        dificultades = request.form.get("dificultades", "").strip() or None
        siguiente_paso = request.form.get("siguiente_paso", "").strip() or None
        errores = []
        try:
            porcentaje = Decimal(request.form.get("porcentaje_declarado", ""))
            if not Decimal("0") <= porcentaje <= Decimal("100"):
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            porcentaje = None
            errores.append("El porcentaje debe estar entre 0 y 100.")
        if not descripcion:
            errores.append("Describe el avance que conseguiste.")
        sesiones_finalizadas = sesiones_finalizadas_actividad(actividad.id)
        if (
            porcentaje == Decimal("100")
            and sesiones_finalizadas < current_app.config["MIN_SESIONES_TRABAJO"]
        ):
            errores.append(
                "Para declarar la actividad al 100%, completa al menos "
                f"{current_app.config['MIN_SESIONES_TRABAJO']} sesiones de trabajo."
            )
        if not errores:
            avance = Avance(
                actividad_id=actividad.id, estudiante_id=g.usuario.id,
                sesion_id=sesion.id, descripcion=descripcion,
                porcentaje_declarado=porcentaje, dificultades=dificultades,
                siguiente_paso=siguiente_paso,
            )
            db.session.add(avance)
            db.session.commit()
            flash("Avance registrado correctamente.", "success")
            return redirect(url_for("trabajo.actividad", actividad_id=actividad.id))
        for error in errores:
            flash(error, "error")
    return render_template(
        "trabajo/avance_form.html", sesion=sesion,
        actividad=actividad, curso=curso,
    )


def avance_del_estudiante(avance_id):
    avance = db.get_or_404(Avance, avance_id)
    return avance if avance.estudiante_id == g.usuario.id else None


@trabajo_bp.route("/avances/<int:avance_id>/evidencias", methods=["GET", "POST"])
@estudiante_requerido
def evidencias(avance_id):
    avance = avance_del_estudiante(avance_id)
    if avance is None:
        flash("No tienes acceso a ese avance.", "error")
        return redirect(url_for("cursos.lista"))
    actividad, curso = actividad_autorizada(avance.actividad_id)
    if actividad is None:
        return redirect(url_for("cursos.lista"))

    if request.method == "POST":
        tipo = request.form.get("tipo", "archivo")
        descripcion = request.form.get("descripcion", "").strip() or None
        errores = []
        evidencia = None
        if tipo == "enlace":
            enlace = request.form.get("enlace", "").strip()
            analizado = urlparse(enlace)
            if analizado.scheme not in {"http", "https"} or not analizado.netloc:
                errores.append("Escribe un enlace válido que comience con http:// o https://.")
            else:
                nombre = request.form.get("nombre_enlace", "").strip() or analizado.netloc
                evidencia = Evidencia(
                    avance_id=avance.id, estudiante_id=g.usuario.id,
                    nombre_archivo=nombre[:255], tipo_archivo="enlace",
                    ubicacion_archivo=enlace, tamano_bytes=None,
                    hash_archivo=hashlib.sha256(enlace.encode("utf-8")).hexdigest(),
                    descripcion=descripcion,
                )
        elif tipo == "archivo":
            archivo = request.files.get("archivo")
            if archivo is None or not archivo.filename:
                errores.append("Selecciona un archivo.")
            else:
                nombre_original = secure_filename(archivo.filename)
                extension = nombre_original.rsplit(".", 1)[-1].lower() if "." in nombre_original else ""
                if extension not in EXTENSIONES_PERMITIDAS:
                    errores.append("Formato no permitido. Usa PNG, JPG, PDF, Word, ZIP o TXT.")
                else:
                    contenido = archivo.read()
                    if not contenido:
                        errores.append("El archivo está vacío.")
                    else:
                        nombre_guardado = f"{uuid.uuid4().hex}.{extension}"
                        ruta = os.path.join(current_app.config["UPLOAD_FOLDER"], nombre_guardado)
                        with open(ruta, "wb") as destino:
                            destino.write(contenido)
                        evidencia = Evidencia(
                            avance_id=avance.id, estudiante_id=g.usuario.id,
                            nombre_archivo=nombre_original[:255],
                            tipo_archivo=archivo.mimetype or "application/octet-stream",
                            ubicacion_archivo=nombre_guardado,
                            tamano_bytes=len(contenido),
                            hash_archivo=hashlib.sha256(contenido).hexdigest(),
                            descripcion=descripcion,
                        )
        else:
            errores.append("Tipo de evidencia no válido.")

        if evidencia and not errores:
            db.session.add(evidencia)
            db.session.commit()
            flash("Evidencia guardada correctamente.", "success")
            return redirect(url_for("trabajo.evidencias", avance_id=avance.id))
        for error in errores:
            flash(error, "error")

    lista = Evidencia.query.filter_by(avance_id=avance.id).order_by(
        Evidencia.cargado_en.desc()
    ).all()
    return render_template(
        "trabajo/evidencias.html", avance=avance, actividad=actividad,
        curso=curso, evidencias=lista,
    )


@trabajo_bp.get("/evidencias/<int:evidencia_id>/descargar")
@estudiante_requerido
def descargar_evidencia(evidencia_id):
    evidencia = db.get_or_404(Evidencia, evidencia_id)
    if evidencia.estudiante_id != g.usuario.id or evidencia.tipo_archivo == "enlace":
        flash("No tienes acceso a ese archivo.", "error")
        return redirect(url_for("cursos.lista"))
    return send_from_directory(
        current_app.config["UPLOAD_FOLDER"], evidencia.ubicacion_archivo,
        as_attachment=True, download_name=evidencia.nombre_archivo,
    )
