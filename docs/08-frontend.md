# Frontend

> **Nivel:** Desarrollo
>
> **Audiencia:** Desarrolladores

---

## 1. Objetivo

El frontend de SportFlow es la interfaz utilizada por los usuarios para interactuar con la plataforma.

Su objetivo es ofrecer una experiencia moderna, intuitiva y responsive, permitiendo administrar toda la información del sistema desde cualquier dispositivo.

El frontend consume la API REST del backend y representa la información de forma visual.

---

## 2. Descripción general

SportFlow utiliza React como biblioteca principal para la construcción de la interfaz de usuario.

La aplicación funciona como una Single Page Application (SPA), permitiendo una navegación fluida sin recargar completamente la página.

Todo el estado de la interfaz se obtiene mediante llamadas a la API del backend.

---

## 3. Arquitectura

```
Usuario

      │

      ▼

React

      │

Componentes

      │

API REST

      │

Flask

      │

PostgreSQL
```

Toda la lógica de negocio permanece en el backend, mientras que el frontend se encarga de la presentación y la interacción con el usuario.

---

## 4. Tecnologías utilizadas

Actualmente el frontend utiliza:

- React
- JavaScript
- HTML5
- CSS3
- Webpack

---

## 5. Organización del proyecto

La estructura principal del frontend se encuentra dentro del proyecto:

```text
src/front/
```

La aplicación está organizada mediante componentes reutilizables y páginas específicas para cada módulo.

---

## 6. Componentes

El frontend está compuesto por componentes reutilizables que permiten mantener una interfaz consistente en toda la aplicación.

Ejemplos de componentes utilizados:

- Sidebar
- Topbar
- PageHeader
- Cards
- Formularios
- Tablas
- Modales
- Botones

Cada componente tiene una única responsabilidad y puede reutilizarse en diferentes secciones del sistema.

---

## 7. Navegación

La navegación entre las diferentes pantallas se realiza mediante rutas internas.

Entre los principales módulos se encuentran:

- Dashboard
- Club
- Categorías
- Equipos
- Jugadores
- Entrenamientos
- Partidos
- Pagos
- Administración

---

## 8. Diseño Responsive

SportFlow fue diseñado siguiendo una filosofía Mobile First.

La interfaz se adapta automáticamente a:

- Teléfonos móviles.
- Tablets.
- Computadoras de escritorio.

La experiencia de usuario debe mantenerse consistente independientemente del tamaño de la pantalla.

---

## 9. PWA

SportFlow puede instalarse como una Progressive Web App (PWA).

Esto permite:

- Instalar la aplicación desde el navegador.
- Acceder rápidamente desde la pantalla principal.
- Utilizar iconos personalizados.
- Mejorar la experiencia en dispositivos móviles.

La configuración de la PWA se encuentra documentada en un documento independiente.

---

## 10. Comunicación con el backend

Toda la información mostrada por el frontend proviene de la API REST.

Las solicitudes se realizan mediante HTTP y las respuestas se reciben en formato JSON.

Las rutas protegidas requieren autenticación mediante JWT.

---

## 11. Buenas prácticas

Se recomienda:

- Crear componentes reutilizables.
- Mantener separados presentación y lógica.
- Evitar duplicar componentes.
- Mantener consistencia visual.
- Utilizar nombres descriptivos para componentes y archivos.
- Probar el comportamiento responsive antes de desplegar cambios.

---

## 12. Troubleshooting

### La aplicación no carga

Verificar:

- Estado del backend.
- Consola del navegador.
- Errores JavaScript.

---

### Error al consumir la API

Comprobar:

- URL de la API.
- Estado del backend.
- Token JWT.

---

### Problemas de estilos

Verificar:

- Archivos CSS.
- Compilación mediante Webpack.
- Caché del navegador.

---

## 13. Checklist

Antes de desplegar cambios en el frontend verificar:

- Componentes funcionando correctamente.
- Diseño responsive probado.
- Navegación correcta.
- Consumo correcto de la API.
- Sin errores en la consola del navegador.

---

## 14. Estado actual

| Componente | Estado |
|------------|--------|
| React | ✅ |
| Webpack | ✅ |
| Responsive | ✅ |
| PWA | ✅ |
| API REST | ✅ |

---

## 15. Archivos relacionados

| Recurso | Descripción |
|----------|-------------|
| `src/front/` | Código fuente del frontend. |
| `public/` | Archivos públicos de la aplicación. |
| `webpack.common.js` | Configuración base de Webpack. |
| `webpack.dev.js` | Configuración para desarrollo. |
| `webpack.prod.js` | Configuración para producción. |

---

## 16. Información del documento

| Campo | Valor |
|--------|-------|
| Documento | 08-frontend.md |
| Proyecto | SportFlow |
| Versión | 1.0 |
| Última actualización | 2026-07-26 |
| Autor | Sousan Wong |