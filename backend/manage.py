"""Explicit, non-destructive database setup: python manage.py init-db."""
import argparse

from sqlalchemy import text

from api import db
from app import create_app


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["init-db"])
    parser.parse_args(argv)
    app = create_app()
    with app.app_context():
        if db.engine.dialect.name != "postgresql":
            parser.error("IFAB indexing requires PostgreSQL with pgvector. Set DB_URI first.")
        # Requires a DB user allowed to enable an installed pgvector extension.
        # No tables or data are dropped, and nothing runs merely on import.
        db.session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        db.session.commit()
        from api.models import DocumentChunks  # register model before create_all
        db.create_all()
        print(f"Database ready: {DocumentChunks.__tablename__}. Existing data preserved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
