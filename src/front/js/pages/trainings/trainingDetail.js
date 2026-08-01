import React, { useEffect, useContext, useState } from "react";
import { Context } from "../../store/appContext";
import { useParams, useNavigate } from "react-router-dom";

import { PageHeader } from "../../component/ui/pageHeader";
import { Card } from "../../component/ui/card";
import { Button } from "../../component/ui/button";
import { Input } from "../../component/ui/input";
import { FormField } from "../../component/ui/formField";
import { AttendanceToggle } from "../../component/ui/attendanceToggle";
import { errorMessages } from "../../utils/errorMessages";
import { validateTraining } from "../../utils/validators";
import { Pencil } from "lucide-react";
import "../../../styles/trainingDetail.css";

const formatTrainingDate = (date) => {
  if (!date) return "Sin definir";

  return new Date(`${date}T00:00:00`).toLocaleDateString("es-ES", {
    day: "2-digit",
    month: "long",
    year: "numeric",
  });
};

const formatTrainingTime = (time) => {
  if (!time) return "Sin definir";

  const [hours, minutes] = time.slice(0, 5).split(":");

  return new Date(
    2000,
    0,
    1,
    Number(hours),
    Number(minutes),
  ).toLocaleTimeString("es-ES", {
    hour: "numeric",
    minute: "2-digit",
  });
};

