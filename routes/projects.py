from flask import Blueprint, request, jsonify
from models.project import make_project
from storage import store

projects_bp = Blueprint("projects", __name__)


@projects_bp.route("/projects", methods=["POST"])
def create_project():
    body = request.get_json(silent=True) or {}
    name = body.get("name", "").strip()
    if not name:
        return jsonify({"error": "Missing required field: name"}), 400

    record = make_project(name=name, config=body.get("config", {}))
    store.insert_project(record)
    return jsonify(record), 201


@projects_bp.route("/projects", methods=["GET"])
def list_projects():
    return jsonify(store.get_all_projects()), 200
