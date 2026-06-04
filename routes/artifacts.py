from flask import Blueprint, request, jsonify
from services.core_engine import run_ingestion
from storage import store

artifacts_bp = Blueprint("artifacts", __name__)


@artifacts_bp.route("/artifacts", methods=["POST"])
def create_artifact():
    body = request.get_json(silent=True) or {}
    try:
        record = run_ingestion(body)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(record), 201


@artifacts_bp.route("/artifacts", methods=["GET"])
def list_artifacts():
    return jsonify(store.get_all_artifacts()), 200
