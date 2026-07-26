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