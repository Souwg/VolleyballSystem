import os
from dotenv import load_dotenv
from datetime import timedelta
from flask import Flask, request, jsonify, send_from_directory
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager, get_jwt
from flask_cors import CORS
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix
from src.api.extensions import bcrypt

load_dotenv()



from src.api.utils import APIException, generate_sitemap
from src.api.models import db, User, TokenBlockedList
from src.api.routes import api
from src.api.admin import is_flask_admin_enabled, setup_admin
from src.api.commands import setup_commands
from src.api.request_validation import (
    ApiRequest,
    InputValidationError,
    register_column_limit_guard,
    validate_json_body,
)
from src.api.upload_utils import MAX_UPLOAD_REQUEST_SIZE

# -------------------------------------------------------------------
# CREATE APP
# -------------------------------------------------------------------

ENV = (os.getenv("APP_ENV") or "production").strip().lower()
static_file_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), '../public/')

token_secret = (os.getenv("TOKEN_SECRET") or "").strip()
if ENV != "development":
    if (
        len(token_secret) < 32
        or len(set(token_secret)) == 1
        or token_secret.lower() in {
            "any key works",
            "dev-secret-local",
            "sample key"
        }
    ):
        raise RuntimeError(
            "TOKEN_SECRET es obligatorio en producción y debe tener al menos 32 caracteres"
        )
    jwt_secret = token_secret
else:
    jwt_secret = token_secret or os.getenv("FLASK_APP_KEY") or "dev-secret-local"

app = Flask(__name__)
app.url_map.strict_slashes = False
app.request_class = ApiRequest

# Tope de cualquier request: la imagen más grande admitida (jugadora) más
# margen para multipart. El logo del club comparte este tope y conserva su
# propio límite, menor.
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_REQUEST_SIZE

# Proxies de confianza que añaden X-Forwarded-For delante de la app. Con 0 la
# IP del cliente es la de la conexión directa (ver .env.example).
trusted_proxy_count = int(os.getenv("TRUSTED_PROXY_COUNT") or 0)

if trusted_proxy_count > 0:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=trusted_proxy_count)

bcrypt.init_app(app)  
# -------------------------------------------------------------------
# CORS — THIS FIXES YOUR ERROR
# -------------------------------------------------------------------
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

# -------------------------------------------------------------------
# JWT CONFIG
# -------------------------------------------------------------------
app.config["JWT_SECRET_KEY"] = jwt_secret
# Access corto (seguro)
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(minutes=15)

# Refresh largo (sesión real SaaS)
app.config["JWT_REFRESH_TOKEN_EXPIRES"] = timedelta(days=7)

# Usaremos headers (como ya trabajas)
app.config["JWT_TOKEN_LOCATION"] = ["headers"]

# Necesario para distinguir tipos de token
app.config["JWT_ALGORITHM"] = "HS256"
jwt = JWTManager(app)

@jwt.token_in_blocklist_loader
def check_if_token_revoked(jwt_header, jwt_payload: dict) -> bool:
    jti = jwt_payload["jti"]
    token = TokenBlockedList.query.filter_by(jti=jti).first()

    if token is not None:
        return True

    user = User.query.get(jwt_payload["sub"])

    if not user:
        return False

    token_session_version = jwt_payload.get(
        "session_version",
        0
    )

    return token_session_version != user.session_version

# -------------------------------------------------------------------
# DATABASE
# -------------------------------------------------------------------
db_url = os.getenv("DATABASE_URL")

if db_url is not None:
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url.replace("postgres://", "postgresql://")
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:////tmp/test.db"

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

MIGRATE = Migrate(app, db, compare_type=True)
db.init_app(app)
register_column_limit_guard(db.session)

# -------------------------------------------------------------------
# BLUEPRINTS & ADMIN
# -------------------------------------------------------------------

# Flask-Admin requiere activación explícita: ver ENABLE_FLASK_ADMIN en .env.example
if is_flask_admin_enabled():
    setup_admin(app)

setup_commands(app)
app.register_blueprint(api, url_prefix='/api')
app.before_request(validate_json_body)


@app.route('/api/<path:path>', methods=['GET', 'POST'])
def api_not_found(path):
    return jsonify({
        "error": True,
        "message": "Recurso no encontrado",
        "code": "NOT_FOUND"
    }), 404

# -------------------------------------------------------------------
# ERROR HANDLER
# -------------------------------------------------------------------
@app.errorhandler(APIException)
def handle_invalid_usage(error):
    return jsonify(error.to_dict()), error.status_code

