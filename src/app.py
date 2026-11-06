import os
import posixpath
from dotenv import load_dotenv
from datetime import timedelta
from urllib.parse import urlsplit
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
from src.api.log_safety import ExceptionMessageRedactor
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
# Los logs con traceback conservan clase, contexto y frames, sin el mensaje
# de la excepción (puede traer valores del usuario). Ver log_safety.
app.logger.addFilter(ExceptionMessageRedactor())

# Tope de cualquier request: la imagen más grande admitida (jugadora) más
# margen para multipart. El logo del club comparte este tope y conserva su
# propio límite, menor.
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_REQUEST_SIZE

# Proxies de confianza que añaden X-Forwarded-For delante de la app. Con 0 la
# IP del cliente es la de la conexión directa (ver .env.example).
trusted_proxy_count = int(os.getenv("TRUSTED_PROXY_COUNT") or 0)

if trusted_proxy_count > 0:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=trusted_proxy_count)

# Los PDF de recibos se guardan fuera de public/ y solo se entregan por la API.
# En producción debe apuntar a un volumen persistente (ver .env.example).
project_root = os.path.realpath(
    os.path.join(os.path.dirname(os.path.realpath(__file__)), "..")
)
private_receipt_root = os.path.realpath(os.path.join(
    project_root,
    (os.getenv("PRIVATE_RECEIPT_ROOT") or "").strip()
    or os.path.join("instance", "receipts")
))
public_root = os.path.realpath(static_file_dir)

if os.path.commonpath([private_receipt_root, public_root]) == public_root:
    raise RuntimeError("PRIVATE_RECEIPT_ROOT no puede estar dentro de public/")

app.config["PRIVATE_RECEIPT_ROOT"] = private_receipt_root

if ENV != "development" and not (os.getenv("PRIVATE_RECEIPT_ROOT") or "").strip():
    app.logger.warning(
        "PRIVATE_RECEIPT_ROOT no está definido: los recibos se guardan en %s",
        private_receipt_root
    )

bcrypt.init_app(app)  
# -------------------------------------------------------------------
# CORS
# -------------------------------------------------------------------
def parse_allowed_origins(value):
    origins = []

    for entry in (value or "").split(","):
        parts = urlsplit(entry.strip())

        if (
            parts.scheme.lower() in ("http", "https")
            and parts.netloc
            and "@" not in parts.netloc
        ):
            origins.append(
                f"{parts.scheme.lower()}://{parts.netloc.lower()}"
            )

    return origins


# Solo orígenes explícitos: CORS_ALLOWED_ORIGINS (separados por coma) o, sin
# esa variable, el origen de FRONTEND_URL. El JWT viaja en la cabecera
# Authorization, así que no se habilitan credenciales (cookies).
cors_allowed_origins = parse_allowed_origins(
    os.getenv("CORS_ALLOWED_ORIGINS") or os.getenv("FRONTEND_URL")
)
CORS(
    app,
    resources={r"/api/*": {"origins": cors_allowed_origins}},
    supports_credentials=False
)

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
# Los errores SQL no incluyen los valores enlazados (emails, contraseñas...).
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {"hide_parameters": True}

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

    # Log interno sin cuerpo, cabeceras ni la URL concreta (puede llevar
    # tokens): bastan el método y la ruta registrada.
    route = request.url_rule.rule if request.url_rule else "sin ruta"
    app.logger.exception(
        "Unhandled exception en %s %s",
        request.method,
        route,
        exc_info=error
    )

    return jsonify({
        "error": True,
        "message": "Ocurrió un error interno",
        "code": "INTERNAL_ERROR"
    }), 500

# -------------------------------------------------------------------
# SECURITY HEADERS
# -------------------------------------------------------------------
# CSP mínima que no rompe la SPA: sin framing ni <base>/<form> hacia otros
# orígenes. Una política completa (script/style/connect) necesita conocer los
# orígenes reales de producción y queda pendiente.
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "same-origin",
    "Content-Security-Policy": (
        "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    ),
}


@app.after_request
def set_security_headers(response):
    for header, value in SECURITY_HEADERS.items():
        response.headers.setdefault(header, value)

    return response

# -------------------------------------------------------------------
# SITEMAP & STATIC
# -------------------------------------------------------------------
@app.route('/')
def sitemap():
    if ENV == "development":
        return generate_sitemap(app)
    return send_from_directory(static_file_dir, 'index.html')

def is_private_upload_path(path):
    """
    Los recibos legacy de public/uploads/receipts nunca se sirven como
    estáticos. Además de la ruta normalizada sin distinguir mayúsculas, se
    compara la identidad de cada directorio con la carpeta de recibos: en un
    sistema de archivos que no distingue mayúsculas o que normaliza Unicode,
    una variante del nombre resuelve al mismo directorio sin coincidir como texto.
    """
    normalized = posixpath.normpath("/" + path.replace("\\", "/")).casefold()

    if (
        normalized == "/uploads/receipts"
        or normalized.startswith("/uploads/receipts/")
    ):
        return True

    receipts_dir = os.path.realpath(
        os.path.join(static_file_dir, 'uploads', 'receipts')
    )
    requested_file = os.path.realpath(os.path.join(static_file_dir, path))

    if (
        requested_file.casefold() == receipts_dir.casefold()
        or requested_file.casefold().startswith(
            receipts_dir.casefold() + os.sep
        )
    ):
        return True

    if not os.path.isdir(receipts_dir):
        return False

    probe = requested_file

    while True:
        try:
            if os.path.samefile(probe, receipts_dir):
                return True
        except OSError:
            pass

        parent = os.path.dirname(probe)

        if parent == probe:
            return False

        probe = parent


@app.route('/<path:path>', methods=['GET'])
def serve_any_other_file(path):
    if is_private_upload_path(path):
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
    return response

# -------------------------------------------------------------------
# RUN
# -------------------------------------------------------------------
if __name__ == '__main__':
    PORT = int(os.environ.get('PORT', 3005))
    app.run(host='0.0.0.0', port=PORT, debug=True)
