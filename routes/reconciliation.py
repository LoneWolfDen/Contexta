"""
Reconciliation Routes
Exposes POST /reconciliation and GET /reconciliation.
"""

from flask import Blueprint, request, jsonify
from services import reconciliation_service

reconciliation_bp = Blueprint("reconciliation", __name__)


@reconciliation_bp.route("/reconciliation", methods=["POST"])
def create_reconciliation():
    body = request.get_json(silent=True) or {}
    try:
        record = reconciliation_service.create_reconciliation(body)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(record), 201


@reconciliation_bp.route("/reconciliation", methods=["GET"])
def list_reconciliations():
    return jsonify(reconciliation_service.get_all_reconciliations()), 200
