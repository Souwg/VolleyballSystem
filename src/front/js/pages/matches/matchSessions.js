import React, { useEffect, useState, useContext } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Context } from "../../store/appContext";
import { PageHeader } from "../../component/ui/pageHeader";
import { Card } from "../../component/ui/card";
import { Button } from "../../component/ui/button";
import "../../../styles/match.css";

export const MatchSessions = () => {
  const { store, actions } = useContext(Context);
  const { team_id } = useParams();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadMatches();
  }, [team_id]);

  const loadMatches = async () => {
    setLoading(true);

    const result = await actions.getTeamMatches(team_id);

    if (!result.ok) {
      setLoading(false);
      return;
    }

    setLoading(false);
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

  if (loading) {
    return <p>Cargando partidos...</p>;
  }

  return (
    <div className="page-container">
      <PageHeader
        variant="detail"
        eyebrow="Categoría"
        title="Partidos"
        subtitle="Gestiona partidos, preparación y rendimiento."
        onBack={() => navigate(`/teams/${team_id}`)}
        actions={
          <Button onClick={() => navigate(`/teams/${team_id}/matches/new`)}>
            + Crear partido
          </Button>
        }
      />

      {store.matches.length === 0 ? (
        <Card>
          <p>No hay partidos creados todavía</p>
        </Card>
      ) : (
        store.matches.map((match) => {
          const hasScore =
            match.is_completed ||
            (match.home_sets ?? 0) > 0 ||
            (match.opponent_sets ?? 0) > 0;

          return (
            <Card
              key={match.id}
              className="match-card card-interactive"
              onClick={() => navigate(`/matches/${match.id}`)}
            >
              <div className="match-card-header">
                <div className="match-card-main">
                  <h3>vs {match.opponent_name || "Scrimmage interno"}</h3>

                  <p className="match-card-meta">
                    {match.date} ·{" "}
                    {match.match_type === "official"
                      ? "Oficial"
                      : match.match_type === "friendly"
                      ? "Amistoso"
                      : "Scrimmage"}
                  </p>
                </div>

                <div className="match-card-side">
                  <span
                    className={`status-badge ${getMatchStatusClass(match)}`}
                  >
                    {getMatchStatusText(match)}
                  </span>

                  {hasScore && (
                    <span className="match-score">
                      {match.home_sets ?? 0} - {match.opponent_sets ?? 0}
                    </span>
                  )}
                </div>
              </div>
            </Card>
          );
        })
      )}
    </div>
  );
};
