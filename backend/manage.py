from flask_migrate import Migrate

from app import create_app
from api import db

app = create_app()

with app.app_context():
    from api.models import DocumentChunks
    db.create_all()

Migrate(app, db)

if __name__ == "__main__":
    import sys

    # .venv/bin/python manage.py recreate
    #   Drops and recreates document_chunks using the current
    #   EMBEDDING_DIMENSIONS from rag/config.py. Run this whenever you
    #   switch to an embedding model with a different output dimension,
    #   then re-run POST /api/v1/rag/index.
    if len(sys.argv) > 1 and sys.argv[1] == "recreate":
        with app.app_context():
            db.session.execute(db.text("DROP TABLE IF EXISTS document_chunks"))
            db.create_all()
            db.session.commit()
        from rag.config import EMBEDDING_DIMENSIONS
        print(f"document_chunks recreated with vector({EMBEDDING_DIMENSIONS})")
    else:
        app.run(port=8080, debug=True)
