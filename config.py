import os

from dotenv import load_dotenv
from sqlalchemy import URL


load_dotenv()


def normalizar_database_url(valor):
    """Usa Psycopg 3 también para las URI entregadas por el proveedor."""
    if valor.startswith("postgres://"):
        return valor.replace("postgres://", "postgresql+psycopg://", 1)
    if valor.startswith("postgresql://"):
        return valor.replace("postgresql://", "postgresql+psycopg://", 1)
    return valor


class Config:
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
    GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip()
    SECRET_KEY = os.getenv("SECRET_KEY", "cambiar-esta-clave-en-desarrollo")
    SQLALCHEMY_DATABASE_URI = normalizar_database_url(os.getenv("DATABASE_URL", "")) or URL.create(
        drivername="postgresql+psycopg",
        username=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME", "impulsa_db"),
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }
