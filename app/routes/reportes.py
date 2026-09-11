from collections import defaultdict
from datetime import datetime, timezone
from functools import wraps

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from app.extensions import db
from app.models import (
    Actividad,
    Avance,
    Curso,
    Evidencia,
    Inscripcion,
    InteraccionIA,
    SesionTrabajo,
    Usuario,
)
from app.routes.auth import login_requerido


reportes_bp = Blueprint("reportes", __name__, url_prefix="/reportes")


def docente_o_admin_requerido(vista):
    @wraps(vista)
    @login_requerido
    def vista_protegida(*args, **kwargs):
        if g.usuario.rol.nombre not in {"docente", "administrador"}:
            flash("Los reportes académicos están disponibles para docentes y administradores.", "error")
            return redirect(url_for("auth.panel"))
        return vista(*args, **kwargs)

    return vista_protegida


def cursos_permitidos():
    consulta = Curso.query.order_by(Curso.anio.desc(), Curso.nombre)
    if g.usuario.rol.nombre == "docente":
        consulta = consulta.filter_by(docente_id=g.usuario.id)
    return consulta.all()


def porcentaje(valor):
    return round(float(valor or 0), 1)


@reportes_bp.get("")
@docente_o_admin_requerido
def panel():
    cursos = cursos_permitidos()
    curso_id = request.args.get("curso_id", type=int)
    curso = next((item for item in cursos if item.id == curso_id), None)
    if curso is None and cursos:
        curso = cursos[0]

    if curso is None:
        return render_template("reportes/panel.html", cursos=[], curso=None)

    inscripciones = Inscripcion.query.filter_by(curso_id=curso.id, estado="activo").all()
    estudiantes_ids = [item.estudiante_id for item in inscripciones]
    estudiantes = (
        Usuario.query.filter(Usuario.id.in_(estudiantes_ids)).order_by(
            Usuario.apellidos, Usuario.nombres
        ).all()
        if estudiantes_ids else []
    )
    actividades = Actividad.query.filter_by(curso_id=curso.id).order_by(
        Actividad.fecha_entrega
    ).all()
    actividades_ids = [item.id for item in actividades]

    sesiones = (
        SesionTrabajo.query.filter(
            SesionTrabajo.actividad_id.in_(actividades_ids),
            SesionTrabajo.estudiante_id.in_(estudiantes_ids),
        ).all()
        if actividades_ids and estudiantes_ids else []
    )
    avances = (
        Avance.query.filter(
            Avance.actividad_id.in_(actividades_ids),
            Avance.estudiante_id.in_(estudiantes_ids),
        ).order_by(Avance.registrado_en).all()
        if actividades_ids and estudiantes_ids else []
    )
    avances_ids = [item.id for item in avances]
    evidencias = (
        Evidencia.query.filter(Evidencia.avance_id.in_(avances_ids)).all()
        if avances_ids else []
    )
    interacciones = (
        InteraccionIA.query.filter(
            InteraccionIA.actividad_id.in_(actividades_ids),
            InteraccionIA.usuario_id.in_(estudiantes_ids),
        ).all()
        if actividades_ids and estudiantes_ids else []
    )

    sesiones_estudiante = defaultdict(list)
    avances_estudiante = defaultdict(list)
    evidencias_estudiante = defaultdict(list)
    ia_estudiante = defaultdict(list)
    for item in sesiones:
        sesiones_estudiante[item.estudiante_id].append(item)
    for item in avances:
        avances_estudiante[item.estudiante_id].append(item)
    for item in evidencias:
        evidencias_estudiante[item.estudiante_id].append(item)
    for item in interacciones:
        ia_estudiante[item.usuario_id].append(item)

    filas_estudiantes = []
    for estudiante in estudiantes:
        sesiones_usuario = sesiones_estudiante[estudiante.id]
        avances_usuario = avances_estudiante[estudiante.id]
        ia_usuario = ia_estudiante[estudiante.id]
        ultimos_avances = {}
        for avance in avances_usuario:
            ultimos_avances[avance.actividad_id] = avance
        avance_general = (
            sum(porcentaje(item.porcentaje_declarado) for item in ultimos_avances.values())
            / len(actividades)
            if actividades else 0
        )
        momentos = [item.inicio for item in sesiones_usuario]
        momentos += [item.registrado_en for item in avances_usuario]
        momentos += [item.creado_en for item in ia_usuario]
        filas_estudiantes.append({
            "usuario": estudiante,
            "sesiones": len(sesiones_usuario),
            "segundos": sum(item.duracion_segundos or 0 for item in sesiones_usuario),
            "avance": round(avance_general, 1),
            "evidencias": len(evidencias_estudiante[estudiante.id]),
            "ia_total": len(ia_usuario),
            "ia_verificadas": sum(item.estado in {"completada", "fallida"} for item in ia_usuario),
            "ultima_actividad": max(momentos) if momentos else None,
        })

    filas_actividades = []
    ahora = datetime.now(timezone.utc)
    for actividad in actividades:
        sesiones_actividad = [item for item in sesiones if item.actividad_id == actividad.id]
        avances_actividad = [item for item in avances if item.actividad_id == actividad.id]
        ia_actividad = [item for item in interacciones if item.actividad_id == actividad.id]
        ultimos = {}
        for avance in avances_actividad:
            ultimos[avance.estudiante_id] = avance
        promedio = (
            sum(porcentaje(item.porcentaje_declarado) for item in ultimos.values())
            / len(estudiantes)
            if estudiantes else 0
        )
        avances_actividad_ids = {item.id for item in avances_actividad}
        fecha_publicacion = actividad.fecha_publicacion
        fecha_entrega = actividad.fecha_entrega
        if fecha_entrega < ahora:
            estado_cronograma = "Finalizada"
        elif fecha_publicacion > ahora:
            estado_cronograma = "Próxima"
        else:
            estado_cronograma = "En curso"
        filas_actividades.append({
            "actividad": actividad,
            "avance": round(promedio, 1),
            "sesiones": len(sesiones_actividad),
            "segundos": sum(item.duracion_segundos or 0 for item in sesiones_actividad),
            "evidencias": sum(item.avance_id in avances_actividad_ids for item in evidencias),
            "ia": len(ia_actividad),
            "estado_cronograma": estado_cronograma,
            "dias_restantes": max(0, (fecha_entrega.date() - ahora.date()).days),
        })

    total_ia = len(interacciones)
    verificadas_ia = sum(item.estado in {"completada", "fallida"} for item in interacciones)
    metricas = {
        "estudiantes": len(estudiantes),
        "actividades": len(actividades),
        "sesiones": len(sesiones),
        "segundos": sum(item.duracion_segundos or 0 for item in sesiones),
        "avance": round(
            sum(item["avance"] for item in filas_estudiantes) / len(filas_estudiantes), 1
        ) if filas_estudiantes else 0,
        "evidencias": len(evidencias),
        "ia_total": total_ia,
        "ia_verificadas": verificadas_ia,
        "ia_porcentaje": round(verificadas_ia * 100 / total_ia, 1) if total_ia else 0,
    }

    estudiantes_con_sesion = sum(
        1 for fila in filas_estudiantes if fila["sesiones"] > 0
    )
    porcentaje_gestion_tiempo = round(
        estudiantes_con_sesion * 100 / len(estudiantes), 1
    ) if estudiantes else 0
    porcentaje_avance = max(0, min(100, metricas["avance"]))
    porcentaje_ia = max(0, min(100, metricas["ia_porcentaje"]))

    objetivos = [
        {
            "codigo": "OE1",
            "titulo": "Gestión y registro del tiempo de trabajo",
            "descripcion": (
                "Determina qué porcentaje de estudiantes utiliza las sesiones "
                "para registrar y analizar el tiempo dedicado a programación."
            ),
            "indicador": "Estudiantes con al menos una sesión registrada",
            "formula": "Estudiantes con sesiones ÷ estudiantes inscritos × 100",
            "datos": f"{estudiantes_con_sesion} de {len(estudiantes)} estudiantes",
            "porcentaje": porcentaje_gestion_tiempo,
            "tipo": "dona",
            "color": "azul",
            "interpretacion": (
                f"El {porcentaje_gestion_tiempo}% de los estudiantes inscritos "
                "ya registra su tiempo de trabajo."
                if estudiantes else
                "Aún no hay estudiantes inscritos para calcular este indicador."
            ),
        },
        {
            "codigo": "OE2",
            "titulo": "Seguimiento del avance académico",
            "descripcion": (
                "Mide el progreso alcanzado a partir del último porcentaje "
                "declarado por estudiante en cada actividad."
            ),
            "indicador": "Promedio del último avance registrado",
            "formula": "Suma de avances actuales ÷ estudiantes y actividades",
            "datos": f"{metricas['avance']}% de avance promedio",
            "porcentaje": porcentaje_avance,
            "tipo": "barra",
            "color": "morado",
            "interpretacion": (
                f"El curso presenta un avance académico promedio de {metricas['avance']}%."
                if actividades and estudiantes else
                "Aún no hay suficientes avances para calcular este indicador."
            ),
        },
        {
            "codigo": "OE3",
            "titulo": "Uso responsable y verificable de inteligencia artificial",
            "descripcion": (
                "Evalúa qué proporción de las consultas de IA fue revisada y "
                "verificada por los estudiantes."
            ),
            "indicador": "Interacciones de IA con verificación estudiantil",
            "formula": "Interacciones verificadas ÷ interacciones totales × 100",
            "datos": f"{verificadas_ia} de {total_ia} interacciones",
            "porcentaje": porcentaje_ia,
            "tipo": "dona",
            "color": "verde",
            "interpretacion": (
                f"El {porcentaje_ia}% del uso de IA cuenta con verificación estudiantil."
                if total_ia else
                "Aún no hay interacciones de IA para calcular este indicador."
            ),
        },
    ]

    docente = db.session.get(Usuario, curso.docente_id)
    return render_template(
        "reportes/panel.html",
        cursos=cursos,
        curso=curso,
        docente=docente,
        metricas=metricas,
        objetivos=objetivos,
        estudiantes=filas_estudiantes,
        actividades=filas_actividades,
    )
