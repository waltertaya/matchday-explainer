from flask import Flask, jsonify
from flask_cors import CORS

from api.config import Config
from api import db
from api.routes import bp
from api.ifab_routes import ifab_bp
from api.rag_routes import rag_bp


def create_app():
    app = Flask(__name__)

    CORS(app,
         origins='*',
         methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
         allow_headers=['Authorization', 'Content-Type', 'Accept'],
         expose_headers=['Authorization', 'Content-Type'],
         supports_credentials=True,
        )

    app.config.from_object(Config)
    db.init_app(app)

    app.register_blueprint(bp, url_prefix='/api/v1')
    app.register_blueprint(ifab_bp, url_prefix='/api/v1/ifabs')
    app.register_blueprint(rag_bp, url_prefix='/api/v1/rag')

    @app.errorhandler(Exception)
    def handle_error(e):
        status_code = getattr(e, 'code', 500)
        response = {'error': f'{e}'}
        return jsonify(response), status_code

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=8080)
