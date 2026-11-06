import os
import uuid

from flask import request
from PIL import Image
from werkzeug.exceptions import RequestEntityTooLarge

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

MAX_PLAYER_IMAGE_SIZE = 8 * 1024 * 1024
MAX_CLUB_IMAGE_SIZE = 2 * 1024 * 1024

# Tope del request completo (MAX_CONTENT_LENGTH): la imagen más grande
# admitida más margen para el sobrecosto de multipart.
MAX_UPLOAD_REQUEST_SIZE = MAX_PLAYER_IMAGE_SIZE + 1024 * 1024

# Formato real detectado por Pillow para cada extensión permitida.
IMAGE_FORMAT_BY_EXTENSION = {
    "png": "PNG",
    "jpg": "JPEG",
    "jpeg": "JPEG",
    "webp": "WEBP",
}

# Content-Type que el navegador puede declarar para cada formato.
IMAGE_MIMETYPES_BY_FORMAT = {
    "PNG": {"image/png"},
    "JPEG": {"image/jpeg", "image/jpg", "image/pjpeg"},
    "WEBP": {"image/webp"},
}

INVALID_IMAGE_FORMAT_ERROR = (
    "Formato inválido. Usa PNG, JPG o WEBP",
    "INVALID_IMAGE_FORMAT",
    400
)

IMAGE_REQUIRED_ERROR = (
    "Debes seleccionar una imagen",
    "IMAGE_REQUIRED",
    400
)


def allowed_image_file(filename):
    return (
        "." in filename and
        filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS
    )


def _detected_image_format(image):
    try:
        with Image.open(image.stream) as decoded:
            decoded.verify()
            return decoded.format
    # Cualquier fallo al decodificar significa que no es una imagen válida.
    except Exception:
        return None
    finally:
        image.stream.seek(0)


def get_uploaded_image(max_size, too_large_message):
    """
    Valida el archivo del campo `image` y devuelve (archivo, extensión, error).

    `error` es una tupla para error_response. La extensión solo se usa si
    coincide con el formato real del contenido; el nombre original nunca llega
    al disco.
    """

    try:
        image = request.files.get("image")
    except RequestEntityTooLarge:
        return None, None, (too_large_message, "IMAGE_TOO_LARGE", 413)

    if image is None or not image.filename:
        return None, None, IMAGE_REQUIRED_ERROR

    if not allowed_image_file(image.filename):
        return None, None, INVALID_IMAGE_FORMAT_ERROR

    extension = image.filename.rsplit(".", 1)[1].lower()

    image.stream.seek(0, os.SEEK_END)
    image_size = image.stream.tell()
    image.stream.seek(0)

    if image_size > max_size:
        return None, None, (too_large_message, "IMAGE_TOO_LARGE", 400)

    detected_format = _detected_image_format(image)

    if detected_format != IMAGE_FORMAT_BY_EXTENSION[extension]:
        return None, None, INVALID_IMAGE_FORMAT_ERROR

    declared_mimetype = (image.mimetype or "").lower()

    if (
        declared_mimetype not in ("", "application/octet-stream")
        and declared_mimetype not in IMAGE_MIMETYPES_BY_FORMAT[detected_format]
    ):
        return None, None, INVALID_IMAGE_FORMAT_ERROR

    return image, extension, None


def save_uploaded_image(image, folder, prefix, extension):
    """Guarda la imagen con nombre UUID bajo public/uploads/<folder>."""
    upload_folder = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "../../public/uploads",
            folder
        )
    )

    os.makedirs(upload_folder, exist_ok=True)

    filename = f"{prefix}-{uuid.uuid4().hex}.{extension}"
    file_path = os.path.join(upload_folder, filename)
    image.save(file_path)

    return f"/uploads/{folder}/{filename}", file_path


def discard_uploaded_image(file_path):
    try:
        os.remove(file_path)
    except FileNotFoundError:
        pass