export const TrainingDetail = () => {
  const { store, actions } = useContext(Context);
  const { training_id } = useParams();
  const navigate = useNavigate();

  const [attendance, setAttendance] = useState({});
  const [loading, setLoading] = useState(true);
  const [hasChanges, setHasChanges] = useState(false);
  const [errors, setErrors] = useState({});
  const [saving, setSaving] = useState(false);
  const [training, setTraining] = useState(null);
  const [editingTraining, setEditingTraining] = useState(false);
  const [savingTraining, setSavingTraining] = useState(false);

  const [trainingForm, setTrainingForm] = useState({
    date: "",
    start_time: "",
    end_time: "",
    location: "",
  });

  const loadTrainingData = async () => {
    setLoading(true);
    setErrors({});

    const [detailResult, playersResult, attendanceResult] = await Promise.all([
      actions.getTrainingDetail(training_id),
      actions.getTrainingPlayers(training_id),
      actions.getTrainingAttendance(training_id),
    ]);

    const nextErrors = {};

    if (detailResult.ok) {
      const trainingData = detailResult.data.training;

      setTraining(trainingData);

      setTrainingForm({
        date: trainingData.date || "",
        start_time: trainingData.start_time?.slice(0, 5) || "",
        end_time: trainingData.end_time?.slice(0, 5) || "",
        location: trainingData.location || "",
      });
    } else {
      nextErrors[detailResult.code] = true;
    }

    if (!playersResult.ok) {
      nextErrors[playersResult.code] = true;
    }

    if (attendanceResult.ok) {
      const attendanceData = attendanceResult.data;
      const attendanceMap = {};

      attendanceData.forEach((attendanceItem) => {
        attendanceMap[attendanceItem.player_id] = attendanceItem.status;
      });

      setAttendance(attendanceMap);
    } else {
      nextErrors[attendanceResult.code] = true;
    }

    setErrors(nextErrors);
    setHasChanges(false);
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

    setErrors({});
    setHasChanges(true);
  };

  const handleTrainingFormChange = (field, value) => {
    setTrainingForm((prev) => ({
      ...prev,
      [field]: value,
    }));

    setErrors((prev) => ({
      ...prev,
      TRAINING_DATE_REQUIRED: false,
      TRAINING_START_TIME_REQUIRED: false,
      TRAINING_END_TIME_REQUIRED: false,
      TRAINING_LOCATION_REQUIRED: false,
      INVALID_TIME_FORMAT: false,
      INVALID_TRAINING_TIME_RANGE: false,
      TRAINING_NOT_FOUND: false,
      FORBIDDEN: false,
      CLUB_REQUIRED: false,
      SESSION_EXPIRED: false,
      NETWORK_ERROR: false,
    }));
  };

  const handleCancelTrainingEdit = () => {
    if (!training) return;

    setTrainingForm({
      date: training.date || "",
      start_time: training.start_time?.slice(0, 5) || "",
      end_time: training.end_time?.slice(0, 5) || "",
      location: training.location || "",
    });

    setErrors((prev) => ({
      ...prev,
      TRAINING_DATE_REQUIRED: false,
      TRAINING_START_TIME_REQUIRED: false,
      TRAINING_END_TIME_REQUIRED: false,
      TRAINING_LOCATION_REQUIRED: false,
      INVALID_TIME_FORMAT: false,
      INVALID_TRAINING_TIME_RANGE: false,
      NETWORK_ERROR: false,
    }));

    setEditingTraining(false);
  };

  const handleSaveTraining = async () => {
    if (savingTraining || !training) return;

    setErrors((prev) => ({
      ...prev,
      TRAINING_DATE_REQUIRED: false,
      TRAINING_START_TIME_REQUIRED: false,
      TRAINING_END_TIME_REQUIRED: false,
      TRAINING_LOCATION_REQUIRED: false,
      INVALID_TIME_FORMAT: false,
      INVALID_TRAINING_TIME_RANGE: false,
      TRAINING_NOT_FOUND: false,
      FORBIDDEN: false,
      CLUB_REQUIRED: false,
      SESSION_EXPIRED: false,
      NETWORK_ERROR: false,
    }));

    const newErrors = validateTraining({
      team_id: training.team_id,
      date: trainingForm.date,
      start_time: trainingForm.start_time,
      end_time: trainingForm.end_time,
      location: trainingForm.location,
    });

    if (Object.keys(newErrors).length > 0) {
      setErrors((prev) => ({
        ...prev,
        ...newErrors,
      }));

      return;
    }

    setSavingTraining(true);

    const result = await actions.updateTraining(training_id, {
      date: trainingForm.date.trim(),
      start_time: trainingForm.start_time.trim(),
      end_time: trainingForm.end_time.trim(),
      location: trainingForm.location.trim(),
    });

    setSavingTraining(false);

    if (!result.ok) {
      setErrors((prev) => ({
        ...prev,
        [result.code]: true,
      }));

      return;
    }

    const updatedTraining = result.data.training;

    setTraining(updatedTraining);

    setTrainingForm({
      date: updatedTraining.date || "",
      start_time: updatedTraining.start_time?.slice(0, 5) || "",
      end_time: updatedTraining.end_time?.slice(0, 5) || "",
      location: updatedTraining.location || "",
    });

    setEditingTraining(false);
  };

  const handleSaveAttendance = async () => {
    if (saving) return;

    setErrors({});
    setSaving(true);

    const attendanceList = store.players
      .filter((player) => attendance[player.id])
      .map((player) => ({
        player_id: player.id,
        status: attendance[player.id],
      }));

    const result = await actions.saveAttendance(training_id, attendanceList);

    setSaving(false);

    if (!result.ok) {
      setErrors({ [result.code]: true });
      return;
    }

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
    return <p>Cargando asistencia...</p>;
  }
  return (
    <div className="training-detail-page">
      <PageHeader
        variant="detail"
        eyebrow="Entrenamiento"
        title="Asistencia"
        subtitle="Marca la asistencia de los deportistas convocados a esta sesión."
        onBack={() => navigate("/trainings")}
      />

      <Card className="training-info-card">
        <div className="training-info-header">
          <div>
            <span className="training-info-eyebrow">
              {training?.category_name || "Entrenamiento"}
            </span>

            <h3>{training?.team_name || "Entrenamiento"}</h3>
          </div>

          {!editingTraining && training && (
            <button
              type="button"
              className="training-info-edit-button"
              onClick={() => {
                setErrors({});
                setEditingTraining(true);
              }}
              aria-label="Editar información del entrenamiento"
            >
              <Pencil size={17} />
            </button>
          )}
        </div>

        {editingTraining ? (
          <div className="training-info-form">
            <FormField
              label="Fecha"
              error={
                errors.TRAINING_DATE_REQUIRED
                  ? errorMessages.TRAINING_DATE_REQUIRED
                  : null
              }
            >
              <Input
                type="date"
                value={trainingForm.date}
                className={errors.TRAINING_DATE_REQUIRED ? "input-error" : ""}
                onChange={(event) =>
                  handleTrainingFormChange("date", event.target.value)
                }
              />
            </FormField>

            <div className="training-time-grid">
              <FormField
                label="Hora de inicio"
                error={
                  errors.TRAINING_START_TIME_REQUIRED
                    ? errorMessages.TRAINING_START_TIME_REQUIRED
                    : null
                }
              >
                <Input
                  type="time"
                  value={trainingForm.start_time}
                  className={
                    errors.TRAINING_START_TIME_REQUIRED ||
                    errors.INVALID_TRAINING_TIME_RANGE
                      ? "input-error"
                      : ""
                  }
                  onChange={(event) =>
                    handleTrainingFormChange("start_time", event.target.value)
                  }
                />
              </FormField>

              <FormField
                label="Hora de finalización"
                error={
                  errors.TRAINING_END_TIME_REQUIRED
                    ? errorMessages.TRAINING_END_TIME_REQUIRED
                    : errors.INVALID_TRAINING_TIME_RANGE
                    ? errorMessages.INVALID_TRAINING_TIME_RANGE
                    : null
                }
              >
                <Input
                  type="time"
                  value={trainingForm.end_time}
                  className={
                    errors.TRAINING_END_TIME_REQUIRED ||
                    errors.INVALID_TRAINING_TIME_RANGE
                      ? "input-error"
                      : ""
                  }
                  onChange={(event) =>
                    handleTrainingFormChange("end_time", event.target.value)
                  }
                />
              </FormField>
            </div>

            <FormField
              label="Ubicación"
              error={
                errors.TRAINING_LOCATION_REQUIRED
                  ? errorMessages.TRAINING_LOCATION_REQUIRED
                  : null
              }
            >
              <Input
                type="text"
                value={trainingForm.location}
                placeholder="Ej: Cancha central"
                className={
                  errors.TRAINING_LOCATION_REQUIRED ? "input-error" : ""
                }
                onChange={(event) =>
                  handleTrainingFormChange("location", event.target.value)
                }
              />
            </FormField>

            {(errors.INVALID_TIME_FORMAT ||
              errors.TRAINING_NOT_FOUND ||
              errors.FORBIDDEN ||
              errors.CLUB_REQUIRED ||
              errors.SESSION_EXPIRED ||
              errors.NETWORK_ERROR) && (
              <p className="form-error">
                {errors.INVALID_TIME_FORMAT
                  ? errorMessages.INVALID_TIME_FORMAT
                  : errors.TRAINING_NOT_FOUND
                  ? errorMessages.TRAINING_NOT_FOUND
                  : errors.FORBIDDEN
                  ? errorMessages.FORBIDDEN
                  : errors.CLUB_REQUIRED
                  ? errorMessages.CLUB_REQUIRED
                  : errors.SESSION_EXPIRED
                  ? errorMessages.SESSION_EXPIRED
                  : errorMessages.NETWORK_ERROR}
              </p>
            )}

            <div className="training-info-form-actions">
              <Button
                type="button"
                variant="secondary"
                onClick={handleCancelTrainingEdit}
                disabled={savingTraining}
              >
                Cancelar
              </Button>

              <Button
                type="button"
                onClick={handleSaveTraining}
                disabled={savingTraining}
              >
                {savingTraining ? "Guardando..." : "Guardar cambios"}
              </Button>
            </div>
          </div>
        ) : training ? (
          <div className="training-info-compact">
            <div className="training-info-meta">
              <span>{formatTrainingDate(training.date)}</span>

              <span className="training-info-separator" aria-hidden="true">
                •
              </span>

              <span>
                {formatTrainingTime(training.start_time)}
                {" – "}
                {formatTrainingTime(training.end_time)}
              </span>
            </div>

            <p className="training-info-location">
              {training.location || "Sin ubicación"}
            </p>
          </div>
        ) : (
          <p className="training-info-empty">
            No se pudo cargar la información del entrenamiento.
          </p>
        )}
      </Card>

      <Card>
        {store.players.length === 0 ? (
          <p>No hay deportistas en esta categoría.</p>
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
      {errors.ATTENDANCE_REQUIRED && (
        <p className="form-error">{errorMessages.ATTENDANCE_REQUIRED}</p>
      )}

      {errors.TRAINING_NOT_FOUND && (
        <p className="form-error">{errorMessages.TRAINING_NOT_FOUND}</p>
      )}

      {errors.FORBIDDEN && (
        <p className="form-error">{errorMessages.FORBIDDEN}</p>
      )}

      {errors.INVALID_ATTENDANCE_STATUS && (
        <p className="form-error">{errorMessages.INVALID_ATTENDANCE_STATUS}</p>
      )}
      <div className="attendance-sticky-bar">
        <div>
          <div className="attendance-progress">
            {markedCount} / {totalPlayers} deportistas marcados
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
          disabled={saving || !hasChanges || !allMarked}
        >
          {saving
            ? "Guardando..."
            : !allMarked
            ? `Faltan ${totalPlayers - markedCount}`
            : hasChanges
            ? "Guardar asistencia"
            : "Sin cambios"}
        </Button>
      </div>
    </div>
  );
};
