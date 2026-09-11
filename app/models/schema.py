from sqlalchemy.dialects.postgresql import INET, JSONB
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db


AHORA = db.text("CURRENT_TIMESTAMP")


class Role(db.Model):
    __tablename__ = "roles"

    id = db.Column(db.BigInteger, primary_key=True)
    nombre = db.Column(db.String(30), nullable=False, unique=True)
    descripcion = db.Column(db.String(150))
    creado_en = db.Column(db.DateTime(timezone=True), nullable=False, server_default=AHORA)


class Usuario(db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.BigInteger, primary_key=True)
    rol_id = db.Column(db.BigInteger, db.ForeignKey("roles.id"), nullable=False)
    nombres = db.Column(db.String(100), nullable=False)
    apellidos = db.Column(db.String(100), nullable=False)
    correo = db.Column(db.String(150), nullable=False, unique=True)
    contrasena_hash = db.Column(db.Text, nullable=False)
    carnet = db.Column(db.String(30), unique=True)
    activo = db.Column(db.Boolean, nullable=False, server_default=db.text("true"))
    ultimo_acceso = db.Column(db.DateTime(timezone=True))
    creado_en = db.Column(db.DateTime(timezone=True), nullable=False, server_default=AHORA)
    actualizado_en = db.Column(db.DateTime(timezone=True), nullable=False, server_default=AHORA)

    rol = db.relationship("Role", backref=db.backref("usuarios", lazy="selectin"))

    def establecer_contrasena(self, password):
        self.contrasena_hash = generate_password_hash(password)

    def verificar_contrasena(self, password):
        return check_password_hash(self.contrasena_hash, password)


class Curso(db.Model):
    __tablename__ = "cursos"

    id = db.Column(db.BigInteger, primary_key=True)
    docente_id = db.Column(db.BigInteger, db.ForeignKey("usuarios.id"), nullable=False)
    codigo = db.Column(db.String(30), nullable=False, unique=True)
    nombre = db.Column(db.String(150), nullable=False)
    descripcion = db.Column(db.Text)
    ciclo = db.Column(db.String(30))
    anio = db.Column(db.SmallInteger, nullable=False)
    activo = db.Column(db.Boolean, nullable=False, server_default=db.text("true"))
    creado_en = db.Column(db.DateTime(timezone=True), nullable=False, server_default=AHORA)


class Inscripcion(db.Model):
    __tablename__ = "inscripciones"
    __table_args__ = (db.UniqueConstraint("curso_id", "estudiante_id"),)

    id = db.Column(db.BigInteger, primary_key=True)
    curso_id = db.Column(
        db.BigInteger, db.ForeignKey("cursos.id", ondelete="CASCADE"), nullable=False
    )
    estudiante_id = db.Column(db.BigInteger, db.ForeignKey("usuarios.id"), nullable=False)
    fecha_inscripcion = db.Column(db.DateTime(timezone=True), nullable=False, server_default=AHORA)
    estado = db.Column(db.String(20), nullable=False, server_default=db.text("'activo'"))


class Actividad(db.Model):
    __tablename__ = "actividades"

    id = db.Column(db.BigInteger, primary_key=True)
    curso_id = db.Column(
        db.BigInteger, db.ForeignKey("cursos.id", ondelete="CASCADE"), nullable=False
    )
    titulo = db.Column(db.String(180), nullable=False)
    descripcion = db.Column(db.Text, nullable=False)
    instrucciones = db.Column(db.Text)
    fecha_publicacion = db.Column(db.DateTime(timezone=True), nullable=False, server_default=AHORA)
    fecha_entrega = db.Column(db.DateTime(timezone=True), nullable=False)
    ponderacion = db.Column(db.Numeric(5, 2), nullable=False)
    frecuencia_avance_dias = db.Column(db.Integer, nullable=False, server_default=db.text("7"))
    estado = db.Column(db.String(20), nullable=False, server_default=db.text("'publicada'"))
    creado_por = db.Column(db.BigInteger, db.ForeignKey("usuarios.id"), nullable=False)
    creado_en = db.Column(db.DateTime(timezone=True), nullable=False, server_default=AHORA)


class CriterioEvaluacion(db.Model):
    __tablename__ = "criterios_evaluacion"
    __table_args__ = (db.UniqueConstraint("actividad_id", "nombre"),)

    id = db.Column(db.BigInteger, primary_key=True)
    actividad_id = db.Column(
        db.BigInteger, db.ForeignKey("actividades.id", ondelete="CASCADE"), nullable=False
    )
    nombre = db.Column(db.String(150), nullable=False)
    descripcion = db.Column(db.Text)
    porcentaje = db.Column(db.Numeric(5, 2), nullable=False)
    orden = db.Column(db.Integer, nullable=False, server_default=db.text("1"))


