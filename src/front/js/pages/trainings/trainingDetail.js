import React, { useEffect, useContext, useState } from "react";
import { Context } from "../../store/appContext";
import { useParams } from "react-router-dom";

import { Container } from "../../component/ui/container";
import { PageHeader } from "../../component/ui/pageHeader";
import { Card } from "../../component/ui/card";
import { Button } from "../../component/ui/button";
import { AttendanceToggle } from "../../component/ui/attendanceToggle";
import "../../../styles/trainingDetail.css";

export const TrainingDetail = () => {
  const { store, actions } = useContext(Context);
  const { training_id } = useParams();

  const [attendance, setAttendance] = useState({});
  const [loading, setLoading] = useState(true);
  const [hasChanges, setHasChanges] = useState(false);

  const loadTrainingData = async () => {
    setLoading(true);

    await actions.getTrainingPlayers(training_id);

    const result = await actions.getTrainingAttendance(training_id);

    if (result.ok) {
      const attendanceData = result.data;

      const map = {};

      attendanceData.forEach((a) => {
        map[a.player_id] = a.status;
      });

      setAttendance(map);
    }

    setLoading(false);
  };

  useEffect(() => {
    loadTrainingData();
  }, [training_id]);

  const handleAttendanceChange = (playerId, newStatus) => {
    setAttendance((prev) => ({
      ...prev,
      [playerId]: newStatus,
    }));

    setHasChanges(true);
  };

  const handleSaveAttendance = async () => {
    const attendanceList = store.players
      .filter((player) => attendance[player.id])
      .map((player) => ({
        player_id: player.id,
        status: attendance[player.id],
      }));

    const result = await actions.saveAttendance(training_id, attendanceList);

    if (!result.ok) return;

    setHasChanges(false);
  };

  const presentCount = Object.values(attendance).filter(
    (s) => s === "present",
  ).length;

  const lateCount = Object.values(attendance).filter(
    (s) => s === "late",
  ).length;

  const absentCount = Object.values(attendance).filter(
    (s) => s === "absent",
  ).length;

  const markedCount = Object.keys(attendance).length;
  const totalPlayers = store.players.length;
  const allMarked = markedCount === totalPlayers;

  if (loading) {
    return (
      <Container>
        <p>Cargando asistencia...</p>
      </Container>
    );
  }
  return (
    <Container>
      <PageHeader title="Asistencia del entrenamiento" />

      <Card>
        {store.players.length === 0 ? (
          <p>No hay jugadores en este equipo.</p>
        ) : (
          <div className="attendance-list">
            {store.players.map((player) => {
              const status = attendance[player.id] || null;

              return (
                <div key={player.id} className="attendance-row">
                  <div className="attendance-player">
                    <span className="player-number">
                      #{player.player_number}
                    </span>

                    <span className="player-name">
                      {player.first_name} {player.last_name}
                    </span>
                  </div>

                  <AttendanceToggle
                    value={status}
                    onChange={(newStatus) =>
                      handleAttendanceChange(player.id, newStatus)
                    }
                  />
                </div>
              );
            })}
          </div>
        )}
      </Card>
      <div className="attendance-sticky-bar">
        <div>
          <div className="attendance-progress">
            {markedCount} / {totalPlayers} jugadoras marcadas
          </div>

          <div className="attendance-summary">
            <span>{presentCount} presentes</span>
            <span>{lateCount} tarde</span>
            <span>{absentCount} ausente</span>
          </div>
        </div>

        <Button
          className="button-primary"
          onClick={handleSaveAttendance}
          disabled={!hasChanges || !allMarked}
        >
          {!allMarked
            ? `Faltan ${totalPlayers - markedCount}`
            : hasChanges
            ? "Guardar asistencia"
            : "Sin cambios"}
        </Button>
      </div>
    </Container>
  );
};
