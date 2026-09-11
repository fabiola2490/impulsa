import time
from threading import Lock
from openai import OpenAI, APIStatusError, APIConnectionError

from flask import Blueprint, current_app, flash, g, redirect, render_template, request, url_for
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import Actividad, Curso, Inscripcion, InteraccionIA, SesionTrabajo
from app.routes.auth import estudiante_requerido


ia_bp = Blueprint("ia", __name__, url_prefix="/ia")
_consulta_lock = Lock()
_ultimas_consultas = {}
TIPOS_AYUDA = {
    "explicacion": "Explicación de conceptos",
    "resolucion_error": "Corrección de errores",
    "revision_codigo": "Revisión o generación de código",
    "documentacion": "Documentación",
    "planificacion": "Planificación o estructura",
    "otro": "Otro tipo de ayuda",
}
ESTADOS = {
    "pendiente": "Pendiente de verificar",
    "completada": "Verificada y completada",
    "fallida": "Respuesta descartada o incorrecta",
    "tiempo_agotado": "No resolvió en el tiempo disponible",
}


def actividades_disponibles():
    return (
        Actividad.query.join(Curso, Actividad.curso_id == Curso.id)
        .join(Inscripcion, Inscripcion.curso_id == Curso.id)
        .filter(
            Inscripcion.estudiante_id == g.usuario.id,
            Inscripcion.estado == "activo",
            Curso.activo.is_(True),
            Actividad.estado == "publicada",
        )
        .order_by(Actividad.fecha_entrega.asc())
        .all()
    )


def interaccion_propia(interaccion_id):
    interaccion = db.get_or_404(InteraccionIA, interaccion_id)
    return interaccion if interaccion.usuario_id == g.usuario.id else None


def actividad_disponible(actividad_id):
    """Devuelve la actividad únicamente si pertenece a un curso del estudiante."""
    return next(
        (item for item in actividades_disponibles() if item.id == actividad_id),
        None,
    )


def sesion_reciente(actividad_id):
    return SesionTrabajo.query.filter_by(
        estudiante_id=g.usuario.id, actividad_id=actividad_id
    ).order_by(SesionTrabajo.inicio.desc()).first()


