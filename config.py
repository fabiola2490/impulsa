import os

from dotenv import load_dotenv
from sqlalchemy import URL


load_dotenv()


class Config:
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
    GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip()
    SECRET_KEY = os.getenv("SECRET_KEY", "cambiar-esta-clave-en-desarrollo")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL") or URL.create(
        drivername="postgresql+psycopg",
        username=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME", "impulsa_db"),
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UMG_ALLOWED_EMAIL_DOMAINS = {
        domain.strip().lower()
        for domain in os.getenv(
            "UMG_ALLOWED_EMAIL_DOMAINS",
            "miumg.edu.gt,umg.edu.gt,mariano.edu.gt",
        ).split(",")
        if domain.strip()
    }
    MIN_SESIONES_TRABAJO = int(os.getenv("MIN_SESIONES_TRABAJO", "4"))
    REGISTRATION_COURSE_CODE = os.getenv(
        "REGISTRATION_COURSE_CODE", "2490-049-A"
    ).strip()
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }
