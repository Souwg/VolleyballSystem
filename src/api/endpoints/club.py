import math
import os
import uuid

from flask import jsonify, request
from flask_jwt_extended import jwt_required
from werkzeug.utils import secure_filename

from src.api.api_blueprint import api
from src.api.dashboard_service import build_club_dashboard
from src.api.extensions import bcrypt
from src.api.models import (
    db,
    User,
    Club,
    RefreshToken,
)
from src.api.upload_utils import allowed_image_file
from src.api.utils import error_response, generate_temp_password, get_current_user


MAX_CLUB_IMAGE_SIZE = 2 * 1024 * 1024
CLUB_USER_ROLES = ["coach", "staff"]


def serialize_club_user(user):
    return {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "first_login": user.first_login,
        "created_at": (
            user.created_at.isoformat()
            if user.created_at
            else None
        )
    }


def get_managed_club_user(owner, user_id):
    managed_user = User.query.get(user_id)

    if not managed_user:
        return None, error_response(
            "Usuario no encontrado",
            "USER_NOT_FOUND",
            404
        )

    if (
        managed_user.club_id != owner.club_id
        or managed_user.role not in CLUB_USER_ROLES
    ):
        return None, error_response(
            "No tienes permisos para gestionar este usuario",
            "FORBIDDEN",
            403
        )

    return managed_user, None


def invalidate_club_user_sessions(user):
    user.session_version = (user.session_version or 0) + 1

    RefreshToken.query.filter_by(
        user_id=user.id,
        revoked=False
    ).update({"revoked": True})


@api.route("/club/users", methods=["POST"])
@jwt_required()
def create_club_user():

    user = get_current_user()

    if user.role != "club_owner":
        return error_response(
            "Solo el dueño del club puede crear usuarios",
            "FORBIDDEN",
            403
        )

    club = Club.query.get(user.club_id)

    if not club:
        return error_response(
            "Club no encontrado",
            "CLUB_NOT_FOUND",
            404
        )

    body = request.get_json() or {}

    full_name = body.get("full_name")
    email = body.get("email")

    if email:
        email = email.strip().lower()
    role = body.get("role")

    if not full_name:
        return error_response(
            "Nombre completo requerido",
            "FULL_NAME_REQUIRED",
            400
        )

    if not email:
        return error_response(
            "Email requerido",
            "EMAIL_REQUIRED",
            400
        )

    if role not in CLUB_USER_ROLES:
        return error_response(
            "Rol inválido",
            "INVALID_ROLE",
            400
        )

    existing_user = User.query.filter_by(email=email).first()

    if existing_user:
        return error_response(
            "Ya existe un usuario con ese email",
            "EMAIL_ALREADY_EXISTS",
            409
        )

    temp_password = generate_temp_password()

    hashed_password = bcrypt.generate_password_hash(temp_password).decode("utf-8")

    new_user = User(
        full_name=full_name,
        email=email,
        password=hashed_password,
        role=role,
        first_login=True,
        club_id=club.id
    )

    db.session.add(new_user)
    db.session.commit()

    return jsonify({
        "message": "Usuario del club creado",
        "temporary_password": temp_password,
        "user": new_user.serialize()
    }), 201


@api.route("/club/users", methods=["GET"])
@jwt_required()
def get_club_users():
    user = get_current_user()

    if user.role != "club_owner":
        return error_response(
            "Solo el dueño del club puede consultar usuarios",
            "FORBIDDEN",
            403
        )

    users = User.query.filter(
        User.club_id == user.club_id,
        User.role.in_(CLUB_USER_ROLES)
    ).order_by(User.created_at.desc()).all()

    return jsonify({
        "total": len(users),
        "users": [
            serialize_club_user(club_user)
            for club_user in users
        ]
    }), 200


@api.route("/club/users/<string:user_id>", methods=["GET"])
@jwt_required()
def get_club_user_detail(user_id):
    user = get_current_user()

    if user.role != "club_owner":
        return error_response(
            "Solo el dueño del club puede consultar usuarios",
            "FORBIDDEN",
            403
        )

    managed_user, managed_user_error = get_managed_club_user(
        user,
        user_id
    )

    if managed_user_error:
        return managed_user_error

    return jsonify({
        "user": serialize_club_user(managed_user)
    }), 200