@ia_bp.route("/asistente/<int:actividad_id>", methods=["GET", "POST"])
@estudiante_requerido
def asistente(actividad_id):
    actividad = actividad_disponible(actividad_id)
    if actividad is None:
        flash("La actividad no está disponible para tu cuenta.", "error")
        return redirect(url_for("cursos.lista"))

    if request.method == "POST":
        consulta = request.form.get("consulta", "").strip()
        codigo = request.form.get("codigo_enviado", "").strip()
        tipo = request.form.get("tipo_ayuda", "explicacion")
        if not consulta or len(consulta) > 6000 or len(codigo) > 12000 or tipo not in TIPOS_AYUDA:
            flash("Escribe una consulta de hasta 6,000 caracteres, código de hasta 12,000 y un tipo de ayuda válido.", "error")
        elif not current_app.config.get("GROQ_API_KEY"):
            flash("Falta configurar GROQ_API_KEY en el servidor. No compartas la clave con estudiantes.", "error")
        elif not _consulta_lock.acquire(blocking=False):
            flash("El asistente atiende otra consulta. Espera unos segundos y vuelve a intentar.", "info")
        else:
            try:
                ahora = time.monotonic()
                if ahora - _ultimas_consultas.get(g.usuario.id, -100) < 15:
                    flash("Espera 15 segundos entre consultas.", "info")
                else:
                    _ultimas_consultas[g.usuario.id] = ahora
                    with OpenAI(api_key=current_app.config["GROQ_API_KEY"], base_url="https://api.groq.com/openai/v1", timeout=45.0, max_retries=0) as cliente:
                        resultado = cliente.chat.completions.create(
                            model=current_app.config.get("GROQ_MODEL") or "openai/gpt-oss-120b",
                            messages=[
                                {"role": "system", "content": "Eres el tutor de programación de Impulsa. Responde en español con explicaciones breves y pasos verificables. Ayuda a aprender y pide comprobar el resultado. No afirmes haber ejecutado código."},
                                {"role": "user", "content": f"Actividad: {actividad.titulo}\n{actividad.descripcion or ''}\nConsulta: {consulta}\nCódigo: {codigo}"},
                            ], max_completion_tokens=2048,
                        )
                    respuesta = (resultado.choices[0].message.content or "").strip() if resultado.choices else ""
                    if not respuesta:
                        flash("El proveedor no devolvió texto. Prueba una pregunta más breve.", "error")
                    else:
                        sesion = sesion_reciente(actividad.id)
                        item = InteraccionIA(usuario_id=g.usuario.id, actividad_id=actividad.id,
                            sesion_id=sesion.id if sesion else None, tipo_ayuda=tipo,
                            consulta=consulta, codigo_enviado=codigo or None, respuesta=respuesta,
                            proveedor="Groq", modelo=resultado.model or current_app.config.get("GROQ_MODEL"),
                            estado="pendiente", tiempo_resolucion_segundos=round(time.monotonic()-ahora))
                        db.session.add(item)
                        db.session.commit()
                        flash("Respuesta recibida y guardada. Falta tu verificación.", "success")
                        return redirect(url_for("ia.asistente", actividad_id=actividad.id, nueva=item.id))
            except APIStatusError as exc:
                mensajes = {401: "Groq rechazó la clave. Revisa GROQ_API_KEY en el servidor.",
                    403: "Groq denegó el acceso. Revisa los permisos de tu proyecto con el proveedor.",
                    404: "El modelo configurado no está disponible. Revisa GROQ_MODEL.",
                    429: "Se alcanzó un límite de Groq. Inténtalo más tarde; no es necesario activar pagos."}
                flash(mensajes.get(exc.status_code, "Groq no pudo procesar la consulta. Inténtalo más tarde."), "error")
            except APIConnectionError:
                flash("No se pudo conectar con Groq o se agotó el tiempo de espera. Tu consulta sigue en el formulario.", "error")
            except SQLAlchemyError:
                db.session.rollback()
                flash("La IA respondió, pero no se pudo guardar el registro. Avisa al administrador.", "error")
            except Exception:
                db.session.rollback()
                flash("No se pudo completar la consulta. Avisa al administrador; no compartas claves.", "error")
            finally:
                _consulta_lock.release()
    interacciones = InteraccionIA.query.filter_by(
        usuario_id=g.usuario.id, actividad_id=actividad.id
    ).order_by(InteraccionIA.creado_en.desc()).limit(20).all()
    return render_template(
        "ia/asistente.html", actividad=actividad, interacciones=interacciones,
        tipos=TIPOS_AYUDA, api_configurada=bool(current_app.config.get("GROQ_API_KEY")),
    )

@ia_bp.post("/asistente/interacciones/<int:interaccion_id>/validar")
@estudiante_requerido
def validar_respuesta(interaccion_id):
    interaccion = interaccion_propia(interaccion_id)
    if interaccion is None:
        flash("No tienes acceso a esa interacción.", "error")
        return redirect(url_for("ia.lista"))
    estado = request.form.get("estado", "")
    verificacion = request.form.get("verificacion", "").strip()
    if estado not in {"completada", "fallida"} or not verificacion:
        flash("Selecciona el resultado y explica cómo verificaste la respuesta.", "error")
    else:
        interaccion.estado = estado
        interaccion.codigo_modificado = request.form.get("codigo_modificado", "").strip() or None
        interaccion.error_tecnico = verificacion
        try:
            db.session.commit()
            flash("Verificación guardada correctamente.", "success")
        except SQLAlchemyError:
            db.session.rollback()
            flash("No fue posible guardar la verificación.", "error")
    return redirect(url_for("ia.asistente", actividad_id=interaccion.actividad_id))


@ia_bp.get("")
@estudiante_requerido
def lista():
    interacciones = InteraccionIA.query.filter_by(usuario_id=g.usuario.id).order_by(
        InteraccionIA.creado_en.desc()
    ).all()
    ids = [item.actividad_id for item in interacciones if item.actividad_id]
    actividades = {
        actividad.id: actividad
        for actividad in Actividad.query.filter(Actividad.id.in_(ids or [-1])).all()
    }
    return render_template(
        "ia/lista.html", interacciones=interacciones,
        actividades=actividades, tipos=TIPOS_AYUDA, estados=ESTADOS,
    )


