"""Límite de intentos en memoria para los endpoints públicos sensibles.

Cada proceso lleva sus propios contadores: con varios workers de Gunicorn el
límite efectivo se multiplica por el número de workers y un reinicio los
borra. Es una defensa mínima contra fuerza bruta, no una cuota distribuida.

La IP es `request.remote_addr`. Detrás de proxies hay que declarar cuántos
añaden X-Forwarded-For con TRUSTED_PROXY_COUNT; si no, todas las peticiones
comparten la IP del proxy y las claves por cuenta pasan a depender solo del
email.
"""
import hashlib
import math
import threading
import time
from collections import deque
from dataclasses import dataclass

from flask import current_app, jsonify, request


@dataclass(frozen=True)
class RateLimitRule:
    name: str
    limit: int
    window_seconds: int


# Intentos fallidos por IP + email.
LOGIN_RULE = RateLimitRule("login", 10, 15 * 60)
# Solicitudes por IP + email, existan o no.
FORGOT_PASSWORD_RULE = RateLimitRule("forgot-password", 5, 60 * 60)
# Tokens inválidos por IP.
RESET_PASSWORD_RULE = RateLimitRule("reset-password", 20, 15 * 60)
# Enlaces de recibo inválidos por IP.
PUBLIC_RECEIPT_RULE = RateLimitRule("public-receipt", 60, 10 * 60)


class RateLimiter:
    MAX_KEYS = 10000

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._lock = threading.Lock()
        self._hits = {}

    def _key(self, rule, parts):
        raw = "\x1f".join([rule.name, *[str(part) for part in parts]])
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _recent(self, rule, key, now):
        hits = self._hits.get(key)

        if hits is None:
            return None

        while hits and hits[0] <= now - rule.window_seconds:
            hits.popleft()

        if not hits:
            del self._hits[key]
            return None

        return hits

    def retry_after(self, rule, *parts):
        """Segundos hasta el próximo intento permitido, o None si no hay límite."""
        now = self._clock()

        with self._lock:
            hits = self._recent(rule, self._key(rule, parts), now)

            if hits is None or len(hits) < rule.limit:
                return None

            return max(1, math.ceil(hits[0] + rule.window_seconds - now))

    def hit(self, rule, *parts):
        now = self._clock()
        key = self._key(rule, parts)

        with self._lock:
            hits = self._recent(rule, key, now)

            if hits is None:
                if len(self._hits) >= self.MAX_KEYS:
                    self._evict(now)

                hits = self._hits[key] = deque()

            hits.append(now)

            while len(hits) > rule.limit:
                hits.popleft()

    def reset(self, rule, *parts):
        with self._lock:
            self._hits.pop(self._key(rule, parts), None)

    def clear(self):
        with self._lock:
            self._hits.clear()

    def _evict(self, now):
        longest_window = max(
            rule.window_seconds
            for rule in (
                LOGIN_RULE,
                FORGOT_PASSWORD_RULE,
                RESET_PASSWORD_RULE,
                PUBLIC_RECEIPT_RULE,
            )
        )

        for key in [
            key
            for key, hits in self._hits.items()
            if not hits or hits[-1] <= now - longest_window
        ]:
            del self._hits[key]

        # Si siguen sin caber, se descartan las claves más antiguas.
        while len(self._hits) >= self.MAX_KEYS:
            del self._hits[next(iter(self._hits))]


rate_limiter = RateLimiter()


def rate_limit_enabled():
    # Activo salvo que la configuración lo apague de forma explícita (tests).
    return current_app.config.get("RATE_LIMIT_ENABLED", True) is not False


def client_ip():
    return request.remote_addr or "unknown"


def limited_response(rule, *parts):
    """Respuesta 429 si `parts` agotó la regla; None en otro caso."""
    if not rate_limit_enabled():
        return None

    retry_after = rate_limiter.retry_after(rule, *parts)

    if retry_after is None:
        return None

    response = jsonify({
        "error": True,
        "message": (
            "Demasiados intentos. Espera unos minutos e inténtalo de nuevo."
        ),
        "code": "RATE_LIMITED",
    })
    response.status_code = 429
    response.headers["Retry-After"] = str(retry_after)
    return response


def record_attempt(rule, *parts):
    if rate_limit_enabled():
        rate_limiter.hit(rule, *parts)


def reset_attempts(rule, *parts):
    rate_limiter.reset(rule, *parts)