@api.route("/club/users/<string:user_id>", methods=["PUT"])
@jwt_required()
def update_club_user(user_id):
    user = get_current_user()

    if user.role != "club_owner":
        return error_response(
            "Solo el dueño del club puede editar usuarios",
            "FORBIDDEN",
            403
        )

    managed_user, managed_user_error = get_managed_club_user(
        user,
        user_id
    )

    if managed_user_error:
        return managed_user_error

    body = request.get_json() or {}

    full_name = body.get("full_name")
    email = body.get("email")
    role = body.get("role")

    if full_name is not None:
        full_name = " ".join(str(full_name).strip().split())

        if not full_name:
            return error_response(
                "Nombre completo requerido",
                "FULL_NAME_REQUIRED",
                400
            )

    if email is not None:
        email = str(email).strip().lower()

        if not email:
            return error_response(
                "Email requerido",
                "EMAIL_REQUIRED",
                400
            )

        existing_user = User.query.filter(
            User.email == email,
            User.id != managed_user.id
        ).first()

        if existing_user:
            return error_response(
                "Ya existe un usuario con ese email",
                "EMAIL_ALREADY_EXISTS",
                409
            )

    if role is not None and role not in CLUB_USER_ROLES:
        return error_response(
            "Rol inválido",
            "INVALID_ROLE",
            400
        )

    role_changed = (
        role is not None
        and role != managed_user.role
    )

    if full_name is not None:
        managed_user.full_name = full_name

    if email is not None:
        managed_user.email = email

    if role_changed:
        managed_user.role = role
        invalidate_club_user_sessions(managed_user)

    db.session.commit()

    return jsonify({
        "message": "Usuario actualizado correctamente",
        "user": serialize_club_user(managed_user)
    }), 200


@api.route(
    "/club/users/<string:user_id>/deactivate",
    methods=["PUT"]
)
@jwt_required()
def deactivate_club_user(user_id):
    user = get_current_user()

    if user.role != "club_owner":
        return error_response(
            "Solo el dueño del club puede desactivar usuarios",
            "FORBIDDEN",
            403
        )

    managed_user, managed_user_error = get_managed_club_user(
        user,
        user_id
    )

    if managed_user_error:
        return managed_user_error

    if managed_user.is_active:
        managed_user.is_active = False
        invalidate_club_user_sessions(managed_user)
    else:
        RefreshToken.query.filter_by(
            user_id=managed_user.id,
            revoked=False
        ).update({"revoked": True})

    db.session.commit()

    return jsonify({
        "message": "Usuario desactivado correctamente",
        "user": serialize_club_user(managed_user)
    }), 200


@api.route(
    "/club/users/<string:user_id>/activate",
    methods=["PUT"]
)
@jwt_required()
def activate_club_user(user_id):
    user = get_current_user()

    if user.role != "club_owner":
        return error_response(
            "Solo el dueño del club puede reactivar usuarios",
            "FORBIDDEN",
            403
        )

    managed_user, managed_user_error = get_managed_club_user(
        user,
        user_id
    )

    if managed_user_error:
        return managed_user_error

    managed_user.is_active = True

    db.session.commit()

    return jsonify({
        "message": "Usuario reactivado correctamente",
        "user": serialize_club_user(managed_user)
    }), 200

@api.route("/club/upload-image", methods=["POST"])
@jwt_required()
def upload_club_image():

    user = get_current_user()

    if user.role != "club_owner":
        return error_response(
            "Solo el dueño del club puede actualizar la imagen",
            "FORBIDDEN",
            403
        )

    club = Club.query.get(user.club_id)

    if not club:
        return error_response(
            "Club no encontrado",
            "CLUB_NOT_FOUND",
            404
        )

    if "image" not in request.files:
        return error_response(
            "Debes seleccionar una imagen",
            "IMAGE_REQUIRED",
            400
        )

    image = request.files["image"]

    if image.filename == "":
        return error_response(
            "Debes seleccionar una imagen",
            "IMAGE_REQUIRED",
            400
        )

    if not allowed_image_file(image.filename):
        return error_response(
            "Formato inválido. Usa PNG, JPG o WEBP",
            "INVALID_IMAGE_FORMAT",
            400
        )

    image.seek(0, os.SEEK_END)
    image_size = image.tell()
    image.seek(0)

    if image_size > MAX_CLUB_IMAGE_SIZE:
        return error_response(
            "La imagen no puede pesar más de 2MB",
            "IMAGE_TOO_LARGE",
            400
        )

    original_filename = secure_filename(image.filename)
    extension = original_filename.rsplit(".", 1)[1].lower()
    filename = f"{club.id}-{uuid.uuid4().hex}.{extension}"

    upload_folder = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "../../../public/uploads/clubs"
        )
    )

    os.makedirs(upload_folder, exist_ok=True)

    file_path = os.path.join(upload_folder, filename)
    image.save(file_path)

    image_url = f"/uploads/clubs/{filename}"

    return jsonify({
        "image_url": image_url
    }), 201

