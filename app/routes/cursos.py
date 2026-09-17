from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from flask import Blueprint, flash, g, redirect, render_template, request, url_for
from sqlalchemy import or_

from app.extensions import db
from app.models import Actividad, Curso, Inscripcion, Role, Usuario
from app.routes.auth import (
    admin_requerido,
    inscribir_estudiante_en_cursos_activos,
    login_requerido,
)


cursos_bp = Blueprint("cursos", __name__, url_prefix="/cursos")


def es_admin():
    return g.usuario.rol.nombre == "administrador"


def puede_ver_curso(curso):
    if es_admin() or curso.docente_id == g.usuario.id:
        return True
    return Inscripcion.query.filter_by(
        curso_id=curso.id, estudiante_id=g.usuario.id, estado="activo"
    ).first() is not None


def puede_gestionar_curso(curso):
    return es_admin() or (
        g.usuario.rol.nombre == "docente" and curso.docente_id == g.usuario.id
    )


def obtener_docentes():
    return (
        Usuario.query.join(Role)
        .filter(Role.nombre == "docente", Usuario.activo.is_(True))
        .order_by(Usuario.nombres, Usuario.apellidos)
        .all()
    )


@cursos_bp.get("")
@login_requerido
def lista():
    rol = g.usuario.rol.nombre
    if rol == "estudiante":
        inscribir_estudiante_en_cursos_activos(g.usuario)
        db.session.commit()
    consulta = Curso.query.order_by(Curso.anio.desc(), Curso.nombre)
    if rol == "docente":
        consulta = consulta.filter_by(docente_id=g.usuario.id)
    elif rol == "estudiante":
        consulta = consulta.join(Inscripcion).filter(
            Inscripcion.estudiante_id == g.usuario.id,
            Inscripcion.estado == "activo",
            Curso.activo.is_(True),
        )
    cursos = consulta.all()
    docentes = {
        usuario.id: usuario
        for usuario in Usuario.query.filter(
            Usuario.id.in_([curso.docente_id for curso in cursos] or [-1])
        ).all()
    }
    return render_template("cursos/lista.html", cursos=cursos, docentes=docentes)


@cursos_bp.route("/nuevo", methods=["GET", "POST"])
@admin_requerido
def nuevo():
    docentes = obtener_docentes()
    if request.method == "POST":
        datos, errores = validar_curso()
        if not docentes:
            errores.append("Primero debes registrar al menos un usuario con rol docente.")
        if not errores:
            curso = Curso(**datos, activo=True)
            db.session.add(curso)
            db.session.commit()
            flash(f"Curso {curso.nombre} creado correctamente.", "success")
            return redirect(url_for("cursos.detalle", curso_id=curso.id))
        for error in errores:
            flash(error, "error")
    return render_template("cursos/formulario.html", curso=None, docentes=docentes)


@cursos_bp.route("/<int:curso_id>/editar", methods=["GET", "POST"])
@admin_requerido
def editar(curso_id):
    curso = db.get_or_404(Curso, curso_id)
    docentes = obtener_docentes()
    if request.method == "POST":
        datos, errores = validar_curso(curso)
        if not errores:
            for campo, valor in datos.items():
                setattr(curso, campo, valor)
            db.session.commit()
            flash("Curso actualizado correctamente.", "success")
            return redirect(url_for("cursos.detalle", curso_id=curso.id))
        for error in errores:
            flash(error, "error")
    return render_template("cursos/formulario.html", curso=curso, docentes=docentes)


