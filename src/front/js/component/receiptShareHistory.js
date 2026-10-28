import React from "react";


const formatEventDateTime = (value) => {
  if (!value) return "Fecha no disponible";

  return new Date(value).toLocaleString("es-ES", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
};

const getEventLabel = (event) => {
  if (event.event_type === "legacy_share_metadata") {
    return "Registro histórico de compartir";
  }

  return event.channel === "whatsapp"
    ? "WhatsApp abierto"
    : "Acción de compartir iniciada";
};

export const ReceiptShareHistory = ({ events, loading, error }) => (
  <section className="receipt-share-history" aria-label="Historial de compartidos">
    <h5>Historial de compartidos</h5>

    {loading && <p>Cargando historial...</p>}

    {!loading && error && <p className="form-error">{error}</p>}

    {!loading && !error && events.length === 0 && (
      <p>Todavía no hay acciones de compartir registradas.</p>
    )}

    {!loading && !error && events.length > 0 && (
      <ul>
        {events.map((event) => (
          <li key={event.id}>
            <strong>{getEventLabel(event)}</strong>
            <span>{formatEventDateTime(event.created_at)}</span>
            {event.destination && <small>{event.destination}</small>}
          </li>
        ))}
      </ul>
    )}
  </section>
);
