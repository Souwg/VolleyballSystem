const SERVICE_WORKER_VERSION = "sportflow-v1";

self.addEventListener("install", () => {
  console.info(
    `[Service Worker] Instalando ${SERVICE_WORKER_VERSION}`,
  );

  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  console.info(
    `[Service Worker] Activando ${SERVICE_WORKER_VERSION}`,
  );

  event.waitUntil(self.clients.claim());
});

/*
 * Por ahora no se interceptan solicitudes.
 *
 * Esto evita almacenar en caché:
 * - respuestas privadas de la API;
 * - información de usuarios;
 * - pagos;
 * - datos administrativos;
 * - tokens de autenticación.
 *
 * Más adelante podremos añadir una estrategia offline
 * únicamente para recursos públicos y estáticos.
 */