def validar_curso(curso=None):
    datos = {
        "codigo": request.form.get("codigo", "").strip().upper(),
        "nombre": request.form.get("nombre", "").strip(),
        "descripcion": request.form.get("descripcion", "").strip() or None,
        "ciclo": request.form.get("ciclo", "").strip() or None,
    }
    errores = []
    try:
        datos["docente_id"] = int(request.form.get("docente_id", ""))
    except ValueError:
        datos["docente_id"] = None
    try:
        datos["anio"] = int(request.form.get("anio", ""))
    except ValueError:
        datos["anio"] = None
    if not datos["codigo"] or len(datos["codigo"]) > 30:
        errores.append("Escribe un código válido de máximo 30 caracteres.")
    if not datos["nombre"] or len(datos["nombre"]) > 150:
        errores.append("Escribe un nombre válido de máximo 150 caracteres.")
    if not datos["anio"] or not 2020 <= datos["anio"] <= 2100:
        errores.append("Escribe un año válido.")
    docente = db.session.get(Usuario, datos["docente_id"]) if datos["docente_id"] else None
    if docente is None or docente.rol.nombre != "docente" or not docente.activo:
        errores.append("Selecciona un docente activo.")
    existente = Curso.query.filter_by(codigo=datos["codigo"]).first()
    if existente and (curso is None or existente.id != curso.id):
        errores.append("Ya existe un curso con ese código.")
    return datos, errores


@cursos_bp.get("/<int:curso_id>")
@login_requerido
def detalle(curso_id):
    curso = db.get_or_404(Curso, curso_id)
    if not puede_ver_curso(curso):
        flash("No tienes acceso a ese curso.", "error")
        return redirect(url_for("cursos.lista"))
    docente = db.session.get(Usuario, curso.docente_id)
    actividades = Actividad.query.filter_by(curso_id=curso.id).order_by(
        Actividad.fecha_entrega.asc()
    )
    if g.usuario.rol.nombre == "estudiante":
        actividades = actividades.filter_by(estado="publicada")
    actividades = actividades.all()
    total_inscritos = Inscripcion.query.filter_by(curso_id=curso.id, estado="activo").count()
    return render_template(
        "cursos/detalle.html", curso=curso, docente=docente,
        actividades=actividades, puede_gestionar=puede_gestionar_curso(curso),
        total_inscritos=total_inscritos,
    )


@cursos_bp.get("/<int:curso_id>/inscripciones")
@admin_requerido
def inscripciones(curso_id):
    curso = db.get_or_404(Curso, curso_id)
    buscar = request.args.get("buscar", "").strip()
    consulta = Usuario.query.join(Role).filter(
        Role.nombre == "estudiante", Usuario.activo.is_(True)
    )
    if buscar:
        patron = f"%{buscar}%"
        consulta = consulta.filter(
            or_(
                Usuario.nombres.ilike(patron),
                Usuario.apellidos.ilike(patron),
                Usuario.correo.ilike(patron),
                Usuario.carnet.ilike(patron),
            )
        )
    estudiantes = consulta.order_by(Usuario.nombres, Usuario.apellidos).all()
    registros = {
        inscripcion.estudiante_id: inscripcion
        for inscripcion in Inscripcion.query.filter_by(curso_id=curso.id).all()
    }
    total_activos = sum(1 for registro in registros.values() if registro.estado == "activo")
    return render_template(
        "cursos/inscripciones.html", curso=curso, estudiantes=estudiantes,
        registros=registros, buscar=buscar, total_activos=total_activos,
    )


@cursos_bp.post("/<int:curso_id>/inscripciones/<int:estudiante_id>/estado")
@admin_requerido
def cambiar_inscripcion(curso_id, estudiante_id):
    curso = db.get_or_404(Curso, curso_id)
    estudiante = db.get_or_404(Usuario, estudiante_id)
    if estudiante.rol.nombre != "estudiante" or not estudiante.activo:
        flash("Solo puedes inscribir cuentas estudiantiles activas.", "error")
        return redirect(url_for("cursos.inscripciones", curso_id=curso.id))

    inscripcion = Inscripcion.query.filter_by(
        curso_id=curso.id, estudiante_id=estudiante.id
    ).first()
    if inscripcion is None:
        inscripcion = Inscripcion(
            curso_id=curso.id, estudiante_id=estudiante.id, estado="activo"
        )
        db.session.add(inscripcion)
        mensaje = f"{estudiante.nombres} fue inscrito correctamente."
    else:
        inscripcion.estado = "retirado" if inscripcion.estado == "activo" else "activo"
        mensaje = (
            f"La inscripción de {estudiante.nombres} fue "
            f"{'reactivada' if inscripcion.estado == 'activo' else 'retirada'}."
        )
    db.session.commit()
    flash(mensaje, "success")
    return redirect(url_for("cursos.inscripciones", curso_id=curso.id))


