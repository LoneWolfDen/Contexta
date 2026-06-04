from flask import Blueprint, request, jsonify
from services.core_engine import run_review
from storage import store

reviews_bp = Blueprint("reviews", __name__)


@reviews_bp.route("/reviews", methods=["POST"])
def create_review():
    body = request.get_json(silent=True) or {}
    try:
        record = run_review(body)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(record), 201


@reviews_bp.route("/reviews", methods=["GET"])
def list_reviews():
    return jsonify(store.get_all_reviews()), 200