@api.route("/club", methods=["PUT"])
@jwt_required()
def update_club():

    user = get_current_user()

    if user.role != "club_owner":
        return error_response(
            "Solo el dueño del club puede actualizar la información",
            "FORBIDDEN",
            403
        )

    club = Club.query.get(user.club_id)

    if not club:
        return error_response(
            "Club no encontrado",
            "CLUB_NOT_FOUND",
            404
        )

    body = request.get_json() or {}

    name = body.get("name")
    city = body.get("city")

    if city is None:
        city = body.get("location")
    image_url = body.get("image_url")
    primary_color = body.get("primary_color")
    secondary_color = body.get("secondary_color")
    default_enrollment_fee = body.get("default_enrollment_fee")
    default_monthly_fee = body.get("default_monthly_fee")

    if name is not None:
        name = str(name).strip()

        if not name:
            return error_response(
                "El nombre del club es obligatorio",
                "CLUB_NAME_REQUIRED",
                400
            )

        club.name = name

    if city is not None:
        city = str(city).strip()

        if not city:
            return error_response(
                "La ciudad es obligatoria",
                "CITY_REQUIRED",
                400
            )

        if len(city) > 120:
            return error_response(
                "La ciudad no puede superar los 120 caracteres",
                "CITY_TOO_LONG",
                400
            )

        club.city = city
        club.location = city

    if image_url is not None:
        image_url = str(image_url).strip()

        club.image_url = image_url or None

    if primary_color is not None:
        primary_color = str(primary_color).strip()
        club.primary_color = primary_color or None

    if secondary_color is not None:
        secondary_color = str(secondary_color).strip()
        club.secondary_color = secondary_color or None

    # ✅ MONTO DE INSCRIPCIÓN POR DEFECTO
    if default_enrollment_fee is not None:
        try:
            default_enrollment_fee = float(default_enrollment_fee or 0)
        except (TypeError, ValueError):
            return error_response(
                "El monto de inscripción debe ser numérico",
                "INVALID_DEFAULT_ENROLLMENT_FEE",
                400
            )

        if not math.isfinite(default_enrollment_fee):
            return error_response(
                "El monto de inscripción debe ser numérico",
                "INVALID_DEFAULT_ENROLLMENT_FEE",
                400
            )

        if default_enrollment_fee < 0:
            return error_response(
                "El monto de inscripción no puede ser negativo",
                "INVALID_DEFAULT_ENROLLMENT_FEE",
                400
            )

        club.default_enrollment_fee = default_enrollment_fee


    if default_monthly_fee is not None:
        try:
            default_monthly_fee = float(default_monthly_fee or 0)
        except (TypeError, ValueError):
            return error_response(
                "El monto de mensualidad debe ser numérico",
                "INVALID_DEFAULT_MONTHLY_FEE",
                400
            )

        if not math.isfinite(default_monthly_fee):
            return error_response(
                "El monto de mensualidad debe ser numérico",
                "INVALID_DEFAULT_MONTHLY_FEE",
                400
            )

        if default_monthly_fee < 0:
            return error_response(
                "El monto de mensualidad no puede ser negativo",
                "INVALID_DEFAULT_MONTHLY_FEE",
                400
            )

        club.default_monthly_fee = default_monthly_fee

    db.session.commit()

    return jsonify({
        "message": "Información del club actualizada",
        "club": club.serialize()
    }), 200

@api.route("/club/dashboard", methods=["GET"])
@jwt_required()
def club_dashboard():

    user = get_current_user()

    if user.role not in ["club_owner", "coach", "staff"]:
        return error_response(
            "No tienes permisos para ver el dashboard",
            "FORBIDDEN",
            403
        )

    if not user.club_id:
        return error_response(
            "El usuario no pertenece a ningún club",
            "CLUB_REQUIRED",
            400
        )

    club = Club.query.get(user.club_id)

    if not club:
        return error_response(
            "Club no encontrado",
            "CLUB_NOT_FOUND",
            404
        )

    return jsonify(build_club_dashboard(user, club)), 200