@cursos_bp.post("/<int:curso_id>/estado")
@admin_requerido
def cambiar_estado(curso_id):
    curso = db.get_or_404(Curso, curso_id)
    curso.activo = not curso.activo
    db.session.commit()
    flash(f"Curso {'activado' if curso.activo else 'desactivado'} correctamente.", "success")
    return redirect(url_for("cursos.detalle", curso_id=curso.id))


@cursos_bp.route("/<int:curso_id>/actividades/nueva", methods=["GET", "POST"])
@login_requerido
def nueva_actividad(curso_id):
    curso = db.get_or_404(Curso, curso_id)
    if not puede_gestionar_curso(curso):
        flash("No tienes permisos para crear actividades en ese curso.", "error")
        return redirect(url_for("cursos.lista"))
    if request.method == "POST":
        datos, errores = validar_actividad()
        if not errores:
            actividad = Actividad(curso_id=curso.id, creado_por=g.usuario.id, **datos)
            db.session.add(actividad)
            db.session.commit()
            flash("Actividad publicada correctamente.", "success")
            return redirect(url_for("cursos.detalle", curso_id=curso.id))
        for error in errores:
            flash(error, "error")
    return render_template("cursos/actividad_form.html", curso=curso, actividad=None)


@cursos_bp.route("/<int:curso_id>/actividades/<int:actividad_id>/editar", methods=["GET", "POST"])
@login_requerido
def editar_actividad(curso_id, actividad_id):
    curso = db.get_or_404(Curso, curso_id)
    actividad = db.get_or_404(Actividad, actividad_id)
    if actividad.curso_id != curso.id:
        return redirect(url_for("cursos.detalle", curso_id=curso.id))
    if not puede_gestionar_curso(curso):
        flash("No tienes permisos para editar esa actividad.", "error")
        return redirect(url_for("cursos.lista"))
    if request.method == "POST":
        datos, errores = validar_actividad()
        if not errores:
            for campo, valor in datos.items():
                setattr(actividad, campo, valor)
            db.session.commit()
            flash("Actividad actualizada correctamente.", "success")
            return redirect(url_for("cursos.detalle", curso_id=curso.id))
        for error in errores:
            flash(error, "error")
    return render_template("cursos/actividad_form.html", curso=curso, actividad=actividad)


def validar_actividad():
    datos = {
        "titulo": request.form.get("titulo", "").strip(),
        "descripcion": request.form.get("descripcion", "").strip(),
        "instrucciones": request.form.get("instrucciones", "").strip() or None,
        "estado": request.form.get("estado", "publicada"),
    }
    errores = []
    try:
        datos["fecha_entrega"] = datetime.fromisoformat(
            request.form.get("fecha_entrega", "")
        ).replace(tzinfo=timezone.utc)
    except ValueError:
        errores.append("Selecciona una fecha y hora de entrega válida.")
    try:
        datos["ponderacion"] = Decimal(request.form.get("ponderacion", ""))
        if not Decimal("0") < datos["ponderacion"] <= Decimal("100"):
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        errores.append("La ponderación debe ser mayor que 0 y menor o igual a 100.")
    try:
        datos["frecuencia_avance_dias"] = int(request.form.get("frecuencia_avance_dias", "7"))
        if not 1 <= datos["frecuencia_avance_dias"] <= 30:
            raise ValueError
    except ValueError:
        errores.append("La frecuencia de avance debe estar entre 1 y 30 días.")
    if not datos["titulo"] or len(datos["titulo"]) > 180:
        errores.append("Escribe un título válido de máximo 180 caracteres.")
    if not datos["descripcion"]:
        errores.append("La descripción es obligatoria.")
    if datos["estado"] not in {"borrador", "publicada", "cerrada"}:
        errores.append("Selecciona un estado válido.")
    return datos, errores
