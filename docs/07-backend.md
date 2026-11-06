# Backend

> **Nivel:** Desarrollo
>
> **Audiencia:** Desarrolladores

---

## 1. Objetivo

El backend de SportFlow es el encargado de implementar toda la lógica de negocio de la plataforma.

Entre sus responsabilidades se encuentran:

- Autenticación de usuarios.
- Gestión de clubes.
- Administración de categorías.
- Gestión de equipos.
- Administración de jugadores.
- Gestión de entrenamientos.
- Gestión de partidos.
- Administración de pagos.
- Envío de correos electrónicos.
- Exposición de la API REST utilizada por el frontend.

Todo el backend está desarrollado en Python utilizando Flask.

---

## 2. Descripción general

El backend sigue una arquitectura basada en una API REST.

El frontend consume los diferentes endpoints mediante solicitudes HTTP.

La aplicación es completamente desacoplada del frontend.

Toda la lógica del negocio reside en el backend.

---

## 3. Arquitectura

```
Frontend (React)

        │

HTTP / JSON

        │

Flask API

        │

Routes

        │

Servicios

        │

SQLAlchemy

        │

PostgreSQL
```

---

## 4. Tecnologías utilizadas

Actualmente el backend utiliza:

- Python
- Flask
- SQLAlchemy
- Flask-JWT-Extended
- Alembic
- PostgreSQL
- Gunicorn
- Resend

---

## 5. Organización del proyecto

La estructura principal del backend es:

```text
src/
│
├── api/
├── models.py
├── admin.py
├── app.py
├── extensions.py
├── utils.py
└── ...
```

Cada archivo tiene una responsabilidad específica para facilitar el mantenimiento y la escalabilidad del proyecto.

---

## 6. API REST

Toda la comunicación con el frontend se realiza mediante una API REST.

Las respuestas se envían en formato JSON.

Los principales módulos de la API incluyen:

- Autenticación.
- Clubes.
- Categorías.
- Equipos.
- Jugadores.
- Entrenamientos.
- Partidos.
- Pagos.
- Administración.

---

## 7. Modelos

Los modelos representan las entidades principales del sistema.

Actualmente incluyen, entre otros:

- Usuario.
- Club.
- Categoría.
- Equipo.
- Jugador.
- Entrenamiento.
- Partido.
- Pago.

Los modelos son administrados mediante SQLAlchemy.

---

## 8. Servicios

La lógica que puede reutilizarse entre distintos módulos debe implementarse mediante servicios.

Ejemplo actual:

```text
src/api/email_service.py
```

Este servicio centraliza el envío de correos electrónicos utilizando Resend.

---

## 9. Validaciones

El backend es responsable de validar toda la información recibida desde el frontend.

Entre las validaciones realizadas se encuentran:

- Campos obligatorios.
- Formatos de datos.
- Relaciones entre entidades.
- Permisos del usuario autenticado.
- Reglas de negocio.

Las validaciones del frontend mejoran la experiencia del usuario, pero nunca sustituyen las validaciones del backend.

---

## 10. Seguridad

El backend implementa diferentes mecanismos de seguridad:

- Autenticación mediante JWT.
- Contraseñas cifradas.
- Variables de entorno para datos sensibles.
- Validación de permisos.
- Protección de rutas privadas.

### Recibos privados

- Los PDF nuevos se guardan en `PRIVATE_RECEIPT_ROOT`, fuera de `public/`
  (por defecto `instance/receipts` del proyecto). La app no arranca si esa
  ruta queda dentro de `public/`.
- Solo se entregan por dos endpoints: `GET /api/payment-receipts/<id>/pdf`
  (JWT, permiso de finanzas y recibo del club) y el enlace público firmado
  `GET /api/payment-receipts/public/<token>`.
- Los PDF emitidos antes siguen en `public/uploads/receipts` y no se mueven:
  los endpoints los leen como respaldo y Flask rechaza cualquier acceso
  estático a esa carpeta (mayúsculas, `//`, `./`, `..`, separadores
  codificados y la identidad del directorio).
