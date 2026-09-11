"""Pruebas sin red, credenciales ni modificaciones a PostgreSQL."""
import unittest
from unittest.mock import patch

from config import normalizar_database_url
from app import create_app


class PublicacionTests(unittest.TestCase):
    def test_driver(self):
        for esquema in ("postgres", "postgresql", "postgresql+psycopg"):
            self.assertEqual(
                normalizar_database_url(f"{esquema}://user:pass@host/db?sslmode=require"),
                "postgresql+psycopg://user:pass@host/db?sslmode=require",
            )
        self.assertEqual(normalizar_database_url(""), "")

    def test_inicio_sin_base(self):
        app = create_app()
        with app.test_client() as client:
            self.assertEqual(client.get("/").status_code, 200)

    def test_salud_no_revela_error(self):
        app = create_app()
        with app.test_client() as client:
            with patch("app.routes.main.db.session.execute", side_effect=RuntimeError("dato-privado")):
                with patch("app.routes.main.db.session.rollback"):
                    response = client.get("/salud")
            self.assertEqual(response.status_code, 500)
            self.assertNotIn("dato-privado", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
