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

### Organización de estilos

`src/front/js/index.js` importa los estilos globales en este orden: `index.css`, `ui.css` y `layout.css`. Las páginas y componentes importan sus CSS de funcionalidad. Webpack inyecta esos CSS con `style-loader`, por lo que se debe comprobar la cascada antes de mover una regla entre archivos.

| Archivo | Responsabilidad |
|---------|-----------------|
| `src/front/styles/index.css` | Tokens, reset, tipografía y estilos base universales. |
| `src/front/styles/layout.css` | Shell, navegación, área principal, responsive estructural y safe areas. |
| `src/front/styles/ui.css` | Primitivas y componentes visuales compartidos: tarjetas, encabezados, formularios, botones, estados vacíos y avisos. |
| CSS de funcionalidad | Composición, variantes y estados propios de cada módulo. `paymentShared.css`, `trainingShared.css`, `clubShared.css` y `playerShared.css` comparten patrones dentro de sus módulos, no en toda la aplicación. |

Un estilo solo debe compartirse si representa el mismo concepto, comportamiento, estados y respuesta móvil. La semejanza visual o un valor repetido no bastan para convertirlo en global. Antes de borrar o mover un selector, busca todos sus usos, incluidas las clases construidas en JavaScript. Revisa las pantallas afectadas en móvil y escritorio cuando el entorno lo permita y ejecuta el build al cerrar un grupo de cambios.

En listas vacías, usa `Card` como contenedor y `.empty-state` para agrupar el título, la descripción y, si corresponde, la acción. Añade `.card-interactive` solo a tarjetas navegables.

Los estilos exclusivos de un componente, como `attendanceToggle.css`, se importan desde ese componente. Su composición dentro de una pantalla permanece en el CSS de la funcionalidad.

En pagos, el bloque de cobros abiertos, sus estados, contadores y acciones táctiles pertenecen a `paymentShared.css`. Los detalles de club y deportista permanecen en sus archivos de módulo.

La base visual compartida debe ser neutral respecto al deporte. Las variantes y componentes de un deporte pueden permanecer en su módulo cuando su flujo o estados sean propios.

Los tokens de `index.css` definen colores, tipografía, radios y la sombra compartida. Los tonos de `PageHeader` se configuran mediante variables del propio componente en `ui.css`; el tono por defecto ya está definido en `.page-header`. No conviertas medidas aisladas o puntos de corte propios de una pantalla en tokens globales.

Los colores de estado, incluidos `--color-success-soft` y `--color-success-dark`, pertenecen a `index.css`. `--auth-hero-image` se asigna en `AuthLayout` para cada página de acceso y no es un token global. Los CSS de funcionalidad pueden usar medidas y colores propios cuando representan una variante local.

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
