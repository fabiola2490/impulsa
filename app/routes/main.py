from flask import Blueprint, jsonify, render_template
from app.extensions import db
from app.models import Role

main_bp = Blueprint("main", __name__)


@main_bp.get("/")
def inicio():
    return render_template("index.html")


@main_bp.get("/salud")
def salud():
    try:
        nombre = db.session.execute(db.text("SELECT current_database()"))
        total_tablas = db.session.execute(
            db.text(
                """
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_type = 'BASE TABLE'
                """
            )
        )
        return {
            "estado": "correcto",
            "aplicacion": "Impulsa",
            "base_datos": nombre.scalar_one(),
            "tablas": total_tablas.scalar_one(),
        }, 200
    except Exception:
        db.session.rollback()
        return {
            "estado": "error",
            "detalle": "No se pudo verificar la base de datos.",
        }, 500


@main_bp.get("/api/roles")
def listar_roles():
    roles = Role.query.order_by(Role.id).all()
    return jsonify(
        [
            {"id": rol.id, "nombre": rol.nombre, "descripcion": rol.descripcion}
            for rol in roles
        ]
    )


@main_bp.get("/api/resumen")
def resumen():
    consultas = {
        "roles": "SELECT COUNT(*) FROM roles",
        "usuarios": "SELECT COUNT(*) FROM usuarios",
        "cursos": "SELECT COUNT(*) FROM cursos",
        "actividades": "SELECT COUNT(*) FROM actividades",
        "sesiones": "SELECT COUNT(*) FROM sesiones_trabajo",
    }
    return {
        nombre: db.session.execute(db.text(sql)).scalar_one()
        for nombre, sql in consultas.items()
    }
