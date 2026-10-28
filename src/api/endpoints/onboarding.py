from flask import jsonify
from flask_jwt_extended import jwt_required

from src.api.api_blueprint import api
from src.api.models import Club
from src.api.onboarding_service import get_club_onboarding_progress
from src.api.utils import error_response, get_current_user


@api.route("/onboarding/status", methods=["GET"])
@jwt_required()
def onboarding_status():
    user = get_current_user()

    if user.role == "system_admin":
        return jsonify({
            "step": 5,
            "status": "completed",
            "club": None
        }), 200

    club = Club.query.get(user.club_id)

    if not club:
        return error_response(
            "Club no encontrado",
            "CLUB_NOT_FOUND",
            404
        )

    progress = get_club_onboarding_progress(club)

    return jsonify({
        **progress,
        "club": club.serialize()
    }), 200
