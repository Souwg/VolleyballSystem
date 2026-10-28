import hashlib
import os
import re
import secrets
from datetime import datetime, timedelta

from flask import current_app, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
)

from src.api.api_blueprint import api
from src.api.email_service import send_password_reset_email
from src.api.extensions import bcrypt
from src.api.models import (
    db,
    PasswordResetToken,
    RefreshToken,
    TokenBlockedList,
    User,
)
from src.api.utils import ensure_club_access, error_response, get_current_user


def hash_reset_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@api.route('/login', methods=['POST'])
def login():
    body = request.get_json() or {}

    email = body.get("email")
    password = body.get("password")

    if email:
        email = str(email).strip().lower()

    if password:
        password = str(password)

    if not email:
        return error_response(
            "Email es obligatorio",
            "EMAIL_REQUIRED",
            400
        )

    if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
        return error_response(
            "Email inválido",
            "INVALID_EMAIL",
            400
        )

    if not password:
        return error_response(
            "Contraseña es obligatoria",
            "PASSWORD_REQUIRED",
            400
        )

    user = User.query.filter_by(email=email).first()

    if not user:
        return error_response(
            "Email o contraseña incorrectos",
            "INVALID_CREDENTIALS",
            401
        )

    if not user.is_active:
        return error_response(
            "Tu cuenta está desactivada. Contacta al administrador.",
            "ACCOUNT_DISABLED",
            403
        )

    if not bcrypt.check_password_hash(user.password, password):
        return error_response(
            "Email o contraseña incorrectos",
            "INVALID_CREDENTIALS",
            401
        )

    ensure_club_access(user)

    session_claims = {
        "session_version": user.session_version
    }

    access_token = create_access_token(
        identity=user.id,
        additional_claims=session_claims
    )
    refresh_token = create_refresh_token(
        identity=user.id,
        additional_claims=session_claims
    )

    decoded_refresh = decode_token(refresh_token)
    refresh_jti = decoded_refresh["jti"]

    refresh_entry = RefreshToken(
        user_id=user.id,
        jti=refresh_jti,
        expires_at=datetime.utcnow() + timedelta(days=7)
    )

    db.session.add(refresh_entry)
    db.session.commit()

    return jsonify({
        "message": "Login exitoso",
        "token": access_token,
        "refresh": refresh_token,
        "first_login": user.first_login,
        "user": user.serialize()
    }), 200

@api.route("/auth/forgot-password", methods=["POST"])
def forgot_password():
    body = request.get_json() or {}

    email = body.get("email")

    if email:
        email = str(email).strip().lower()

    if not email:
        return error_response(
            "Email es obligatorio",
            "EMAIL_REQUIRED",
            400
        )

    if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
        return error_response(
            "Email inválido",
            "INVALID_EMAIL",
            400
        )

    user = User.query.filter_by(email=email).first()

    generic_response = {
        "message": (
            "Si el email existe, enviaremos instrucciones "
            "para recuperar el acceso."
        )
    }

    if not user or not user.is_active:
        return jsonify(generic_response), 200

    PasswordResetToken.query.filter_by(
        user_id=user.id,
        used_at=None
    ).update({
        "used_at": datetime.utcnow()
    })

    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_reset_token(raw_token)

    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.utcnow() + timedelta(minutes=30)
    )

    db.session.add(reset_token)
    db.session.commit()

    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    reset_url = f"{frontend_url}/reset-password?token={raw_token}"

    try:
        send_password_reset_email(
            recipient_email=user.email,
            recipient_name=user.full_name,
            reset_url=reset_url
        )

    except Exception as error:
        db.session.delete(reset_token)
        db.session.commit()

        current_app.logger.exception(
            "No se pudo enviar el correo de recuperación",
            exc_info=error
        )

        return error_response(
            "No pudimos enviar el correo de recuperación",
            "PASSWORD_RESET_EMAIL_FAILED",
            500
        )

    return jsonify(generic_response), 200

@api.route("/auth/reset-password", methods=["POST"])
def reset_password():
    body = request.get_json() or {}

    token = body.get("token")
    new_password = body.get("new_password")

    if not token:
        return error_response(
            "Token requerido",
            "RESET_TOKEN_REQUIRED",
            400
        )

    if not new_password:
        return error_response(
            "Nueva contraseña requerida",
            "PASSWORD_REQUIRED",
            400
        )

    if len(str(new_password)) < 8:
        return error_response(
            "Debe tener al menos 8 caracteres",
            "PASSWORD_TOO_SHORT",
            400
        )

    token_hash = hash_reset_token(str(token))

    reset_token = PasswordResetToken.query.filter_by(
        token_hash=token_hash,
        used_at=None
    ).first()

    if not reset_token:
        return error_response(
            "El enlace no es válido o ya fue usado",
            "RESET_TOKEN_INVALID",
            400
        )

    if reset_token.expires_at < datetime.utcnow():
        return error_response(
            "El enlace expiró. Solicita uno nuevo.",
            "RESET_TOKEN_EXPIRED",
            400
        )

    user = User.query.get(reset_token.user_id)

    if not user or not user.is_active:
        return error_response(
            "El usuario no está disponible",
            "USER_NOT_FOUND",
            404
        )

    user.password = bcrypt.generate_password_hash(new_password).decode("utf-8")
    user.first_login = False
    user.session_version += 1

    reset_token.used_at = datetime.utcnow()

    RefreshToken.query.filter_by(
        user_id=user.id,
        revoked=False
    ).update({
        "revoked": True
    })

    db.session.commit()

    return jsonify({
        "message": "Contraseña actualizada correctamente"
    }), 200

@api.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():

    jwt_data = get_jwt()
    user_id = get_jwt_identity()
    jti = jwt_data["jti"]

    user = User.query.get(user_id)

    if not user:
        return error_response(
            "Usuario no encontrado",
            "USER_NOT_FOUND",
            404
        )

    if not user.is_active:
        return error_response(
            "Tu cuenta está desactivada. Contacta al administrador.",
            "ACCOUNT_DISABLED",
            403
        )

    ensure_club_access(user)

    stored_token = RefreshToken.query.filter_by(jti=jti).first()


    if not stored_token:
        return error_response(
            "La sesión ya no es válida. Inicia sesión nuevamente",
            "REFRESH_NOT_FOUND",
            401
        )

    if stored_token.revoked:
        return error_response(
            "La sesión fue cerrada previamente",
            "REFRESH_REVOKED",
            401
        )


    stored_token.revoked = True


    session_claims = {
        "session_version": user.session_version
    }

    new_access = create_access_token(
        identity=user_id,
        additional_claims=session_claims
    )
    new_refresh = create_refresh_token(
        identity=user_id,
        additional_claims=session_claims
    )

    decoded_new = decode_token(new_refresh)

    new_entry = RefreshToken(
        user_id=user_id,
        jti=decoded_new["jti"],
        expires_at=datetime.utcnow() + timedelta(days=7)
    )

    db.session.add(new_entry)
    db.session.commit()

    return jsonify({
        "token": new_access,
        "refresh": new_refresh
    }), 200

@api.route('/auth/set-password', methods=['POST'])
@jwt_required()
def set_password():

    user = get_current_user(allow_first_login=True)

    if user.first_login is not True:
        return error_response(
            "La contraseña inicial ya fue configurada",
            "FIRST_LOGIN_ALREADY_COMPLETED",
            409
        )

    body = request.get_json() or {}

    new_password = body.get("new_password")

    if not new_password:
        return error_response(
            "Nueva contraseña requerida",
            "PASSWORD_REQUIRED",
            400
        )

    if len(new_password) < 8:
        return error_response(
            "Debe tener al menos 8 caracteres",
            "PASSWORD_TOO_SHORT",
            400
        )

    user.password = bcrypt.generate_password_hash(new_password).decode("utf-8")
    user.first_login = False
    user.session_version += 1

    RefreshToken.query.filter_by(
        user_id=user.id,
        revoked=False
    ).update({
        "revoked": True
    })

    session_claims = {
        "session_version": user.session_version
    }

    new_access = create_access_token(
        identity=user.id,
        additional_claims=session_claims
    )
    new_refresh = create_refresh_token(
        identity=user.id,
        additional_claims=session_claims
    )

    decoded_refresh = decode_token(new_refresh)

    refresh_entry = RefreshToken(
        user_id=user.id,
        jti=decoded_refresh["jti"],
        revoked=False,
        expires_at=datetime.utcnow() + timedelta(days=7)
    )

    db.session.add(refresh_entry)

    db.session.commit()

    return jsonify({
        "message": "Contraseña actualizada correctamente",
        "token": new_access,
        "refresh": new_refresh,
        "first_login": user.first_login,
        "user": user.serialize()
    }), 200

@api.route("/logout", methods=["POST"])
@jwt_required()
def logout():

    jwt_data = get_jwt()
    jti = jwt_data["jti"]

    blocked_token = TokenBlockedList(jti=jti)
    db.session.add(blocked_token)

    user = get_current_user(allow_first_login=True)

    RefreshToken.query.filter_by(user_id=user.id, revoked=False).update({
        "revoked": True
    })

    db.session.commit()

    return jsonify({"message": "Logout exitoso"}), 200
