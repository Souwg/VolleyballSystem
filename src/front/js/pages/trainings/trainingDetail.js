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
import { getTrainingStatus } from "../../utils/trainingStatus";
import { Pencil } from "lucide-react";
import "../../../styles/trainingShared.css";
import "../../../styles/trainingDetail.css";

const METADATA_LABELS = {
  date: "Fecha",
  start_time: "Hora de inicio",
  end_time: "Hora de finalización",
  location: "Ubicación",
  status: "Estado",
};

const ATTENDANCE_LABELS = {
  present: "Presente",
  late: "Tarde",
  absent: "Ausente",
};

const AUDIT_ACTION_LABELS = {
  training_metadata_corrected: "Corrigió la información",
  training_attendance_corrected: "Corrigió la asistencia",
  training_reactivated: "Reactivó el entrenamiento",
};

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

const formatAuditDate = (value) => {
  if (!value) return "Fecha no disponible";

  return new Date(value).toLocaleString("es-ES", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
};

const formatAuditValue = (field, value) => {
  if (value === null || value === undefined || value === "") {
    return "Sin registro";
  }

  if (field === "date") return formatTrainingDate(value);
  if (["start_time", "end_time"].includes(field)) {
    return formatTrainingTime(value);
  }
  if (field === "status") return getTrainingStatus(value).label;

  return value;
};

const mapAttendanceRows = (rows) => {
  const mapped = {};

  rows.forEach((row) => {
    mapped[row.player_id] = row.status;
  });

  return mapped;
};

export const TrainingDetail = () => {
  const { store, actions } = useContext(Context);
  const { training_id } = useParams();
  const navigate = useNavigate();

  const [attendance, setAttendance] = useState({});
  const [originalAttendance, setOriginalAttendance] = useState({});
  const [loading, setLoading] = useState(true);
  const [hasChanges, setHasChanges] = useState(false);
  const [errors, setErrors] = useState({});
  const [saving, setSaving] = useState(false);
  const [training, setTraining] = useState(null);
  const [editMode, setEditMode] = useState(null);
  const [metadataReason, setMetadataReason] = useState("");
  const [attendanceCorrection, setAttendanceCorrection] = useState(false);
  const [attendanceReason, setAttendanceReason] = useState("");
  const [reactivationOpen, setReactivationOpen] = useState(false);
  const [reactivationReason, setReactivationReason] = useState("");
  const [savingTraining, setSavingTraining] = useState(false);
  const [transitioningStatus, setTransitioningStatus] = useState(null);
  const [syncingRoster, setSyncingRoster] = useState(false);
  const [auditOpen, setAuditOpen] = useState(false);
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditEvents, setAuditEvents] = useState([]);

  const [trainingForm, setTrainingForm] = useState({
    date: "",
    start_time: "",
    end_time: "",
    location: "",
  });

  const resetTrainingForm = (trainingData) => {
    setTrainingForm({
      date: trainingData?.date || "",
      start_time: trainingData?.start_time?.slice(0, 5) || "",
      end_time: trainingData?.end_time?.slice(0, 5) || "",
      location: trainingData?.location || "",
    });
  };

  const loadAuditEvents = async () => {
    setAuditLoading(true);
    const result = await actions.getTrainingAudit(training_id);
    setAuditLoading(false);

    if (!result.ok) {
      setErrors({ [result.code]: true });
      return;
    }

    setAuditEvents(result.data || []);
  };

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
      resetTrainingForm(trainingData);
    } else {
      nextErrors[detailResult.code] = true;
    }

    if (!playersResult.ok) nextErrors[playersResult.code] = true;

    if (attendanceResult.ok) {
      const attendanceMap = mapAttendanceRows(attendanceResult.data);
      setAttendance(attendanceMap);
      setOriginalAttendance(attendanceMap);
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
    setAttendance((previous) => {
      const next = { ...previous, [playerId]: newStatus };
      const changed = store.players.some(
        (player) =>
          (next[player.id] || null) !==
          (originalAttendance[player.id] || null),
      );

      setHasChanges(changed);
      return next;
    });
    setErrors({});
  };

  const handleTrainingFormChange = (field, value) => {
    setTrainingForm((previous) => ({ ...previous, [field]: value }));
    setErrors({});
  };

  const openTrainingEditor = (mode) => {
    resetTrainingForm(training);
    setMetadataReason("");
    setErrors({});
    setEditMode(mode);
  };

  const handleCancelTrainingEdit = () => {
    resetTrainingForm(training);
    setMetadataReason("");
    setErrors({});
    setEditMode(null);
  };

  const handleSaveTraining = async () => {
    if (savingTraining || !training) return;

    setErrors({});
    const newErrors = validateTraining({
      team_id: training.team_id,
      date: trainingForm.date,
      start_time: trainingForm.start_time,
      end_time: trainingForm.end_time,
      location: trainingForm.location,
    });

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    if (editMode === "correction" && !metadataReason.trim()) {
      setErrors({ CORRECTION_REASON_REQUIRED: true });
      return;
    }

    const changes = {
      date: trainingForm.date.trim(),
      start_time: trainingForm.start_time.trim(),
      end_time: trainingForm.end_time.trim(),
      location: trainingForm.location.trim(),
    };

    setSavingTraining(true);
    const result = editMode === "correction"
      ? await actions.correctTrainingMetadata(
          training_id,
          metadataReason.trim(),
          changes,
        )
      : await actions.updateTraining(training_id, changes);
    setSavingTraining(false);

    if (!result.ok) {
      setErrors({ [result.code]: true });
      return;
    }

    const updatedTraining = result.data.training;
    setTraining(updatedTraining);
    resetTrainingForm(updatedTraining);
    setMetadataReason("");
    setEditMode(null);

    if (auditOpen || editMode === "correction") await loadAuditEvents();
  };

  const handleSaveAttendance = async () => {
    if (saving || !training) return;

    setErrors({});

    if (attendanceCorrection && !attendanceReason.trim()) {
      setErrors({ CORRECTION_REASON_REQUIRED: true });
      return;
    }

    const attendanceList = store.players
      .filter((player) => {
        if (!attendance[player.id]) return false;

        return !attendanceCorrection || (
          attendance[player.id] !== originalAttendance[player.id]
        );
      })
      .map((player) => ({
        player_id: player.id,
        status: attendance[player.id],
      }));

    setSaving(true);
    const result = attendanceCorrection
      ? await actions.correctTrainingAttendance(
          training_id,
          attendanceReason.trim(),
          attendanceList,
        )
      : await actions.saveAttendance(training_id, attendanceList);
    setSaving(false);

    if (!result.ok) {
      setErrors({ [result.code]: true });
      return;
    }

    const nextAttendance = result.data.attendance
      ? mapAttendanceRows(result.data.attendance)
      : { ...attendance };

    setAttendance(nextAttendance);
    setOriginalAttendance(nextAttendance);
    setHasChanges(false);
    setAttendanceCorrection(false);
    setAttendanceReason("");

    if (auditOpen) await loadAuditEvents();
  };

  const cancelAttendanceCorrection = () => {
    setAttendance({ ...originalAttendance });
    setAttendanceReason("");
    setHasChanges(false);
    setErrors({});
    setAttendanceCorrection(false);
  };

  const handleTrainingTransition = async (targetStatus) => {
    if (transitioningStatus || syncingRoster || !training) return;

    const isCompleting = targetStatus === "completed";
    const confirmed = window.confirm(
      isCompleting
        ? "¿Marcar este entrenamiento como completado?\n\nEl entrenamiento quedará registrado como realizado."
        : "¿Cancelar este entrenamiento?\n\nSe conservarán los datos registrados.",
    );

    if (!confirmed) return;

    setErrors({});
    setTransitioningStatus(targetStatus);

    try {
      const result = isCompleting
        ? await actions.completeTraining(training_id)
        : await actions.cancelTraining(training_id);

      if (!result.ok) {
        setErrors({ [result.code]: true });
        return;
      }

      setTraining(result.data.training);
      setAttendance({ ...originalAttendance });
      setHasChanges(false);
    } finally {
      setTransitioningStatus(null);
    }
  };

  const handleSyncRoster = async () => {
    if (syncingRoster || transitioningStatus || !training) return;

    setErrors({});
    setSyncingRoster(true);

    try {
      const result = await actions.syncTrainingRoster(training_id);
      if (!result.ok) setErrors({ [result.code]: true });
    } finally {
      setSyncingRoster(false);
    }
  };

  const handleReactivate = async () => {
    if (transitioningStatus || !training) return;

    if (!reactivationReason.trim()) {
      setErrors({ CORRECTION_REASON_REQUIRED: true });
      return;
    }

    setErrors({});
    setTransitioningStatus("reactivating");

    try {
      const result = await actions.reactivateTraining(
        training_id,
        reactivationReason.trim(),
      );

      if (!result.ok) {
        setErrors({ [result.code]: true });
        return;
      }

      setTraining(result.data.training);
      setReactivationOpen(false);
      setReactivationReason("");
      if (auditOpen) await loadAuditEvents();
    } finally {
      setTransitioningStatus(null);
    }
  };

  const toggleAudit = async () => {
    const nextOpen = !auditOpen;
    setAuditOpen(nextOpen);
    if (nextOpen) await loadAuditEvents();
  };

  const presentCount = Object.values(attendance).filter(
    (status) => status === "present",
  ).length;
  const lateCount = Object.values(attendance).filter(
    (status) => status === "late",
  ).length;
  const absentCount = Object.values(attendance).filter(
    (status) => status === "absent",
  ).length;
  const markedCount = Object.keys(attendance).length;
  const totalPlayers = store.players.length;
  const allMarked = markedCount === totalPlayers;
  const trainingStatus = getTrainingStatus(training?.status);
  const isScheduled = training?.status === "scheduled";
  const isCompleted = training?.status === "completed";
  const isCancelled = training?.status === "cancelled";
  const canTransitionTraining = ["club_owner", "coach"].includes(
    store.user?.role,
  );
  const attendanceEditable = isScheduled || attendanceCorrection;
  const generalErrorCode = Object.keys(errors).find(
    (code) => errors[code] && errorMessages[code],
  );

  if (loading) return <p>Cargando asistencia...</p>;

  return (
    <div className="training-detail-page">
      <PageHeader
        variant="detail"
        eyebrow="Entrenamiento"
        title="Asistencia"
        subtitle={isScheduled
          ? "Marca la asistencia de los deportistas convocados a esta sesión."
          : "Consulta el registro cerrado y realiza correcciones históricas cuando sea necesario."}
        onBack={() => navigate("/trainings")}
      />

      <Card className="training-info-card">
        <div className="training-info-header">
          <div>
            <span className="training-info-eyebrow">
              {training?.category_name || "Entrenamiento"}
            </span>
            <h3>{training?.team_name || "Entrenamiento"}</h3>
            {training && (
              <span className={`status-badge ${trainingStatus.className}`}>
                {trainingStatus.label}
              </span>
            )}
          </div>

          {!editMode && training && isScheduled && (
            <button
              type="button"
              className="training-info-edit-button"
              onClick={() => openTrainingEditor("normal")}
              aria-label="Editar información del entrenamiento"
            >
              <Pencil size={17} />
            </button>
          )}
        </div>

        {editMode ? (
          <div className="training-info-form">
            {editMode === "correction" && (
              <div className="training-correction-heading">
                <strong>Corrección histórica</strong>
                <span>El entrenamiento conservará su estado actual.</span>
              </div>
            )}

            <FormField
              label="Fecha"
              error={errors.TRAINING_DATE_REQUIRED
                ? errorMessages.TRAINING_DATE_REQUIRED
                : null}
            >
              <Input
                type="date"
                value={trainingForm.date}
                className={errors.TRAINING_DATE_REQUIRED ? "input-error" : ""}
                onChange={(event) =>
                  handleTrainingFormChange("date", event.target.value)}
              />
            </FormField>

            <div className="training-time-grid">
              <FormField
                label="Hora de inicio"
                error={errors.TRAINING_START_TIME_REQUIRED
                  ? errorMessages.TRAINING_START_TIME_REQUIRED
                  : null}
              >
                <Input
                  type="time"
                  value={trainingForm.start_time}
                  className={errors.TRAINING_START_TIME_REQUIRED ||
                    errors.INVALID_TRAINING_TIME_RANGE ? "input-error" : ""}
                  onChange={(event) =>
                    handleTrainingFormChange("start_time", event.target.value)}
                />
              </FormField>

              <FormField
                label="Hora de finalización"
                error={errors.TRAINING_END_TIME_REQUIRED
                  ? errorMessages.TRAINING_END_TIME_REQUIRED
                  : errors.INVALID_TRAINING_TIME_RANGE
                  ? errorMessages.INVALID_TRAINING_TIME_RANGE
                  : null}
              >
                <Input
                  type="time"
                  value={trainingForm.end_time}
                  className={errors.TRAINING_END_TIME_REQUIRED ||
                    errors.INVALID_TRAINING_TIME_RANGE ? "input-error" : ""}
                  onChange={(event) =>
                    handleTrainingFormChange("end_time", event.target.value)}
                />
              </FormField>
            </div>

            <FormField
              label="Ubicación"
              error={errors.TRAINING_LOCATION_REQUIRED
                ? errorMessages.TRAINING_LOCATION_REQUIRED
                : null}
            >
              <Input
                type="text"
                value={trainingForm.location}
                placeholder="Ej: Cancha central"
                className={errors.TRAINING_LOCATION_REQUIRED ? "input-error" : ""}
                onChange={(event) =>
                  handleTrainingFormChange("location", event.target.value)}
              />
            </FormField>

            {editMode === "correction" && (
              <FormField
                label="Motivo de la corrección *"
                error={errors.CORRECTION_REASON_REQUIRED
                  ? errorMessages.CORRECTION_REASON_REQUIRED
                  : null}
              >
                <textarea
                  className="input training-reason-input"
                  maxLength={500}
                  value={metadataReason}
                  onChange={(event) => setMetadataReason(event.target.value)}
                  placeholder="Explica por qué debe corregirse este registro"
                />
              </FormField>
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
                {savingTraining
                  ? "Guardando..."
                  : editMode === "correction"
                  ? "Guardar corrección"
                  : "Guardar cambios"}
              </Button>
            </div>
          </div>
        ) : training ? (
          <div className="training-info-compact">
            <div className="training-info-meta">
              <span>{formatTrainingDate(training.date)}</span>
              <span className="training-info-separator" aria-hidden="true">•</span>
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

        {isScheduled && canTransitionTraining && (
          <div className="training-status-actions">
            <Button
              type="button"
              variant="secondary"
              onClick={handleSyncRoster}
              disabled={syncingRoster || Boolean(transitioningStatus)}
            >
              {syncingRoster ? "Actualizando..." : "Actualizar participantes"}
            </Button>
            <Button
              type="button"
              onClick={() => handleTrainingTransition("completed")}
              disabled={Boolean(transitioningStatus) || syncingRoster}
            >
              {transitioningStatus === "completed"
                ? "Completando..."
                : "Completar entrenamiento"}
            </Button>
            <Button
              type="button"
              variant="danger"
              onClick={() => handleTrainingTransition("cancelled")}
              disabled={Boolean(transitioningStatus) || syncingRoster}
            >
              {transitioningStatus === "cancelled"
                ? "Cancelando..."
                : "Cancelar entrenamiento"}
            </Button>
          </div>
        )}

        {(isCompleted || isCancelled) && !editMode && (
          <div className="training-status-actions training-history-actions">
            <Button
              type="button"
              variant="secondary"
              onClick={() => openTrainingEditor("correction")}
            >
              Corregir información
            </Button>
            {isCancelled && (
              <Button
                type="button"
                onClick={() => {
                  setErrors({});
                  setReactivationOpen(true);
                }}
              >
                Reactivar entrenamiento
              </Button>
            )}
          </div>
        )}

        {reactivationOpen && isCancelled && (
          <div className="training-correction-panel">
            <div className="training-correction-heading">
              <strong>Reactivar entrenamiento</strong>
              <span>Volverá al estado programado sin borrar su historial.</span>
            </div>
            <FormField
              label="Motivo de la reactivación *"
              error={errors.CORRECTION_REASON_REQUIRED
                ? errorMessages.CORRECTION_REASON_REQUIRED
                : null}
            >
              <textarea
                className="input training-reason-input"
                maxLength={500}
                value={reactivationReason}
                onChange={(event) => setReactivationReason(event.target.value)}
                placeholder="Explica por qué se reactiva esta sesión"
              />
            </FormField>
            <div className="training-info-form-actions">
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  setReactivationOpen(false);
                  setReactivationReason("");
                  setErrors({});
                }}
                disabled={transitioningStatus === "reactivating"}
              >
                Cancelar
              </Button>
              <Button
                type="button"
                onClick={handleReactivate}
                disabled={transitioningStatus === "reactivating"}
              >
                {transitioningStatus === "reactivating"
                  ? "Reactivando..."
                  : "Confirmar reactivación"}
              </Button>
            </div>
          </div>
        )}
      </Card>

      <Card>
        <div className="training-attendance-heading">
          <div>
            <h3>Asistencia</h3>
            {!isScheduled && <p>Registro histórico en modo de solo lectura.</p>}
          </div>
          {isCompleted && !attendanceCorrection && (
            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                setErrors({});
                setAttendanceReason("");
                setAttendanceCorrection(true);
              }}
            >
              Corregir asistencia
            </Button>
          )}
        </div>

        {attendanceCorrection && (
          <div className="training-correction-heading">
            <strong>Corrección histórica de asistencia</strong>
            <span>Solo se guardarán las deportistas cuyo estado cambie.</span>
          </div>
        )}

        {store.players.length === 0 ? (
          <p>No hay deportistas en esta categoría.</p>
        ) : (
          <div className="attendance-list">
            {store.players.map((player) => {
              const status = attendance[player.id] || null;

              return (
                <div key={player.id} className="attendance-row">
                  <div className="attendance-player">
                    <span className="player-number">#{player.player_number}</span>
                    <span className="attendance-player-name">
                      {player.first_name} {player.last_name}
                    </span>
                  </div>
                  <AttendanceToggle
                    value={status}
                    disabled={!attendanceEditable}
                    onChange={(newStatus) =>
                      handleAttendanceChange(player.id, newStatus)}
                  />
                </div>
              );
            })}
          </div>
        )}

        {attendanceCorrection && (
          <div className="training-correction-panel">
            <FormField
              label="Motivo de la corrección *"
              error={errors.CORRECTION_REASON_REQUIRED
                ? errorMessages.CORRECTION_REASON_REQUIRED
                : null}
            >
              <textarea
                className="input training-reason-input"
                maxLength={500}
                value={attendanceReason}
                onChange={(event) => setAttendanceReason(event.target.value)}
                placeholder="Explica por qué debe corregirse la asistencia"
              />
            </FormField>
            <div className="training-info-form-actions">
              <Button
                type="button"
                variant="secondary"
                onClick={cancelAttendanceCorrection}
                disabled={saving}
              >
                Cancelar
              </Button>
              <Button
                type="button"
                onClick={handleSaveAttendance}
                disabled={saving || !hasChanges}
              >
                {saving ? "Guardando..." : "Guardar corrección"}
              </Button>
            </div>
          </div>
        )}
      </Card>

      {generalErrorCode && (
        <p className="form-error">{errorMessages[generalErrorCode]}</p>
      )}

      <Card className="training-audit-card">
        <div className="training-audit-header">
          <div>
            <h3>Historial de cambios</h3>
            <p>Correcciones realizadas sobre esta sesión.</p>
          </div>
          <Button type="button" variant="secondary" onClick={toggleAudit}>
            {auditOpen ? "Ocultar historial" : "Ver historial"}
          </Button>
        </div>

        {auditOpen && (
          auditLoading ? (
            <p>Cargando historial...</p>
          ) : auditEvents.length === 0 ? (
            <p className="training-audit-empty">
              No se han realizado correcciones.
            </p>
          ) : (
            <div className="training-audit-list">
              {auditEvents.map((event) => (
                <div className="training-audit-entry" key={event.id}>
                  <div className="training-audit-meta">
                    <strong>
                      {AUDIT_ACTION_LABELS[event.action] || "Actualizó el entrenamiento"}
                    </strong>
                    <span>
                      {formatAuditDate(event.created_at)} · {event.created_by_name || "Usuario"}
                    </span>
                  </div>

                  {event.action === "training_attendance_corrected" ? (
                    <ul>
                      {(event.changes?.players || []).map((change) => (
                        <li key={`${event.id}-${change.player_id}`}>
                          {change.player_name}: {ATTENDANCE_LABELS[change.from] || "Sin registro"}
                          {" → "}
                          {ATTENDANCE_LABELS[change.to] || change.to}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <ul>
                      {Object.entries(event.changes || {}).map(([field, change]) => (
                        <li key={`${event.id}-${field}`}>
                          {METADATA_LABELS[field] || field}: {formatAuditValue(field, change.from)}
                          {" → "}
                          {formatAuditValue(field, change.to)}
                        </li>
                      ))}
                    </ul>
                  )}

                  <p className="training-audit-reason">
                    <strong>Motivo:</strong> {event.reason}
                  </p>
                </div>
              ))}
            </div>
          )
        )}
      </Card>

      {isScheduled && (
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
      )}
    </div>
  );
};
