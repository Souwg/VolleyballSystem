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
  const [loading, setLoading] = useState(true);

  const loadPlayers = async () => {
    setLoading(true);

    try {
      const result = await actions.getMatchRoster(match_id);

      if (result.ok) {
        const roster = result.data || [];

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

  return (
    <>
      <PageHeader
        variant="detail"
        eyebrow="Estadísticas"
        title="Ajustar estadísticas"
        subtitle="Selecciona un deportista para corregir sus datos."
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
              Revisa o corrige las estadísticas manuales de este deportista.
            </p>

            <Button
              variant="secondary"
              onClick={() =>
                navigate(`/match-players/${player.match_player_id}/stats`)
              }
            >
              Ajustar stats
            </Button>
          </Card>
        ))
      )}
    </>
  );
};
