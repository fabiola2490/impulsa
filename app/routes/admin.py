import csv
import io

from flask import Blueprint, flash, g, redirect, render_template, request, send_file, url_for
from sqlalchemy import or_

from app.extensions import db
from app.models import Curso, Inscripcion, Role, Usuario
from app.routes.auth import admin_requerido


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def datos_formulario():
    return {
        "nombres": request.form.get("nombres", "").strip(),
        "apellidos": request.form.get("apellidos", "").strip(),
        "correo": request.form.get("correo", "").strip().lower(),
        "carnet": request.form.get("carnet", "").strip() or None,
        "rol_id": request.form.get("rol_id", "").strip(),
        "password": request.form.get("password", ""),
    }


def validar_datos(datos, usuario=None):
    errores = []
    if not datos["nombres"] or len(datos["nombres"]) > 100:
        errores.append("Escribe nombres válidos (máximo 100 caracteres).")
    if not datos["apellidos"] or len(datos["apellidos"]) > 100:
        errores.append("Escribe apellidos válidos (máximo 100 caracteres).")
    if "@" not in datos["correo"] or len(datos["correo"]) > 150:
        errores.append("Escribe un correo electrónico válido.")
    if datos["carnet"] and len(datos["carnet"]) > 30:
        errores.append("El carnet no puede superar 30 caracteres.")
    try:
        rol_id = int(datos["rol_id"])
    except (TypeError, ValueError):
        rol_id = None
    rol = db.session.get(Role, rol_id) if rol_id else None
    if rol is None:
        errores.append("Selecciona un rol válido.")
    if usuario is None and len(datos["password"]) < 8:
        errores.append("La contraseña debe tener al menos 8 caracteres.")
    if datos["password"] and len(datos["password"]) < 8:
        errores.append("La nueva contraseña debe tener al menos 8 caracteres.")

    correo_existente = Usuario.query.filter_by(correo=datos["correo"]).first()
    if correo_existente and (usuario is None or correo_existente.id != usuario.id):
        errores.append("Ya existe una cuenta con ese correo.")
    if datos["carnet"]:
        carnet_existente = Usuario.query.filter_by(carnet=datos["carnet"]).first()
        if carnet_existente and (usuario is None or carnet_existente.id != usuario.id):
            errores.append("Ya existe un usuario con ese carnet.")
    return errores, rol


@admin_bp.get("/usuarios")
@admin_requerido
def usuarios():
    buscar = request.args.get("buscar", "").strip()
    consulta = Usuario.query.join(Role).order_by(Usuario.creado_en.desc(), Usuario.id.desc())
    if buscar:
        patron = f"%{buscar}%"
        consulta = consulta.filter(
            or_(
                Usuario.nombres.ilike(patron),
                Usuario.apellidos.ilike(patron),
                Usuario.correo.ilike(patron),
                Usuario.carnet.ilike(patron),
                Role.nombre.ilike(patron),
            )
        )
    return render_template("admin/usuarios.html", usuarios=consulta.all(), buscar=buscar)


@admin_bp.get("/usuarios/plantilla-csv")
@admin_requerido
def plantilla_usuarios():
    contenido = io.StringIO()
    escritor = csv.writer(contenido)
    escritor.writerow(["nombres", "apellidos", "correo", "carnet", "password", "curso_codigo"])
    escritor.writerow(["Ejemplo", "Estudiante", "estudiante@correo.edu.gt", "2490-00-0000", "Cambiar123!", "001"])
    archivo = io.BytesIO(contenido.getvalue().encode("utf-8-sig"))
    return send_file(archivo, mimetype="text/csv", as_attachment=True, download_name="plantilla_estudiantes.csv")


