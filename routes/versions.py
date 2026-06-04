from flask import Blueprint, request, jsonify
from services.core_engine import run_version
from storage import store

versions_bp = Blueprint("versions", __name__)


@versions_bp.route("/versions", methods=["POST"])
def create_version():
    body = request.get_json(silent=True) or {}
    try:
        record = run_version(body)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(record), 201


@versions_bp.route("/versions", methods=["GET"])
def list_versions():
    return jsonify(store.get_all_versions()), 200
