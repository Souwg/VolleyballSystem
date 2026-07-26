# Resend

## 1. Objetivo

Resend es el proveedor oficial de correo electrónico utilizado por SportFlow para el envío de correos transaccionales desde el dominio:

```
sportflow.club
```

Su función es garantizar el envío confiable de correos relacionados con autenticación, recuperación de contraseña, pagos y futuras notificaciones automáticas del sistema.

---

## 2. Descripción general

SportFlow utiliza Resend como plataforma principal para el envío de correos electrónicos.

Actualmente el dominio se encuentra completamente verificado y listo para producción.

El remitente configurado es:

```
SportFlow <noreply@sportflow.club>
```

---

## 3. Arquitectura

```
Usuario
      │
      ▼
Flask
      │
      ▼
email_service.py
      │
      ▼
Resend API
      │
      ▼
Internet
      │
      ▼
Proveedor de correo
      │
      ▼
Usuario final
```

Todo el envío de correos pasa obligatoriamente por:

```
src/api/email_service.py
```

No deben realizarse llamadas directas a Resend desde otros módulos.

---

## 4. Componentes utilizados

### Servicio

Resend

### Dominio

```
sportflow.club
```

### Remitente

```
SportFlow <noreply@sportflow.club>
```

### Librería

```
resend
```

Instalada mediante:

```
Pipfile
```

---

## 5. Configuración

### Variables de entorno

El servicio utiliza las siguientes variables:

```env
RESEND_API_KEY=
MAIL_FROM_EMAIL=noreply@sportflow.club
MAIL_FROM_NAME=SportFlow
```

Estas variables se encuentran en:

```
/opt/sportflow/docker/.env
```

La API Key nunca debe almacenarse dentro del repositorio.

---

## 6. Configuración DNS

Para permitir el envío desde el dominio fue necesario verificar:

```
sportflow.club
```

En Cloudflare se añadieron registros:

- TXT (DKIM)
- MX
- TXT (SPF)
- TXT (DMARC)

Todos estos registros deben permanecer en:

```
DNS only
```

Nunca deben utilizar Proxy de Cloudflare.

---

## 7. Proceso de implementación

La integración de Resend se realizó durante el despliegue inicial del entorno de producción.

### Pasos realizados

1. Creación de la cuenta en Resend.
2. Registro del dominio `sportflow.club`.
3. Verificación del dominio mediante Cloudflare.
4. Configuración de los registros DNS:
   - DKIM
   - SPF
   - MX
   - DMARC
5. Generación de una API Key de producción.
6. Configuración de las variables de entorno del contenedor Docker.
7. Recreación del contenedor de la aplicación.
8. Prueba de envío utilizando la recuperación de contraseña.
9. Verificación del correo recibido correctamente en Gmail.

Resultado:

- Dominio verificado.
- API Key funcionando.
- Envío de correos operativo.
- Sistema listo para producción.

Esta configuración únicamente fue necesaria durante el despliegue inicial.

Una vez verificado el dominio, únicamente será necesario generar una nueva API Key si la actual es revocada o comprometida.

## 7.1. Flujo de funcionamiento

El flujo actual es:

1. Flask solicita el envío.
2. email_service.py prepara el contenido.
3. Se leen las variables de entorno.
4. Se inicializa Resend.
5. Se genera el HTML.
6. Se envía la solicitud mediante la API.
7. Resend entrega el correo.

---

## 8. Funciones implementadas

Actualmente existe:

```
send_password_reset_email()
```

Ubicada en:

```
src/api/email_service.py
```

Esta función envía el correo para restablecimiento de contraseña.

---

## 9. Casos de uso futuros

Resend será utilizado para:

- Bienvenida de nuevos usuarios.
- Envío de credenciales.
- Recuperación de contraseña.
- Recibos de pago.
- Confirmación de pagos.
- Recordatorios de mensualidad.
- Recordatorios de entrenamiento.
- Avisos de partidos.
- Notificaciones administrativas.

---

## 10. Seguridad

Nunca compartir:

- API Key.
- Variables del archivo `.env`.
- Tokens de recuperación.
- Credenciales de usuarios.

Si una API Key queda comprometida:

1. Revocarla desde Resend.
2. Crear una nueva.
3. Actualizar `.env`.
4. Recrear el contenedor.

---

## 11. Mantenimiento

Después de modificar únicamente variables de entorno no es necesario reconstruir la imagen Docker.

Basta con recrear el contenedor:

```bash
docker compose \
  --env-file .env \
  -f compose.yml \
  up -d --force-recreate app
```

---

## 12. Pruebas realizadas

Durante la implementación se verificó correctamente:

- Envío mediante Resend.
- Lectura de variables de entorno.
- Inicialización de la librería `resend`.
- Generación del HTML del correo.
- Entrega del mensaje.
- Recepción en Gmail.
- Correcto funcionamiento de la recuperación de contraseña.

Resultado:

Todas las pruebas fueron satisfactorias.


## 13. Troubleshooting

### Error

```
RESEND_API_KEY no está configurada
```

Verificar:

- Variable en `.env`.
- Recreación del contenedor.

---

### Error

```
MAIL_FROM_EMAIL no está configurado
```

Verificar:

```
MAIL_FROM_EMAIL
```

---

### Dominio Pending

Esperar propagación DNS.

Verificar registros en Cloudflare.

---

### Correos no llegan

Revisar:

- Spam.
- Dashboard de Resend.
- Estado del dominio.
- API Key.

---

## 14. Checklist

Antes de dar por finalizada una instalación verificar:

- Dominio verificado.
- API Key configurada.
- Variables cargadas.
- Contenedor recreado.
- Correo de prueba enviado.
- Correo recibido correctamente.

---

## 15. Estado actual

| Componente | Estado |
|------------|--------|
| Cuenta Resend | ✅ |
| Dominio | ✅ |
| DNS | ✅ |
| API Key | ✅ |
| Docker | ✅ |
| Correo de prueba | ✅ |
| Recuperación de contraseña | ✅ |

---

## 16. Historial de implementación

La integración de Resend quedó completamente funcional durante el despliegue inicial de producción.

### Acciones realizadas

- Creación de cuenta en Resend.
- Verificación del dominio sportflow.club.
- Configuración de Cloudflare como proveedor DNS.
- Creación de registros:
  - DKIM
  - SPF
  - MX
  - DMARC
- Generación de API Key.
- Configuración de variables de entorno.
- Recreación del contenedor Docker.
- Prueba de recuperación de contraseña.
- Recepción satisfactoria del correo.

Resultado:

Estado del dominio:

✅ Verified

Servicio listo para producción.

## 17. Archivos relacionados

## 17. Archivos relacionados

| Archivo | Descripción |
|----------|-------------|
| `src/api/email_service.py` | Servicio encargado del envío de correos mediante Resend. |
| `docker/.env` | Variables de entorno utilizadas por el contenedor Docker. |
| `.env.example` | Plantilla de variables necesarias para el proyecto. |
| `Pipfile` | Dependencia de la librería `resend`. |

Ejemplo

.env.example

Proveedor DNS

Cloudflare

Proveedor SMTP

Resend


---

## Información del documento

| Campo | Valor |
|--------|-------|
| Documento | 03-resend.md |
| Proyecto | SportFlow |
| Versión | 1.0 |
| Última actualización | 2026-07-26 |
| Autor | Sousan Wong |