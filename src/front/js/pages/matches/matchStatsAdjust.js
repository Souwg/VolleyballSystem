import React, { useEffect, useState, useContext } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Context } from "../../store/appContext";
import { PageHeader } from "../../component/ui/pageHeader";
import { Card } from "../../component/ui/card";
import { Button } from "../../component/ui/button";

const PLAYABLE_STATUSES = ["present", "late"];

export const MatchStatsAdjust = () => {
  const { actions } = useContext(Context);
  const { match_id } = useParams();
  const navigate = useNavigate();

  const [players, setPlayers] = useState([]);
  const [captureMode, setCaptureMode] = useState(null);
  const [isCompleted, setIsCompleted] = useState(false);
  const [loading, setLoading] = useState(true);

  const loadPlayers = async () => {
    setLoading(true);

    try {
      const [matchResult, rosterResult] = await Promise.all([
        actions.getMatchDetail(match_id),
        actions.getMatchRoster(match_id),
      ]);

      if (matchResult.ok) {
        setCaptureMode(matchResult.data.match?.capture_mode || null);
        setIsCompleted(Boolean(matchResult.data.match?.is_completed));
      }

      if (rosterResult.ok) {
        const roster = rosterResult.data || [];

        const playablePlayers = roster.filter(
          (player) =>
            player.is_called &&
            PLAYABLE_STATUSES.includes(player.attendance_status) &&
            player.did_play,
        );

        setPlayers(playablePlayers);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPlayers();
  }, [match_id]);

  if (loading) {
    return (
      <>
        <PageHeader
          variant="detail"
          eyebrow="Partido"
          title="Ajustar estadísticas"
          subtitle="Cargando deportistas..."
          onBack={() => navigate(`/matches/${match_id}`)}
        />
      </>
    );
  }

  const canEditStats = captureMode === "summary" && !isCompleted;

  return (
    <>
      <PageHeader
        variant="detail"
        eyebrow="Estadísticas"
        title={canEditStats ? "Cargar resumen estadístico" : "Consultar estadísticas"}
        subtitle={
          canEditStats
            ? "Selecciona una deportista para cargar su resumen."
            : isCompleted
            ? "El partido está completado y sus estadísticas son de solo lectura."
            : "Las estadísticas de este partido están disponibles en modo de solo lectura."
        }
        onBack={() => navigate(`/matches/${match_id}`)}
      />
      {players.length === 0 ? (
        <Card>
          <p className="mb-0">
            No hay deportistas disponibles para ajustar estadísticas.
          </p>
        </Card>
      ) : (
        players.map((player) => (
          <Card key={player.match_player_id} className="mb-3">
            <h3>
              #{player.player_number} {player.first_name} {player.last_name}
            </h3>

            <p className="text-muted mb-3">
              {canEditStats
                ? "Carga o actualiza el resumen estadístico de esta deportista."
                : "Consulta las estadísticas registradas de esta deportista."}
            </p>

            <Button
              variant="secondary"
              onClick={() =>
                navigate(`/match-players/${player.match_player_id}/stats`)
              }
            >
              {canEditStats ? "Cargar resumen" : "Ver estadísticas"}
            </Button>
          </Card>
        ))
      )}
    </>
  );
};
