"""
Proposal Routes
Exposes POST /proposal and GET /proposal.
"""

from flask import Blueprint, request, jsonify
from services import proposal_service

proposal_bp = Blueprint("proposal", __name__)


@proposal_bp.route("/proposal", methods=["POST"])
def create_proposal():
    body = request.get_json(silent=True) or {}
    try:
        record = proposal_service.create_proposal(body)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(record), 201


@proposal_bp.route("/proposal", methods=["GET"])
def list_proposals():
    return jsonify(proposal_service.get_all_proposals()), 200
