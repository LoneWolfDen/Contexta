"""
Learning Routes
Exposes POST /learning and GET /learning.
"""

from flask import Blueprint, request, jsonify
from services import learning_service

learning_bp = Blueprint("learning", __name__)


@learning_bp.route("/learning", methods=["POST"])
def create_learning():
    body = request.get_json(silent=True) or {}
    try:
        record = learning_service.create_learning(body)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(record), 201


@learning_bp.route("/learning", methods=["GET"])
def list_learnings():
    return jsonify(learning_service.get_all_learnings()), 200
