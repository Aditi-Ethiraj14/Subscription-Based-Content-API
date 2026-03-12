from flask import Flask, jsonify
from .database import init_db
from .routes import auth_bp, content_bp, sub_bp, admin_bp


def create_app():
    app = Flask(__name__)

    # Init DB on startup
    init_db()

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(content_bp)
    app.register_blueprint(sub_bp)
    app.register_blueprint(admin_bp)

    # Health check
    @app.get("/")
    def index():
        return jsonify({
            "service": "Subscription-Based Content API",
            "version": "1.0.0",
            "status":  "running",
            "docs":    "See README.md for API reference",
        })

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    # Global error handlers
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Endpoint not found"}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"error": "Method not allowed"}), 405

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"error": "Internal server error"}), 500

    return app