- Si Nginx sirve `/uploads` directamente debe excluir `/uploads/receipts`;
  esa configuración no está en el repositorio y no se ha verificado.

### Cabeceras HTTP y CORS

- Todas las respuestas llevan `X-Content-Type-Options: nosniff`,
  `Referrer-Policy: same-origin` y una CSP mínima
  (`frame-ancestors 'none'; base-uri 'self'; form-action 'self'`).
- Una CSP completa queda pendiente: la SPA usa `style-loader` (estilos
  inline), Bootstrap y Popper desde jsDelivr, Font Awesome desde cdnjs,
  Google Fonts e imágenes `blob:`, y el origen de la API depende de
  `REACT_APP_BACKEND_URL`, que debe confirmarse en producción.
- HSTS se configura donde termina HTTPS (Nginx/Cloudflare), no en Flask.
- CORS solo acepta los orígenes de `CORS_ALLOWED_ORIGINS` o, sin esa
  variable, el de `FRONTEND_URL`. No se habilitan credenciales: el JWT viaja
  en `Authorization`. Si la SPA se sirve desde más de un origen sin
  redirección (por ejemplo con y sin `www`) y llama a la API en otro, todos
  esos orígenes deben figurar en `CORS_ALLOWED_ORIGINS`.

### Logs

- Los registros con traceback conservan la clase, el contexto SQL sin valores
  y los frames, pero no el mensaje de la excepción (puede traer datos del
  usuario). Las sentencias SQL se registran sin parámetros
  (`hide_parameters`).
- Los logs de acceso del servidor (Gunicorn/Nginx) pueden incluir la URL del
  enlace público de recibos y del restablecimiento de contraseña, que llevan
  un token: su configuración está fuera del repositorio.

---

## 11. Buenas prácticas

Para mantener el backend organizado se recomienda:

- Mantener cada módulo con una única responsabilidad.
- Evitar duplicar lógica de negocio.
- Reutilizar servicios comunes.
- Documentar nuevos endpoints.
- Utilizar migraciones para cambios en la base de datos.
- Mantener consistencia en los nombres de rutas y modelos.

---

## 12. Troubleshooting

### Error al iniciar Flask

Verificar:

- Variables de entorno.
- Dependencias instaladas.
- Logs de Gunicorn.

---

### Error de conexión con PostgreSQL

Comprobar:

- DATABASE_URL.
- Estado del contenedor PostgreSQL.
- Configuración de Docker Compose.

---

### Error en un endpoint

Revisar:

- Logs de la aplicación.
- Validaciones del endpoint.
- Respuesta HTTP devuelta.

---

## 13. Checklist

Antes de desplegar cambios en el backend verificar:

- Código probado.
- Migraciones generadas (si aplica).
- Endpoints funcionando.
- Variables de entorno correctas.
- Despliegue realizado correctamente.

---

## 14. Estado actual

| Componente | Estado |
|------------|--------|
| Flask | ✅ |
| SQLAlchemy | ✅ |
| JWT | ✅ |
| Alembic | ✅ |
| Resend | ✅ |
| API REST | ✅ |

---

## 15. Archivos relacionados

| Recurso | Descripción |
|----------|-------------|
| `src/app.py` | Punto de entrada de la aplicación Flask. |
| `src/models.py` | Modelos de la base de datos. |
| `src/api/` | Endpoints y lógica de la API. |
| `src/api/email_service.py` | Servicio de envío de correos. |
| `migrations/` | Migraciones de Alembic. |

---

## 16. Información del documento

| Campo | Valor |
|--------|-------|
| Documento | 07-backend.md |
| Proyecto | SportFlow |
| Versión | 1.0 |
| Última actualización | 2026-07-26 |
| Autor | Sousan Wong |

---

## Flask-Admin

Está apagado por defecto. Solo se registra con `APP_ENV=development` y
`ENABLE_FLASK_ADMIN=1`; fuera de desarrollo la variable se ignora y `/admin`
responde 404. Con la opción activa, cada vista exige un JWT de `system_admin` en
la cabecera `Authorization`. El formulario de Club no permite editar el modo de
acceso de entrenadores: lo decide el dueño del club desde "Mi club".
