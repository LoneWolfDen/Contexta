"""
Contexta entry point.
Starts the Flask application and registers all route blueprints.
"""

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

from routes.projects import projects_bp
from routes.artifacts import artifacts_bp
from routes.versions import versions_bp
from routes.reviews import reviews_bp
from routes.reconciliation import reconciliation_bp
from routes.proposal import proposal_bp
from routes.learning import learning_bp


def create_app() -> Flask:
    app = Flask(__name__)

    # ✅ Enable CORS properly (Codespaces fix)
    CORS(app, resources={r"/*": {"origins": "*"}})

    @app.after_request
    def add_headers(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        return response

    # ✅ Register APIs
    app.register_blueprint(projects_bp)
    app.register_blueprint(artifacts_bp)
    app.register_blueprint(versions_bp)
    app.register_blueprint(reviews_bp)
    app.register_blueprint(reconciliation_bp)
    app.register_blueprint(proposal_bp)
    app.register_blueprint(learning_bp)

    # ✅ Health check
    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok"}), 200

    # ✅ Serve UI + static files (VERY IMPORTANT)
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_ui(path):
        import os

        ui_dir = "ui"

        # if file exists in /ui, serve it
        file_path = os.path.join(ui_dir, path)
        if path != "" and os.path.exists(file_path):
            return send_from_directory(ui_dir, path)

        # otherwise serve index
        return send_from_directory(ui_dir, "index.html")

    return app


if __name__ == "__main__":
    application = create_app()
    application.run(host="0.0.0.0", port=5000, debug=False)