class SesionTrabajo(db.Model):
    __tablename__ = "sesiones_trabajo"

    id = db.Column(db.BigInteger, primary_key=True)
    estudiante_id = db.Column(db.BigInteger, db.ForeignKey("usuarios.id"), nullable=False)
    actividad_id = db.Column(
        db.BigInteger, db.ForeignKey("actividades.id", ondelete="CASCADE"), nullable=False
    )
    inicio = db.Column(db.DateTime(timezone=True), nullable=False, server_default=AHORA)
    fin = db.Column(db.DateTime(timezone=True))
    duracion_segundos = db.Column(db.Integer)
    pausas_segundos = db.Column(db.Integer, nullable=False, server_default=db.text("0"))
    objetivo = db.Column(db.Text, nullable=False)
    resumen = db.Column(db.Text)
    estado = db.Column(db.String(20), nullable=False, server_default=db.text("'activa'"))


class Pausa(db.Model):
    __tablename__ = "pausas"

    id = db.Column(db.BigInteger, primary_key=True)
    sesion_id = db.Column(
        db.BigInteger, db.ForeignKey("sesiones_trabajo.id", ondelete="CASCADE"), nullable=False
    )
    inicio = db.Column(db.DateTime(timezone=True), nullable=False)
    fin = db.Column(db.DateTime(timezone=True))
    duracion_segundos = db.Column(db.Integer)


class Avance(db.Model):
    __tablename__ = "avances"

    id = db.Column(db.BigInteger, primary_key=True)
    actividad_id = db.Column(
        db.BigInteger, db.ForeignKey("actividades.id", ondelete="CASCADE"), nullable=False
    )
    estudiante_id = db.Column(db.BigInteger, db.ForeignKey("usuarios.id"), nullable=False)
    sesion_id = db.Column(
        db.BigInteger, db.ForeignKey("sesiones_trabajo.id", ondelete="SET NULL")
    )
    descripcion = db.Column(db.Text, nullable=False)
    porcentaje_declarado = db.Column(db.Numeric(5, 2), nullable=False)
    dificultades = db.Column(db.Text)
    siguiente_paso = db.Column(db.Text)
    registrado_en = db.Column(db.DateTime(timezone=True), nullable=False, server_default=AHORA)


class Evidencia(db.Model):
    __tablename__ = "evidencias"

    id = db.Column(db.BigInteger, primary_key=True)
    avance_id = db.Column(
        db.BigInteger, db.ForeignKey("avances.id", ondelete="CASCADE"), nullable=False
    )
    estudiante_id = db.Column(db.BigInteger, db.ForeignKey("usuarios.id"), nullable=False)
    nombre_archivo = db.Column(db.String(255), nullable=False)
    tipo_archivo = db.Column(db.String(100), nullable=False)
    ubicacion_archivo = db.Column(db.Text, nullable=False)
    tamano_bytes = db.Column(db.BigInteger)
    hash_archivo = db.Column(db.String(128))
    descripcion = db.Column(db.Text)
    cargado_en = db.Column(db.DateTime(timezone=True), nullable=False, server_default=AHORA)


class AvanceCriterio(db.Model):
    __tablename__ = "avances_criterio"
    __table_args__ = (db.UniqueConstraint("criterio_id", "estudiante_id"),)

    id = db.Column(db.BigInteger, primary_key=True)
    criterio_id = db.Column(
        db.BigInteger,
        db.ForeignKey("criterios_evaluacion.id", ondelete="CASCADE"),
        nullable=False,
    )
    estudiante_id = db.Column(db.BigInteger, db.ForeignKey("usuarios.id"), nullable=False)
    evidencia_id = db.Column(
        db.BigInteger, db.ForeignKey("evidencias.id", ondelete="SET NULL")
    )
    estado = db.Column(db.String(20), nullable=False, server_default=db.text("'pendiente'"))
    porcentaje_aportado = db.Column(db.Numeric(5, 2), nullable=False, server_default=db.text("0"))
    observacion_docente = db.Column(db.Text)
    validado_por = db.Column(db.BigInteger, db.ForeignKey("usuarios.id"))
    registrado_en = db.Column(db.DateTime(timezone=True), nullable=False, server_default=AHORA)
    validado_en = db.Column(db.DateTime(timezone=True))


class Entrega(db.Model):
    __tablename__ = "entregas"
    __table_args__ = (db.UniqueConstraint("actividad_id", "estudiante_id", "version"),)

    id = db.Column(db.BigInteger, primary_key=True)
    actividad_id = db.Column(
        db.BigInteger, db.ForeignKey("actividades.id", ondelete="CASCADE"), nullable=False
    )
    estudiante_id = db.Column(db.BigInteger, db.ForeignKey("usuarios.id"), nullable=False)
    version = db.Column(db.Integer, nullable=False, server_default=db.text("1"))
    comentario = db.Column(db.Text)
    ubicacion_entrega = db.Column(db.Text)
    fecha_entrega = db.Column(db.DateTime(timezone=True), nullable=False, server_default=AHORA)
    estado = db.Column(db.String(25), nullable=False, server_default=db.text("'enviada'"))


