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

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      const trainingsData = await actions.getAllTrainings();
      const currentTraining = trainingsData?.trainings?.find(
        (t) => t.id === training_id,
      );

      if (!currentTraining) {
        setLoading(false);
        return;
      }

      await actions.getTeamPlayers(currentTraining.team_id);

      const attendanceData = await actions.getTrainingAttendance(training_id);

      if (attendanceData) {
        const map = {};

        attendanceData.forEach((a) => {
          map[a.player_id] = a.status;
        });

        setAttendance(map);
      }
      setLoading(false);
    };

    loadData();
  }, [training_id]);

  const saveAttendance = async () => {
    const attendanceList = store.players
      .filter((player) => attendance[player.id])
      .map((player) => ({
        player_id: player.id,
        status: attendance[player.id],
      }));

    const result = await actions.saveAttendance(training_id, attendanceList);

    if (!result?.ok) return;

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
                    onChange={(newStatus) => {
                      setAttendance((prev) => ({
                        ...prev,
                        [player.id]: newStatus,
                      }));
                      setHasChanges(true);
                    }}
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
          onClick={saveAttendance}
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
