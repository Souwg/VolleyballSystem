import React, { useEffect, useContext, useState } from "react";
import { useParams } from "react-router-dom";
import { Context } from "../../store/appContext";

import { Container } from "../../component/ui/container";
import { PageHeader } from "../../component/ui/pageHeader";
import { Card } from "../../component/ui/card";

export const PlayerDetail = () => {
  const { actions } = useContext(Context);
  const { player_id } = useParams();

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
    return (
      <Container>
        <p>Cargando perfil...</p>
      </Container>
    );
  }

  return (
    <Container>
      <PageHeader
        title={`${player.first_name} ${player.last_name}`}
        subtitle={
          player.teams
            ?.map((t) => `#${t.player_number} ${t.name}`)
            .join(" • ") || "Sin categoría"
        }
      />

      {/* 🔥 PERFIL GENERAL */}
      <Card>
        <h3>Perfil general</h3>

        <p>
          <strong>Sexo:</strong>{" "}
          {player.sex === "female" ? "Femenino" : "Masculino"}
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

            <p>
              <strong>Estado:</strong>{" "}
              {team.status === "active"
                ? "Activa"
                : team.status === "injured"
                ? "Lesionada"
                : "Inactiva"}
            </p>
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
    </Container>
  );
};
