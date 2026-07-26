# Progressive Web App (PWA)

> **Nivel:** Desarrollo
>
> **Audiencia:** Desarrolladores

---

## 1. Objetivo

SportFlow implementa una Progressive Web App (PWA) para ofrecer una experiencia similar a una aplicación nativa sin necesidad de distribuir la aplicación mediante las tiendas oficiales (App Store o Google Play).

La PWA permite instalar SportFlow directamente desde el navegador, facilitando un acceso rápido desde dispositivos móviles y computadoras compatibles.

---

## 2. Descripción general

La PWA de SportFlow permite:

- Instalar la aplicación desde el navegador.
- Acceder mediante un icono en la pantalla principal.
- Ejecutarse en modo aplicación (sin barra del navegador).
- Mostrar iconos personalizados.
- Mejorar la experiencia de usuario en dispositivos móviles.

Actualmente la PWA está disponible para el dominio oficial:

```text
https://sportflow.club
```

---

## 3. Arquitectura

```
Usuario

      │

      ▼

Navegador

      │

      ▼

Manifest.webmanifest

      │

      ▼

Service Worker

      │

      ▼

SportFlow
```

El navegador utiliza el archivo `manifest.webmanifest` para obtener la configuración de instalación y registra el Service Worker para habilitar las funcionalidades propias de una PWA.

---

## 4. Componentes principales

La PWA utiliza los siguientes archivos:

| Archivo | Descripción |
|----------|-------------|
| `public/manifest.webmanifest` | Configuración principal de la PWA. |
| `public/service-worker.js` | Service Worker de la aplicación. |
| `public/icons/icon-192.png` | Icono principal de 192x192 px. |
| `public/icons/icon-512.png` | Icono principal de 512x512 px. |
| `public/icons/apple-touch-icon.png` | Icono utilizado por dispositivos Apple. |

---

## 5. Manifest

El archivo:

```text
public/manifest.webmanifest
```

define la información utilizada por el navegador para instalar SportFlow.

Actualmente incluye:

- Nombre de la aplicación.
- Nombre corto.
- Descripción.
- Idioma.
- URL de inicio.
- Scope.
- Modo de visualización.
- Orientación.
- Colores del tema.
- Iconos.

---

## 6. Service Worker

El archivo:

```text
public/service-worker.js
```

es registrado automáticamente por la aplicación.

Actualmente se utiliza para permitir que el navegador reconozca SportFlow como una Progressive Web App.

---

## 7. Instalación

### Google Chrome (Android y Escritorio)

1. Abrir:

```
https://sportflow.club
```

2. Abrir el menú del navegador.

3. Seleccionar:

```
Instalar aplicación
```

o

```
Agregar a pantalla principal
```

4. Confirmar la instalación.

---

### Safari (iPhone y iPad)

1. Abrir:

```
https://sportflow.club
```

2. Pulsar el botón **Compartir**.

3. Seleccionar:

```
Añadir a pantalla de inicio
```

4. Confirmar la instalación.

---

## 8. Requisitos

Para que la instalación sea posible se requiere:

- HTTPS activo.
- Dominio válido.
- Manifest válido.
- Service Worker registrado.
- Iconos configurados correctamente.

Todos estos requisitos se encuentran implementados en la versión actual de SportFlow.

---

## 9. Pruebas realizadas

Durante el despliegue en producción se verificó correctamente:

- Manifest cargado.
- Service Worker válido.
- Instalación en Google Chrome.
- Instalación en Safari para iPhone.
- Correcta visualización de los iconos.
- Apertura en modo aplicación.

Resultado:

La PWA quedó completamente funcional en producción.

---

## 10. Buenas prácticas

Se recomienda:

- Mantener actualizados los iconos.
- No modificar el nombre de la aplicación sin actualizar el manifest.
- Verificar el funcionamiento de la instalación después de cada despliegue.
- Mantener HTTPS habilitado permanentemente.

---

## 11. Troubleshooting

### No aparece la opción de instalar

Verificar:

- HTTPS activo.
- Manifest accesible.
- Service Worker registrado.

---

### Los iconos no aparecen

Comprobar:

- Archivos dentro de:

```text
public/icons
```

- Rutas definidas en el manifest.

---

### Safari no permite instalar

Verificar:

- Que el sitio se abra mediante HTTPS.
- Que el acceso se realice desde Safari.
- Que el usuario utilice la opción "Añadir a pantalla de inicio".

---

## 12. Checklist

Antes de finalizar un despliegue verificar:

- Manifest accesible.
- Service Worker registrado.
- Iconos cargados.
- Instalación desde Chrome.
- Instalación desde Safari.

---

## 13. Estado actual

| Componente | Estado |
|------------|--------|
| Manifest | ✅ |
| Service Worker | ✅ |
| HTTPS | ✅ |
| Chrome | ✅ |
| Safari | ✅ |
| Iconos | ✅ |

---

## 14. Archivos relacionados

| Recurso | Descripción |
|----------|-------------|
| `public/manifest.webmanifest` | Configuración de la PWA. |
| `public/service-worker.js` | Service Worker. |
| `public/icons/` | Iconos utilizados por la aplicación. |
| `docs/04-docker.md` | Despliegue de la aplicación. |
| `docs/05-cloudflare.md` | Configuración HTTPS y dominio. |

---

## 15. Información del documento

| Campo | Valor |
|--------|-------|
| Documento | 10-pwa.md |
| Proyecto | SportFlow |
| Versión | 1.0 |
| Última actualización | 2026-07-26 |
| Autor | Sousan Wong |