import React, { useContext, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Context } from "../../store/appContext";

import { PageHeader } from "../../component/ui/pageHeader";
import { Card } from "../../component/ui/card";
import "../../../styles/match.css";
import { Trophy } from "lucide-react";

export const Matches = () => {
  const { store, actions } = useContext(Context);
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadMatches();
  }, []);

  const loadMatches = async () => {
    setLoading(true);

    try {
      await actions.getClubMatches();
    } finally {
      setLoading(false);
    }
  };

  const getMatchStatusText = (match) => {
    if (match.is_completed) {
      if (match.result === "win") return "Victoria";
      if (match.result === "loss") return "Derrota";

      return "Finalizado";
    }

    const step = match.match_step ?? 0;

    if (step === 0) return "Por preparar";
    if (step === 1) return "Falta confirmar asistencia";
    if (step === 2) return "Listo para modo en vivo";
    if (step === 3) return "Modo en vivo iniciado";
    if (step >= 4) return "Con estadísticas";

    return "Por preparar";
  };

  const getMatchStatusClass = (match) => {
    if (match.is_completed) {
      if (match.result === "win") return "status-success";
      if (match.result === "loss") return "status-danger";

      return "status-muted";
    }

    const step = match.match_step ?? 0;

    if (step === 0) return "status-muted";
    if (step === 1) return "status-warning";
    if (step === 2) return "status-info";
    if (step === 3) return "status-info";
    if (step >= 4) return "status-success";

    return "status-muted";
  };

  const getMatchTypeLabel = (type) => {
    if (type === "official") return "Oficial";
    if (type === "friendly") return "Amistoso";
    if (type === "scrimmage") return "Partido interno";

    return "Partido";
  };

  if (loading) {
    return <p>Cargando partidos...</p>;
  }

  const matches = store.clubMatches || [];

  return (
    <>
      <PageHeader
        tone="matches"
        icon={Trophy}
        eyebrow="Calendario competitivo"
        title="Partidos del club"
        subtitle="Consulta todos los partidos registrados en los equipos del club."
      />

      {matches.length === 0 ? (
        <Card>
          <div className="empty-state">
            <Trophy size={30} />

            <h4>Aún no tienes partidos</h4>

            <p>
              Los partidos aparecerán aquí cuando los crees desde un equipo.
            </p>
          </div>
        </Card>
      ) : (
        <div className="match-list">
          {matches.map((match) => {
            const hasScore =
              match.is_completed ||
              (match.home_sets ?? 0) > 0 ||
              (match.opponent_sets ?? 0) > 0;

            const categoryName =
              match.category_name ||
              match.team?.category?.name ||
              "Sin categoría";

            const teamName = match.team_name || match.team?.name || "Equipo";

            return (
              <Card
                key={match.id}
                className="match-card card-interactive"
                onClick={() =>
                  navigate(`/matches/${match.id}`, {
                    state: {
                      from: "clubMatches",
                    },
                  })
                }
              >
                <div className="match-card-content">
                  <div className="match-card-main">
                    <h3>vs {match.opponent_name || "Partido interno"}</h3>

                    <p className="match-card-team">
                      {categoryName} · {teamName}
                    </p>

                    <p className="match-card-meta">
                      {match.date} · {getMatchTypeLabel(match.match_type)}
                    </p>

                    <span
                      className={`status-badge ${getMatchStatusClass(match)}`}
                    >
                      {getMatchStatusText(match)}
                    </span>
                  </div>

                  {hasScore && (
                    <span
                      className="match-score"
                      aria-label="Resultado en sets"
                    >
                      <span className="match-score-label">Sets</span>

                      <strong>
                        {match.home_sets ?? 0}
                        <span className="match-score-separator">–</span>
                        {match.opponent_sets ?? 0}
                      </strong>
                    </span>
                  )}
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </>
  );
};
