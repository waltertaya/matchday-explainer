import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Archive browsing and source-data summaries do not need a vector database.
    # SQLite is only a boot fallback; IFAB retrieval explicitly needs PostgreSQL.
    SQLALCHEMY_DATABASE_URI = os.getenv('DB_URI') or 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 20 * 1024 * 1024
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    SECRET_KEY = os.getenv('SECRET_KEY')
