from flask_migrate import Migrate

from app import create_app
from api import db

app = create_app()

with app.app_context():
    from api.models import DocumentChunks
    db.create_all()

Migrate(app, db)

if __name__ == "__main__":
    app.run(port=8080, debug=True)