@ia_bp.route("/nueva", methods=["GET", "POST"])
@estudiante_requerido
def nueva():
    actividades = actividades_disponibles()
    if request.method == "POST":
        datos, errores = validar_formulario(actividades)
        if not errores:
            interaccion = InteraccionIA(usuario_id=g.usuario.id, **datos)
            try:
                db.session.add(interaccion)
                db.session.commit()
                flash("Uso de IA registrado responsablemente.", "success")
                return redirect(url_for("ia.lista"))
            except SQLAlchemyError:
                db.session.rollback()
                errores.append("No fue posible guardar el registro. Revisa los datos e inténtalo nuevamente.")
        for error in errores:
            flash(error, "error")
    actividad_preseleccionada = request.args.get("actividad_id", type=int)
    return render_template(
        "ia/formulario.html", interaccion=None, actividades=actividades,
        tipos=TIPOS_AYUDA, estados=ESTADOS,
        actividad_preseleccionada=actividad_preseleccionada,
    )


@ia_bp.route("/<int:interaccion_id>/editar", methods=["GET", "POST"])
@estudiante_requerido
def editar(interaccion_id):
    interaccion = interaccion_propia(interaccion_id)
    if interaccion is None:
        flash("No tienes acceso a ese registro.", "error")
        return redirect(url_for("ia.lista"))
    actividades = actividades_disponibles()
    if request.method == "POST":
        datos, errores = validar_formulario(actividades)
        if not errores:
            try:
                for campo, valor in datos.items():
                    setattr(interaccion, campo, valor)
                db.session.commit()
                flash("Registro de IA actualizado correctamente.", "success")
                return redirect(url_for("ia.lista"))
            except SQLAlchemyError:
                db.session.rollback()
                errores.append("No fue posible actualizar el registro. Revisa los datos.")
        for error in errores:
            flash(error, "error")
    return render_template(
        "ia/formulario.html", interaccion=interaccion, actividades=actividades,
        tipos=TIPOS_AYUDA, estados=ESTADOS, actividad_preseleccionada=None,
    )


def validar_formulario(actividades):
    errores = []
    permitidas = {actividad.id for actividad in actividades}
    actividad_id = request.form.get("actividad_id", type=int)
    if actividad_id not in permitidas:
        actividad_id = None
        errores.append("Selecciona una actividad disponible.")
    tipo_ayuda = request.form.get("tipo_ayuda", "")
    if tipo_ayuda not in TIPOS_AYUDA:
        errores.append("Selecciona un tipo de ayuda válido.")
    estado = request.form.get("estado", "pendiente")
    if estado not in ESTADOS:
        errores.append("Selecciona un estado válido.")
    consulta = request.form.get("consulta", "").strip()
    if not consulta:
        errores.append("El prompt o consulta es obligatorio.")
    proveedor = request.form.get("proveedor", "").strip() or None
    modelo = request.form.get("modelo", "").strip() or None
    if proveedor and len(proveedor) > 40:
        errores.append("El nombre de la herramienta no puede superar 40 caracteres.")
    if modelo and len(modelo) > 80:
        errores.append("El modelo no puede superar 80 caracteres.")
    try:
        minutos = float(request.form.get("tiempo_resolucion_minutos", "0") or 0)
        if not 0 <= minutos <= 1440:
            raise ValueError
        tiempo_segundos = round(minutos * 60)
    except ValueError:
        tiempo_segundos = None
        errores.append("El tiempo debe estar entre 0 y 1,440 minutos.")

    sesion = None
    if actividad_id:
        sesion = SesionTrabajo.query.filter_by(
            estudiante_id=g.usuario.id, actividad_id=actividad_id, estado="finalizada"
        ).order_by(SesionTrabajo.fin.desc()).first()
    datos = {
        "actividad_id": actividad_id,
        "sesion_id": sesion.id if sesion else None,
        "tipo_ayuda": tipo_ayuda,
        "consulta": consulta,
        "codigo_enviado": request.form.get("codigo_enviado", "").strip() or None,
        "respuesta": request.form.get("respuesta", "").strip() or None,
        "codigo_modificado": request.form.get("codigo_modificado", "").strip() or None,
        "proveedor": proveedor,
        "modelo": modelo,
        "estado": estado,
        "tiempo_resolucion_segundos": tiempo_segundos,
        "error_tecnico": request.form.get("verificacion", "").strip() or None,
    }
    return datos, errores
