import uuid

from flask import Flask, g, jsonify, request
from flask_cors import CORS

import db_schema
from config import Config
from db_utils import get_db


def create_app(db_path: str = None) -> Flask:
    app = Flask(__name__, static_folder="static")

    if db_path is None:
        db_path = Config.DB_PATH

    db_schema.init(db_path)
    app.config["DB_PATH"] = db_path
    app.config["MAX_CONTENT_LENGTH"] = Config.MAX_CONTENT_LENGTH

    CORS(app, origins=Config.CORS_ORIGINS)

    @app.before_request
    def attach_request_id():
        incoming = request.headers.get("X-Request-Id", "").strip()
        g.request_id = incoming or str(uuid.uuid4())

    @app.after_request
    def add_request_id_header(response):
        request_id = getattr(g, "request_id", None)
        if request_id:
            response.headers["X-Request-Id"] = request_id
            app.logger.info(
                "request_id=%s method=%s path=%s status=%s",
                request_id,
                request.method,
                request.path,
                response.status_code,
            )
        return response

    @app.teardown_appcontext
    def close_db(e=None):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    @app.errorhandler(500)
    def internal_error(e):
        return jsonify({"error": "Internal server error", "request_id": getattr(g, "request_id", None)}), 500

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not found", "request_id": getattr(g, "request_id", None)}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"error": "Method not allowed", "request_id": getattr(g, "request_id", None)}), 405

    @app.errorhandler(413)
    def payload_too_large(e):
        return jsonify({"error": "Request payload too large", "request_id": getattr(g, "request_id", None)}), 413

    from blueprints.conversations import bp as conversations_bp
    from blueprints.kv import bp as kv_bp
    from blueprints.memory import bp as memory_bp
    from blueprints.search import bp as search_bp
    from blueprints.utility import bp as utility_bp

    app.register_blueprint(conversations_bp, url_prefix="/conversation")
    app.register_blueprint(memory_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(kv_bp, url_prefix="/kv")
    app.register_blueprint(utility_bp)

    return app


# Make get_db importable from here for convenience
__all__ = ["create_app", "get_db"]


if __name__ == "__main__":
    app = create_app()
    print(f"Memory Graph API listening on http://{Config.HOST}:{Config.PORT}", flush=True)
    app.run(host=Config.HOST, port=Config.PORT)
