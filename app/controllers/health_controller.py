"""Health controller for container orchestration checks."""
from __future__ import annotations
from flask import Blueprint, jsonify

health_bp = Blueprint("health", __name__)

@health_bp.route("/health", methods=["GET"])
def health():
    """Return a simple 200 OK response."""
    return jsonify({"status": "ok"}), 200
