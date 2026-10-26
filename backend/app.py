from flask import Flask, jsonify
from flask_cors import CORS
import os

from api.config import Config
from api import db
from api.routes import bp
from api.ifab_routes import ifab_bp
from api.rag_routes import rag_bp
from api.match_summary_routes import match_summary_bp
from api.match_stats_routes import match_stats_bp


def create_app():
    app = Flask(__name__)

    CORS(app, resources={r'/api/*': {
        'origins': os.getenv('CORS_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173').split(','),
    }})

    app.config.from_object(Config)
    if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgresql'):
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            **app.config['SQLALCHEMY_ENGINE_OPTIONS'], 'connect_args': {'connect_timeout': 3},
        }
    db.init_app(app)

    app.register_blueprint(bp, url_prefix='/api/v1')
    app.register_blueprint(ifab_bp, url_prefix='/api/v1/ifabs')
    app.register_blueprint(rag_bp, url_prefix='/api/v1/rag')
    app.register_blueprint(match_summary_bp, url_prefix='/api/v1')
    app.register_blueprint(match_stats_bp, url_prefix='/api/v1')

    @app.errorhandler(Exception)
    def handle_error(e):
        status_code = getattr(e, 'code', 500)
        if status_code >= 500:
            app.logger.exception('Unhandled API error')
        response = {'error': getattr(e, 'description', 'The request failed. Check backend logs for details.')}
        return jsonify(response), status_code

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=8080)
