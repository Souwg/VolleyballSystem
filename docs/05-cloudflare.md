# Cloudflare

> **Nivel:** Infraestructura
>
> **Audiencia:** Desarrolladores / Administradores del servidor

---

## 1. Objetivo

Cloudflare es el servicio encargado de gestionar el dominio principal de SportFlow, proporcionar HTTPS, administrar los registros DNS y proteger la aplicación frente a tráfico malicioso.

Toda solicitud realizada a:

```
https://sportflow.club
```

pasa primero por Cloudflare antes de llegar al servidor de producción.

---

## 2. Descripción general

Actualmente Cloudflare proporciona:

- Gestión del dominio.
- Resolución DNS.
- Certificados HTTPS.
- Proxy inverso.
- Protección básica contra ataques.
- Capa adicional de seguridad.
- Integración con Resend mediante registros DNS.

Cloudflare no almacena información de la aplicación ni de la base de datos.

---

## 3. Arquitectura

```
Usuario
      │
      ▼
Internet
      │
      ▼
Cloudflare
      │
      ▼
Servidor VPS
      │
      ▼
Docker
      │
      ├─────────────┐
      ▼             ▼
Flask          PostgreSQL
```

Cloudflare actúa como intermediario entre los usuarios y el servidor.

---

## 4. Dominio

Dominio principal:

```
sportflow.club
```

Subdominio principal:

```
www.sportflow.club
```

Todo el tráfico HTTPS se dirige hacia el VPS de producción.

---

## 5. Configuración DNS

Cloudflare almacena todos los registros DNS utilizados por SportFlow.

Actualmente existen registros para:

- Dominio principal.
- Subdominio www.
- Resend.
- DKIM.
- SPF.
- DMARC.

Toda modificación DNS debe realizarse únicamente desde Cloudflare.

---

## 6. Registros utilizados

### Registro A

Se utiliza para dirigir el dominio principal hacia la dirección IP pública del VPS.

Ejemplo:

```
sportflow.club
↓
IP pública del servidor
```

---

### Registro CNAME

Se utiliza para el subdominio:

```
www
```

---

### Registros TXT

Actualmente se utilizan para:

- Verificación de Resend.
- DKIM.
- SPF.
- DMARC.

---

### Registro MX

Utilizado por Resend para la verificación del dominio de envío.

---

## 7. Proxy de Cloudflare

No todos los registros utilizan el proxy.

### Proxy habilitado

Debe permanecer habilitado para:

- sportflow.club
- www

Estado:

```
Proxied
```

---

### Proxy deshabilitado

Debe permanecer deshabilitado para:

- DKIM
- SPF
- MX
- DMARC

Estado:

```
DNS only
```

Esto es necesario para que Resend pueda validar correctamente el dominio.

---

## 8. HTTPS

Cloudflare proporciona el acceso seguro mediante HTTPS.

El dominio oficial de producción es:

```
https://sportflow.club
```

Todo el tráfico HTTP debe redirigirse automáticamente a HTTPS.

---

## 9. SSL/TLS

La configuración SSL debe mantenerse siempre activa.

Cloudflare cifra la comunicación entre:

Usuario

↓

Cloudflare

↓

Servidor

Nunca debe deshabilitarse HTTPS en producción.

---

## 10. Integración con Resend

Cloudflare es el proveedor DNS utilizado para verificar el dominio de envío de Resend.

Durante la configuración se añadieron los siguientes registros:

- DKIM
- SPF
- MX
- DMARC

Una vez verificado el dominio no es necesario volver a crear estos registros salvo migración o cambio de dominio.

---

## 11. Buenas prácticas

Se recomienda:

- No eliminar registros DNS sin verificar su función.
- Mantener activado HTTPS.
- Mantener el proxy únicamente donde corresponda.
- Evitar registros DNS duplicados.
- Documentar cualquier modificación realizada en Cloudflare.

---

## 12. Troubleshooting

### El dominio no responde

Verificar:

- Registro A.
- Estado del VPS.
- Estado de Cloudflare.

---

### HTTPS no funciona

Comprobar:

- Certificado SSL.
- Configuración SSL/TLS.
- Estado del proxy.

---

### Resend no verifica el dominio

Comprobar:

- DKIM.
- SPF.
- MX.
- DMARC.

Todos deben permanecer en:

```
DNS only
```

Esperar la propagación DNS si los registros fueron creados recientemente.

---

## 13. Checklist

Antes de finalizar una configuración verificar:

- Dominio activo.
- HTTPS funcionando.
- Registro A correcto.
- Registro CNAME correcto.
- DKIM configurado.
- SPF configurado.
- DMARC configurado.
- MX configurado.
- Proxy correctamente aplicado.
- Resend verificado.

---

## 14. Estado actual

| Componente | Estado |
|------------|--------|
| Dominio | ✅ |
| HTTPS | ✅ |
| Cloudflare | ✅ |
| Registro A | ✅ |
| Registro CNAME | ✅ |
| DKIM | ✅ |
| SPF | ✅ |
| DMARC | ✅ |
| Resend | ✅ |

---

## 15. Archivos relacionados

| Recurso | Descripción |
|----------|-------------|
| Cloudflare Dashboard | Administración del dominio y DNS. |
| `docs/03-resend.md` | Configuración del servicio de correo. |
| `/opt/sportflow/docker/.env` | Variables relacionadas con el correo. |

---

## 16. Información del documento

| Campo | Valor |
|--------|-------|
| Documento | 05-cloudflare.md |
| Proyecto | SportFlow |
| Versión | 1.0 |
| Última actualización | 2026-07-26 |
| Autor | Sousan Wong |