# Autenticación

> **Nivel:** Desarrollo
>
> **Audiencia:** Desarrolladores

---

## 1. Objetivo

El sistema de autenticación de SportFlow garantiza que únicamente los usuarios autorizados puedan acceder a la plataforma.

La autenticación se basa en JSON Web Tokens (JWT), permitiendo proteger la API REST y controlar el acceso a los diferentes recursos del sistema.

---

## 2. Descripción general

Todo usuario debe autenticarse antes de acceder a cualquier funcionalidad protegida.

Una vez autenticado correctamente, el backend genera un token JWT que será utilizado por el frontend para realizar las solicitudes posteriores.

Las rutas protegidas únicamente aceptan solicitudes que contengan un token válido.

---

## 3. Arquitectura

```
Usuario

      │

      ▼

Login

      │

      ▼

Flask API

      │

Verificación

      │

      ▼

JWT

      │

      ▼

Frontend

      │

      ▼

Solicitudes autenticadas
```

---

## 4. Tecnologías utilizadas

Actualmente el sistema utiliza:

- Flask
- Flask-JWT-Extended
- SQLAlchemy
- PostgreSQL

---

## 5. Flujo de autenticación

El proceso de autenticación sigue el siguiente flujo:

1. El usuario introduce sus credenciales.
2. El backend valida el correo y la contraseña.
3. Si las credenciales son válidas, se genera un JWT.
4. El frontend almacena el token.
5. El token acompaña todas las solicitudes protegidas.
6. El backend valida el token antes de procesar la petición.

---

## 6. Recuperación de contraseña

SportFlow incorpora un mecanismo seguro para recuperar la contraseña.

El flujo es el siguiente:

1. El usuario solicita recuperar la contraseña.
2. Se genera un token temporal.
3. El token se almacena en la base de datos.
4. Se envía un correo mediante Resend.
5. El usuario accede al enlace recibido.
6. Se valida el token.
7. Se establece la nueva contraseña.
8. El token queda invalidado.

---

## 7. Primer acceso

Cuando un usuario accede por primera vez a la plataforma debe establecer una contraseña definitiva.

Hasta completar este proceso no podrá utilizar el sistema con normalidad.

---

## 8. Protección de rutas

Las rutas protegidas requieren un JWT válido.

Si el token no existe, ha expirado o es inválido, el backend devuelve una respuesta de autenticación no válida.

El frontend debe gestionar estos casos redirigiendo al usuario al inicio de sesión cuando corresponda.

---

## 9. Seguridad

El sistema implementa las siguientes medidas de seguridad:

- Contraseñas cifradas.
- Tokens JWT.
- Variables sensibles mediante `.env`.
- Tokens temporales para recuperación.
- Invalidación de tokens utilizados.
- Protección de rutas privadas.

---

## 10. Buenas prácticas

Se recomienda:

- No almacenar contraseñas en texto plano.
- No compartir tokens JWT.
- Invalidar tokens de recuperación una vez utilizados.
- Mantener protegidas las variables de entorno.
- Verificar siempre la autenticación en el backend.

---

## 11. Troubleshooting

### El usuario no puede iniciar sesión

Verificar:

- Correo electrónico.
- Contraseña.
- Estado del usuario.

---

### Token inválido

Comprobar:

- Expiración del JWT.
- Token enviado por el frontend.

---

### Recuperación de contraseña no funciona

Verificar:

- Resend.
- Token generado.
- Token almacenado en PostgreSQL.

---

## 12. Checklist

Antes de desplegar cambios relacionados con autenticación verificar:

- Inicio de sesión.
- Cierre de sesión.
- Recuperación de contraseña.
- Primer acceso.
- Validación de rutas protegidas.

---

## 13. Estado actual

| Componente | Estado |
|------------|--------|
| Login | ✅ |
| JWT | ✅ |
| Recuperación de contraseña | ✅ |
| Primer acceso | ✅ |
| Protección de rutas | ✅ |

---

## 14. Archivos relacionados

| Recurso | Descripción |
|----------|-------------|
| `src/api/routes.py` | Endpoints de autenticación. |
| `src/models.py` | Modelos relacionados con usuarios y recuperación de contraseña. |
| `src/api/email_service.py` | Envío del correo de recuperación. |
| `docs/03-resend.md` | Configuración del servicio de correo. |

---

## 15. Información del documento

| Campo | Valor |
|--------|-------|
| Documento | 09-autenticacion.md |
| Proyecto | SportFlow |
| Versión | 1.0 |
| Última actualización | 2026-07-26 |
| Autor | Sousan Wong |