@app.errorhandler(InputValidationError)
def handle_input_validation_error(error):
    db.session.rollback()
    return jsonify(error.to_dict()), error.status_code

# -------------------------------------------------------------------
# HTTP ERRORS (Werkzeug)
# -------------------------------------------------------------------
HTTP_ERRORS = {
    400: ("BAD_REQUEST", "La solicitud no es válida."),
    401: ("UNAUTHORIZED", "Debes iniciar sesión para continuar."),
    403: ("FORBIDDEN", "No tienes permisos para realizar esta acción."),
    404: ("NOT_FOUND", "Recurso no encontrado"),
    405: ("METHOD_NOT_ALLOWED", "Método no permitido para este recurso."),
    413: (
        "PAYLOAD_TOO_LARGE",
        "La solicitud supera el tamaño máximo permitido."
    ),
    415: (
        "UNSUPPORTED_MEDIA_TYPE",
        "El contenido de la solicitud debe enviarse como JSON."
    ),
    429: (
        "RATE_LIMITED",
        "Demasiados intentos. Espera unos minutos e inténtalo de nuevo."
    ),
}


@app.errorhandler(HTTPException)
def handle_http_exception(error):
    """
    Los errores HTTP de Werkzeug (JSON malformado, 404, 405, 413...)
    conservan su estado y responden con el contrato JSON del API.
    """

    if error.code is None or error.code >= 500:
        return handle_unexpected_error(error)

    db.session.rollback()

    code, message = HTTP_ERRORS.get(
        error.code,
        ("HTTP_ERROR", "No se pudo procesar la solicitud.")
    )
    response = jsonify({
        "error": True,
        "message": message,
        "code": code
    })
    response.status_code = error.code

    # Conserva cabeceras como Allow (405) o Retry-After (429).
    for header, value in error.get_headers():
        if header.lower() != "content-type":
            response.headers[header] = value

    return response

# -------------------------------------------------------------------
# GLOBAL EXCEPTION HANDLER (Production Safety Net)
# -------------------------------------------------------------------
@app.errorhandler(Exception)
def handle_unexpected_error(error):
    """
    Captura cualquier excepción no controlada y mantiene
    el contrato JSON del API. Evita respuestas HTML 500.
    """

    # Muy importante: si algo falló en medio de una transacción
    db.session.rollback()

    # Log interno (para que en consola / docker logs sí veas el error real)
    app.logger.exception("Unhandled exception:", exc_info=error)

    return jsonify({
        "error": True,
        "message": "Ocurrió un error interno",
        "code": "INTERNAL_ERROR"
    }), 500

# -------------------------------------------------------------------
# SITEMAP & STATIC
# -------------------------------------------------------------------
@app.route('/')
def sitemap():
    if ENV == "development":
        return generate_sitemap(app)
    return send_from_directory(static_file_dir, 'index.html')

@app.route('/<path:path>', methods=['GET'])
def serve_any_other_file(path):
    receipts_dir = os.path.realpath(
        os.path.join(static_file_dir, 'uploads', 'receipts')
    )
    uploads_dir = os.path.realpath(os.path.join(static_file_dir, 'uploads'))
    requested_file = os.path.realpath(os.path.join(static_file_dir, path))

    if (
        requested_file == receipts_dir
        or requested_file.startswith(receipts_dir + os.sep)
    ):
        return jsonify({
            "error": True,
            "message": "Recibo no encontrado",
            "code": "RECEIPT_NOT_FOUND"
        }), 404

    # /admin/clients es la única pantalla del frontend bajo /admin. Si Flask-Admin
    # está activo, sus rutas son más específicas y no llegan hasta aquí.
    if (
        (path == "admin" or path.startswith("admin/"))
        and path.rstrip("/") != "admin/clients"
    ):
        return jsonify({
            "error": True,
            "message": "Recurso no encontrado",
            "code": "NOT_FOUND"
        }), 404

    if not os.path.isfile(os.path.join(static_file_dir, path)):
        path = 'index.html'
    response = send_from_directory(static_file_dir, path)
    response.cache_control.max_age = 0

    # Lo subido por usuarios se sirve solo con el tipo de su extensión.
    if requested_file.lower().startswith(uploads_dir.lower() + os.sep):
        response.headers["X-Content-Type-Options"] = "nosniff"

    return response

# -------------------------------------------------------------------
# RUN
# -------------------------------------------------------------------
if __name__ == '__main__':
    PORT = int(os.environ.get('PORT', 3005))
    app.run(host='0.0.0.0', port=PORT, debug=True)
