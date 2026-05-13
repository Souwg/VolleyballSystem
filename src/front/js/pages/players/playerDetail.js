import React, { useEffect, useContext, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Context } from "../../store/appContext";
import "../../../styles/playerDetails.css";
import { PageHeader } from "../../component/ui/pageHeader";
import { Card } from "../../component/ui/card";
import { Button } from "../../component/ui/button";

const POSITION_LABELS = {
  setter: "Armadora",
  outside: "Punta",
  middle: "Central",
  opposite: "Opuesto",
  libero: "Líbero",
};

export const PlayerDetail = () => {
  const { actions } = useContext(Context);
  const { player_id } = useParams();
  const navigate = useNavigate();

  const [player, setPlayer] = useState(null);
  const [summary, setSummary] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);

  const loadPlayerData = async () => {
    setLoading(true);

    const result = await actions.getPlayerAttendance(player_id);

    if (result.ok) {
      const data = result.data;
      setPlayer(data.player);
      setSummary(data.summary);
      setHistory(data.history);
    }

    setLoading(false);
  };

  useEffect(() => {
    loadPlayerData();
  }, [player_id]);

  if (loading) {
    return <p>Cargando perfil...</p>;
  }

  if (!player) {
    return <p>No se pudo cargar el deportista.</p>;
  }

  return (
    <div className="player-detail-page">
      <PageHeader
        variant="detail"
        eyebrow="Perfil de deportista"
        title={`${player.first_name} ${player.last_name}`}
        subtitle={
          player.teams?.length > 0
            ? player.teams
                .map((t) => `#${t.player_number} · ${t.name}`)
                .join(" • ")
            : "Sin categoría asignada"
        }
        onBack={() => navigate("/players")}
        actions={
          <Button
            variant="secondary"
            onClick={() => navigate(`/players/${player_id}/edit`)}
          >
            Editar perfil
          </Button>
        }
      />

      {/* 🔥 PERFIL GENERAL */}
      <Card>
        <h3>Perfil general</h3>

        <p>
          <strong>Sexo:</strong>{" "}
          {player.sex === "female" ? "Femenino" : "Masculino"}
        </p>

        <p>
          <strong>Fecha de nacimiento:</strong>{" "}
          {player.birth_date || "Sin definir"}
        </p>

        <p>
          <strong>Posición principal:</strong>{" "}
          {POSITION_LABELS[player.main_position] || "Sin definir"}
        </p>
      </Card>

      {/* 🏐 MEMBERSHIP CARDS */}
      {player.teams?.length > 0 ? (
        player.teams.map((team) => (
          <Card key={team.id}>
            <h3>{team.name}</h3>

            <p>
              <strong>Número:</strong> #{team.player_number}
            </p>

            <div>
              <strong>Estado:</strong>{" "}
              <span
                className={`status-badge ${
                  team.status === "active"
                    ? "status-success"
                    : team.status === "injured"
                    ? "status-warning"
                    : "status-muted"
                }`}
              >
                {team.status === "active"
                  ? "Activo"
                  : team.status === "injured"
                  ? "Lesionado"
                  : "Inactivo"}
              </span>
            </div>
          </Card>
        ))
      ) : (
        <Card>
          <p>Sin categorías asignadas</p>
        </Card>
      )}

      {/* 📊 RESUMEN DE ASISTENCIA */}
      <Card>
        <h3>Resumen de asistencia</h3>

        {summary && (
          <div>
            <p>Presentes: {summary.present}</p>
            <p>Tardes: {summary.late}</p>
            <p>Ausencias: {summary.absent}</p>
            <p>Asistencia: {summary.attendance_rate}%</p>
          </div>
        )}
      </Card>

      {/* 🕓 HISTORIAL */}
      <Card>
        <h3>Historial</h3>

        {history.length === 0 ? (
          <p>No hay historial todavía</p>
        ) : (
          history.map((h) => (
            <div key={h.training_id}>
              {h.date} — {h.status}
            </div>
          ))
        )}
      </Card>
    </div>
  );
};
