import React, { useEffect, useRef, useState, useContext } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import { Context } from "../../store/appContext";
import { PageHeader } from "../../component/ui/pageHeader";
import { Card } from "../../component/ui/card";
import { Button } from "../../component/ui/button";
import { canManage, resolveTeamOperational } from "../../utils/coachAccess";

const PLAYABLE_STATUSES = ["present", "late"];

export const MatchStatsAdjust = () => {
  const { actions } = useContext(Context);
  const { match_id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const detailPath = `/matches/${match_id}${location.search}`;

  const [players, setPlayers] = useState([]);
  const [captureMode, setCaptureMode] = useState(null);
  const [isCompleted, setIsCompleted] = useState(false);
  const [canOperate, setCanOperate] = useState(true);
  const [loading, setLoading] = useState(true);
  const [preflight, setPreflight] = useState(null);
  const loadRequestId = useRef(0);

  const loadPlayers = async () => {
    const requestId = ++loadRequestId.current;
    setLoading(true);

    try {
      setPlayers([]);
      setPreflight(null);
      const [matchResult, rosterResult, preflightResult] = await Promise.all([
        actions.getMatchDetail(match_id),
        actions.getMatchRoster(match_id),
        actions.getMatchPreflight(match_id),
      ]);

      if (requestId !== loadRequestId.current) return;

      if (matchResult.ok) {
        const matchData = matchResult.data.match;

        setCaptureMode(matchData?.capture_mode || null);
        setIsCompleted(Boolean(matchData?.is_completed));
        setCanOperate(
          canManage(matchData) &&
            (await resolveTeamOperational(actions, matchData?.team_id)),
        );
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

      if (preflightResult.ok) setPreflight(preflightResult.data.preflight);
    } finally {
      if (requestId === loadRequestId.current) setLoading(false);
    }
  };

  useEffect(() => {
    loadPlayers();
    return () => { loadRequestId.current += 1; };
  }, [match_id]);

  if (loading) {
    return (
      <>
        <PageHeader
          variant="detail"
          eyebrow="Partido"
          title="Ajustar estadísticas"
          subtitle="Cargando deportistas..."
          onBack={() => navigate(detailPath)}
        />
      </>
    );
  }

  const canEditStats =
    captureMode === "summary" && !isCompleted && canOperate;

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
        onBack={() => navigate(detailPath)}
      />
      {players.length === 0 ? (
        <Card>
          <p className="mb-0">
            No hay deportistas disponibles para ajustar estadísticas.
          </p>
        </Card>
      ) : (
        <>
        <Card className="mb-3" aria-live="polite">
          <strong>Progreso del resumen</strong>
          <p className="mb-0">{preflight?.stats?.counts?.reviewed || 0} de {preflight?.stats?.counts?.required || players.length} deportistas revisadas</p>
        </Card>
        {players.map((player) => (
          <Card key={player.match_player_id} className="mb-3">
            <h3>
              #{player.player_number} {player.first_name} {player.last_name}
            </h3>

            <p className="text-muted mb-3">
              {canEditStats
                ? "Carga o actualiza el resumen estadístico de esta deportista."
                : "Consulta las estadísticas registradas de esta deportista."}
            </p>

            <span className={`status-badge ${player.stats_reviewed ? "status-success" : "status-warning"}`}>
              {player.stats_reviewed ? "Revisada" : "Pendiente"}
            </span>

            <Button
              variant="secondary"
              onClick={() =>
                navigate(`/match-players/${player.match_player_id}/stats${location.search}`)
              }
            >
              {canEditStats ? "Cargar resumen" : "Ver estadísticas"}
            </Button>
          </Card>
        ))}
        </>
      )}
    </>
  );
};
