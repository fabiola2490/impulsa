from datetime import datetime, timedelta, timezone

import click
from flask import current_app

from app.extensions import db
from app.models import (
    Actividad,
    Avance,
    Curso,
    Evidencia,
    Inscripcion,
    InteraccionIA,
    Role,
    SesionTrabajo,
    Usuario,
)


PREFIX = "prueba.analisis."


def registrar_comandos(app):
    @app.cli.command("generar-datos-analisis")
    @click.option("--confirmar", is_flag=True, help="Confirma la escritura de datos sintéticos.")
    @click.password_option(confirmation_prompt=True)
    def generar_datos_analisis(confirmar, password):
        """Genera 20 estudiantes, 80 sesiones y 40 interacciones de IA sintéticas."""
        if not confirmar:
            raise click.ClickException(
                "Operación cancelada. Usa --confirmar para crear los datos sintéticos."
            )

        rol = Role.query.filter_by(nombre="estudiante").first()
        if rol is None:
            raise click.ClickException("No existe el rol estudiante.")

        codigo = current_app.config.get("REGISTRATION_COURSE_CODE")
        curso = Curso.query.filter_by(codigo=codigo, activo=True).first()
        curso = curso or Curso.query.filter_by(activo=True).order_by(Curso.id).first()
        if curso is None:
            raise click.ClickException("No existe un curso activo para asociar las pruebas.")

        actividad = (
            Actividad.query.filter_by(curso_id=curso.id)
            .order_by(Actividad.id)
            .first()
        )
        if actividad is None:
            ahora = datetime.now(timezone.utc)
            actividad = Actividad(
                curso_id=curso.id,
                titulo="Actividad controlada de análisis",
                descripcion="Actividad creada para validar el análisis con datos sintéticos.",
                instrucciones="Registrar cuatro sesiones y dos interacciones de IA por estudiante.",
                fecha_publicacion=ahora - timedelta(days=30),
                fecha_entrega=ahora + timedelta(days=30),
                ponderacion=100,
                estado="publicada",
                creado_por=curso.docente_id,
            )
            db.session.add(actividad)
            db.session.flush()

        correos = [f"{PREFIX}{numero:02d}@miumg.edu.gt" for numero in range(1, 21)]
        anteriores = Usuario.query.filter(Usuario.correo.in_(correos)).all()
        ids = [usuario.id for usuario in anteriores]
        if ids:
            avances = Avance.query.filter(Avance.estudiante_id.in_(ids)).all()
            avance_ids = [avance.id for avance in avances]
            if avance_ids:
                Evidencia.query.filter(Evidencia.avance_id.in_(avance_ids)).delete(
                    synchronize_session=False
                )
            InteraccionIA.query.filter(InteraccionIA.usuario_id.in_(ids)).delete(
                synchronize_session=False
            )
            Avance.query.filter(Avance.estudiante_id.in_(ids)).delete(
                synchronize_session=False
            )
            SesionTrabajo.query.filter(SesionTrabajo.estudiante_id.in_(ids)).delete(
                synchronize_session=False
            )
            Inscripcion.query.filter(Inscripcion.estudiante_id.in_(ids)).delete(
                synchronize_session=False
            )
            Usuario.query.filter(Usuario.id.in_(ids)).delete(synchronize_session=False)
            db.session.flush()

        base = datetime.now(timezone.utc) - timedelta(days=24)
        total_sesiones = 0
        total_interacciones = 0
        for indice, correo in enumerate(correos, start=1):
            usuario = Usuario(
                rol_id=rol.id,
                nombres=f"Estudiante {indice:02d}",
                apellidos="Prueba de análisis",
                correo=correo,
                carnet=f"PRUEBA-{indice:03d}",
                activo=True,
            )
            usuario.establecer_contrasena(password)
            db.session.add(usuario)
            db.session.flush()

            db.session.add(
                Inscripcion(curso_id=curso.id, estudiante_id=usuario.id, estado="activo")
            )

            sesiones = []
            for numero_sesion in range(1, 5):
                inicio = base + timedelta(
                    days=indice - 1,
                    hours=numero_sesion * 2,
                )
                duracion = 2700 + indice * 35 + numero_sesion * 240
                sesion = SesionTrabajo(
                    estudiante_id=usuario.id,
                    actividad_id=actividad.id,
                    inicio=inicio,
                    fin=inicio + timedelta(seconds=duracion),
                    duracion_segundos=duracion,
                    pausas_segundos=numero_sesion * 30,
                    objetivo=f"Completar la fase {numero_sesion} de la actividad controlada.",
                    resumen=(
                        "Registro sintético para comprobar el análisis de tiempo, avance e IA."
                    ),
                    estado="finalizada",
                )
                db.session.add(sesion)
                db.session.flush()
                sesiones.append(sesion)
                total_sesiones += 1

                avance = Avance(
                    actividad_id=actividad.id,
                    estudiante_id=usuario.id,
                    sesion_id=sesion.id,
                    descripcion=f"Avance sintético de la sesión {numero_sesion}.",
                    porcentaje_declarado=numero_sesion * 25,
                    dificultades="Dato sintético: validación de lógica y estructura.",
                    siguiente_paso=(
                        "Continuar con la siguiente fase." if numero_sesion < 4
                        else "Revisar y presentar el resultado."
                    ),
                    registrado_en=sesion.fin,
                )
                db.session.add(avance)
                db.session.flush()
                if numero_sesion == 4:
                    db.session.add(
                        Evidencia(
                            avance_id=avance.id,
                            estudiante_id=usuario.id,
                            nombre_archivo=f"evidencia_sintetica_{indice:02d}.url",
                            tipo_archivo="text/uri-list",
                            ubicacion_archivo=(
                                f"https://example.invalid/impulsa/prueba-{indice:02d}"
                            ),
                            descripcion="Evidencia sintética; no corresponde a trabajo real.",
                        )
                    )

            for numero_ia, sesion in enumerate(sesiones[:2], start=1):
                db.session.add(
                    InteraccionIA(
                        usuario_id=usuario.id,
                        actividad_id=actividad.id,
                        sesion_id=sesion.id,
                        tipo_ayuda="explicacion" if numero_ia == 1 else "resolucion_error",
                        consulta=(
                            "Consulta sintética para explicar una función."
                            if numero_ia == 1
                            else "Consulta sintética para identificar un error de código."
                        ),
                        codigo_enviado="def ejemplo():\n    return True",
                        respuesta=(
                            "Respuesta sintética del asistente utilizada para validar el reporte."
                        ),
                        codigo_modificado="def ejemplo():\n    return bool(True)",
                        proveedor="datos_sinteticos",
                        modelo="plantilla-controlada",
                        estado="completada",
                        tiempo_resolucion_segundos=35 + indice + numero_ia,
                        creado_en=sesion.inicio + timedelta(minutes=15),
                    )
                )
                total_interacciones += 1

        db.session.commit()
        click.echo("Datos sintéticos creados correctamente.")
        click.echo(f"Curso: {curso.codigo} - {curso.nombre}")
        click.echo(f"Actividad: {actividad.titulo}")
        click.echo(f"Estudiantes: {len(correos)}")
        click.echo(f"Sesiones: {total_sesiones}")
        click.echo(f"Interacciones IA: {total_interacciones}")
        click.echo("La contraseña común fue recibida de forma oculta y no se almacenó en el código.")
