"""
Contexta — Sprint 0 entry point.
Starts the Flask application and registers all route blueprints.
"""
from flask_cors import CORS
from flask import Flask, app, jsonify, send_from_directory
from routes.projects import projects_bp
from routes.artifacts import artifacts_bp
from routes.versions import versions_bp
from routes.reviews import reviews_bp
from routes.reconciliation import reconciliation_bp
from routes.proposal import proposal_bp
from routes.learning import learning_bp


def create_app() -> Flask:
    app = Flask(__name__)
    CORS(app, supports_credentials=True)

    @app.after_request
    def add_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "*"
    return response


    app.register_blueprint(projects_bp)
    app.register_blueprint(artifacts_bp)
    app.register_blueprint(versions_bp)
    app.register_blueprint(reviews_bp)
    app.register_blueprint(reconciliation_bp)
    app.register_blueprint(proposal_bp)
    app.register_blueprint(learning_bp)

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok"}), 200

    @app.route('/')
    def ui():
        return send_from_directory('ui', 'index.html')


    return app


if __name__ == "__main__":
    application = create_app()
    application.run(host="0.0.0.0", port=5000, debug=False)
