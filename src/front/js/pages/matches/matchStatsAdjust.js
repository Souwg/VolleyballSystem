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

    const result = await actions.getMatchRoster(match_id);

    if (result.ok) {
      const playablePlayers = result.data.filter(
        (player) =>
          player.is_called &&
          PLAYABLE_STATUSES.includes(player.attendance_status) &&
          player.did_play,
      );

      setPlayers(playablePlayers);
    }

    setLoading(false);
  };

  useEffect(() => {
    loadPlayers();
  }, [match_id]);

  if (loading) {
    return (
      <div className="page-container">
        <PageHeader
          title="Ajustar estadísticas"
          subtitle="Cargando jugadoras..."
        />
      </div>
    );
  }

  return (
    <div className="page-container">
      <PageHeader
        title="Ajustar estadísticas"
        subtitle="Selecciona una jugadora para corregir sus datos"
      />

      {players.length === 0 ? (
        <Card>
          <p className="mb-0">
            No hay jugadoras disponibles para ajustar estadísticas.
          </p>
        </Card>
      ) : (
        players.map((player) => (
          <Card key={player.match_player_id} className="mb-3">
            <h3>
              #{player.player_number} {player.first_name} {player.last_name}
            </h3>

            <p className="text-muted mb-3">
              Revisa o corrige las estadísticas manuales de esta jugadora.
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
    </div>
  );
};