class EvaluacionCriterio(db.Model):
    __tablename__ = "evaluaciones_criterio"
    __table_args__ = (db.UniqueConstraint("entrega_id", "criterio_id"),)

    id = db.Column(db.BigInteger, primary_key=True)
    entrega_id = db.Column(
        db.BigInteger, db.ForeignKey("entregas.id", ondelete="CASCADE"), nullable=False
    )
    criterio_id = db.Column(
        db.BigInteger, db.ForeignKey("criterios_evaluacion.id"), nullable=False
    )
    docente_id = db.Column(db.BigInteger, db.ForeignKey("usuarios.id"), nullable=False)
    porcentaje_cumplimiento = db.Column(db.Numeric(5, 2), nullable=False)
    observacion = db.Column(db.Text)
    evaluado_en = db.Column(db.DateTime(timezone=True), nullable=False, server_default=AHORA)


class ValidacionDocente(db.Model):
    __tablename__ = "validaciones_docente"

    id = db.Column(db.BigInteger, primary_key=True)
    entrega_id = db.Column(
        db.BigInteger, db.ForeignKey("entregas.id", ondelete="CASCADE"), nullable=False
    )
    docente_id = db.Column(db.BigInteger, db.ForeignKey("usuarios.id"), nullable=False)
    decision = db.Column(db.String(25), nullable=False)
    calificacion = db.Column(db.Numeric(5, 2))
    retroalimentacion = db.Column(db.Text, nullable=False)
    validado_en = db.Column(db.DateTime(timezone=True), nullable=False, server_default=AHORA)


class InteraccionIA(db.Model):
    __tablename__ = "interacciones_ia"

    id = db.Column(db.BigInteger, primary_key=True)
    usuario_id = db.Column(db.BigInteger, db.ForeignKey("usuarios.id"), nullable=False)
    actividad_id = db.Column(
        db.BigInteger, db.ForeignKey("actividades.id", ondelete="SET NULL")
    )
    sesion_id = db.Column(
        db.BigInteger, db.ForeignKey("sesiones_trabajo.id", ondelete="SET NULL")
    )
    tipo_ayuda = db.Column(db.String(40), nullable=False)
    consulta = db.Column(db.Text, nullable=False)
    codigo_enviado = db.Column(db.Text)
    respuesta = db.Column(db.Text)
    codigo_modificado = db.Column(db.Text)
    proveedor = db.Column(db.String(40))
    modelo = db.Column(db.String(80))
    estado = db.Column(db.String(25), nullable=False, server_default=db.text("'pendiente'"))
    tiempo_resolucion_segundos = db.Column(db.Integer)
    error_tecnico = db.Column(db.Text)
    creado_en = db.Column(db.DateTime(timezone=True), nullable=False, server_default=AHORA)


class EventoAcceso(db.Model):
    __tablename__ = "eventos_acceso"

    id = db.Column(db.BigInteger, primary_key=True)
    usuario_id = db.Column(db.BigInteger, db.ForeignKey("usuarios.id"), nullable=False)
    fecha_ingreso = db.Column(db.DateTime(timezone=True), nullable=False, server_default=AHORA)
    fecha_salida = db.Column(db.DateTime(timezone=True))
    direccion_ip = db.Column(INET)
    agente_usuario = db.Column(db.Text)
    resultado = db.Column(db.String(20), nullable=False)


class BitacoraEvento(db.Model):
    __tablename__ = "bitacora_eventos"

    id = db.Column(db.BigInteger, primary_key=True)
    usuario_id = db.Column(
        db.BigInteger, db.ForeignKey("usuarios.id", ondelete="SET NULL")
    )
    tipo_evento = db.Column(db.String(60), nullable=False)
    entidad = db.Column(db.String(60))
    entidad_id = db.Column(db.BigInteger)
    datos = db.Column(JSONB, nullable=False, server_default=db.text("'{}'::jsonb"))
    direccion_ip = db.Column(INET)
    creado_en = db.Column(db.DateTime(timezone=True), nullable=False, server_default=AHORA)


class PeriodoObservacion(db.Model):
    __tablename__ = "periodos_observacion"

    id = db.Column(db.BigInteger, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    fecha_inicio = db.Column(db.Date, nullable=False)
    fecha_fin = db.Column(db.Date, nullable=False)
    activo = db.Column(db.Boolean, nullable=False, server_default=db.text("true"))
    creado_en = db.Column(db.DateTime(timezone=True), nullable=False, server_default=AHORA)


class Exportacion(db.Model):
    __tablename__ = "exportaciones"

    id = db.Column(db.BigInteger, primary_key=True)
    usuario_id = db.Column(db.BigInteger, db.ForeignKey("usuarios.id"), nullable=False)
    periodo_id = db.Column(db.BigInteger, db.ForeignKey("periodos_observacion.id"))
    tipo_archivo = db.Column(db.String(15), nullable=False)
    filtros = db.Column(JSONB, nullable=False, server_default=db.text("'{}'::jsonb"))
    ubicacion_archivo = db.Column(db.Text)
    hash_archivo = db.Column(db.String(128))
    anonimizada = db.Column(db.Boolean, nullable=False, server_default=db.text("true"))
    creado_en = db.Column(db.DateTime(timezone=True), nullable=False, server_default=AHORA)