@admin_bp.post("/usuarios/importar")
@admin_requerido
def importar_usuarios():
    archivo = request.files.get("archivo_csv")
    if not archivo or not archivo.filename.lower().endswith(".csv"):
        flash("Selecciona un archivo CSV válido.", "error")
        return redirect(url_for("admin.usuarios"))

    try:
        texto = archivo.stream.read().decode("utf-8-sig")
        filas = list(csv.DictReader(io.StringIO(texto)))
    except (UnicodeDecodeError, csv.Error):
        flash("No se pudo leer el CSV. Guárdalo con codificación UTF-8.", "error")
        return redirect(url_for("admin.usuarios"))

    columnas = {"nombres", "apellidos", "correo", "carnet", "password", "curso_codigo"}
    if not filas or set(filas[0].keys()) != columnas:
        flash("El CSV no tiene las columnas de la plantilla oficial.", "error")
        return redirect(url_for("admin.usuarios"))

    rol = Role.query.filter_by(nombre="estudiante").first()
    errores = []
    preparados = []
    correos_archivo = set()
    carnets_archivo = set()
    for numero, fila in enumerate(filas, start=2):
        datos = {clave: (fila.get(clave) or "").strip() for clave in columnas}
        datos["correo"] = datos["correo"].lower()
        if not datos["nombres"] or not datos["apellidos"]:
            errores.append(f"Fila {numero}: faltan nombres o apellidos.")
        if "@" not in datos["correo"]:
            errores.append(f"Fila {numero}: correo inválido.")
        if len(datos["password"]) < 8:
            errores.append(f"Fila {numero}: la contraseña debe tener al menos 8 caracteres.")
        if datos["correo"] in correos_archivo or Usuario.query.filter_by(correo=datos["correo"]).first():
            errores.append(f"Fila {numero}: el correo ya existe o está repetido.")
        if datos["carnet"] and (datos["carnet"] in carnets_archivo or Usuario.query.filter_by(carnet=datos["carnet"]).first()):
            errores.append(f"Fila {numero}: el carnet ya existe o está repetido.")
        curso = Curso.query.filter_by(codigo=datos["curso_codigo"]).first() if datos["curso_codigo"] else None
        if datos["curso_codigo"] and curso is None:
            errores.append(f"Fila {numero}: no existe el curso {datos['curso_codigo']}.")
        correos_archivo.add(datos["correo"])
        if datos["carnet"]:
            carnets_archivo.add(datos["carnet"])
        preparados.append((datos, curso))

    if rol is None:
        errores.append("No existe el rol estudiante en la base de datos.")
    if errores:
        for error in errores[:12]:
            flash(error, "error")
        if len(errores) > 12:
            flash(f"Hay {len(errores) - 12} errores adicionales. Corrige el archivo e inténtalo de nuevo.", "error")
        return redirect(url_for("admin.usuarios"))

    for datos, curso in preparados:
        usuario = Usuario(
            nombres=datos["nombres"], apellidos=datos["apellidos"],
            correo=datos["correo"], carnet=datos["carnet"] or None,
            rol_id=rol.id, activo=True,
        )
        usuario.establecer_contrasena(datos["password"])
        db.session.add(usuario)
        db.session.flush()
        if curso:
            db.session.add(Inscripcion(curso_id=curso.id, estudiante_id=usuario.id, estado="activo"))
    db.session.commit()
    flash(f"Se importaron {len(preparados)} estudiantes correctamente.", "success")
    return redirect(url_for("admin.usuarios"))


@admin_bp.route("/usuarios/nuevo", methods=["GET", "POST"])
@admin_requerido
def nuevo_usuario():
    roles = Role.query.order_by(Role.id).all()
    if request.method == "POST":
        datos = datos_formulario()
        errores, rol = validar_datos(datos)
        if not errores:
            usuario = Usuario(
                nombres=datos["nombres"], apellidos=datos["apellidos"],
                correo=datos["correo"], carnet=datos["carnet"],
                rol_id=rol.id, activo=True,
            )
            usuario.establecer_contrasena(datos["password"])
            db.session.add(usuario)
            db.session.commit()
            flash(f"Usuario {usuario.nombres} creado correctamente.", "success")
            return redirect(url_for("admin.usuarios"))
        for error in errores:
            flash(error, "error")
    return render_template("admin/usuario_form.html", roles=roles, usuario=None)


@admin_bp.route("/usuarios/<int:usuario_id>/editar", methods=["GET", "POST"])
@admin_requerido
def editar_usuario(usuario_id):
    usuario = db.get_or_404(Usuario, usuario_id)
    roles = Role.query.order_by(Role.id).all()
    if request.method == "POST":
        datos = datos_formulario()
        errores, rol = validar_datos(datos, usuario)
        if not errores:
            usuario.nombres = datos["nombres"]
            usuario.apellidos = datos["apellidos"]
            usuario.correo = datos["correo"]
            usuario.carnet = datos["carnet"]
            usuario.rol_id = rol.id
            if datos["password"]:
                usuario.establecer_contrasena(datos["password"])
            db.session.commit()
            flash("Datos actualizados correctamente.", "success")
            return redirect(url_for("admin.usuarios"))
        for error in errores:
            flash(error, "error")
    return render_template("admin/usuario_form.html", roles=roles, usuario=usuario)


@admin_bp.post("/usuarios/<int:usuario_id>/estado")
@admin_requerido
def cambiar_estado(usuario_id):
    usuario = db.get_or_404(Usuario, usuario_id)
    if usuario.id == g.usuario.id:
        flash("No puedes desactivar tu propia cuenta mientras la estás utilizando.", "error")
    else:
        usuario.activo = not usuario.activo
        db.session.commit()
        estado = "activada" if usuario.activo else "desactivada"
        flash(f"La cuenta de {usuario.nombres} fue {estado}.", "success")
    return redirect(url_for("admin.usuarios"))
