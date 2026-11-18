import React, { useEffect, useContext, useRef, useState } from "react";
import { Context } from "../../store/appContext";
import { useLocation, useParams, useNavigate } from "react-router-dom";

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
import { ReadOnlyNotice } from "../../component/ui/readOnlyNotice";
import {
  canManage,
  isTeamOperational,
  useTeamAccessLost,
} from "../../utils/coachAccess";
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
  const location = useLocation();

  const [players, setPlayers] = useState([]);
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
  const [teamOperational, setTeamOperational] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [infoMessage, setInfoMessage] = useState("");
  const loadRequestId = useRef(0);

  useTeamAccessLost(() => loadTrainingData());

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

  const loadRosterAttendance = async (requestId = null) => {
    const [playersResult, attendanceResult] = await Promise.all([
      actions.getTrainingPlayers(training_id),
      actions.getTrainingAttendance(training_id),
    ]);

    if (requestId !== null && requestId !== loadRequestId.current) {
      return { ok: false, stale: true };
    }

    if (!playersResult.ok) return playersResult;
    if (!attendanceResult.ok) return attendanceResult;

    const nextPlayers = playersResult.data.players || [];
    const attendanceMap = mapAttendanceRows(attendanceResult.data);
    setPlayers(nextPlayers);
    setAttendance(attendanceMap);
    setOriginalAttendance(attendanceMap);
    setHasChanges(false);

    return { ok: true };
  };

  const loadTrainingData = async () => {
    const requestId = loadRequestId.current + 1;
    loadRequestId.current = requestId;
    setLoading(true);
    setErrors({});
    setLoadError(null);
    setInfoMessage("");
    setTraining(null);
    setPlayers([]);
    setAttendance({});
    setOriginalAttendance({});

    const detailResult = await actions.getTrainingDetail(training_id);

    if (requestId !== loadRequestId.current) return;

    if (!detailResult.ok) {
      setLoadError(detailResult);
      setLoading(false);
      return;
    }

    const trainingData = detailResult.data.training;
    const rosterResult = await loadRosterAttendance(requestId);

    if (rosterResult.stale) return;

    if (!rosterResult.ok) {
      setLoadError(rosterResult);
      setLoading(false);
      return;
    }

    setTraining(trainingData);
    resetTrainingForm(trainingData);
    setTeamOperational(isTeamOperational({
      status: trainingData.team_status,
      season_status: trainingData.season_status,
    }));
    setLoading(false);
  };

  useEffect(() => {
    loadTrainingData();
    return () => {
      loadRequestId.current += 1;
    };
  }, [training_id]);

  const handleAttendanceChange = (playerId, newStatus) => {
    setAttendance((previous) => {
      const next = { ...previous, [playerId]: newStatus };
      const changed = players.some(
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

    const attendanceList = players
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
      : await actions.saveAttendance(
          training_id,
          attendanceList,
          players.map((player) => player.id),
        );
    setSaving(false);

    if (!result.ok) {
      if (result.code === "TRAINING_ROSTER_CHANGED") {
        await loadTrainingData();
        setErrors({ TRAINING_ROSTER_CHANGED: true });
        return;
      }
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
        ? "¿Completar este entrenamiento?\n\nEl entrenamiento quedará cerrado y sus participantes quedarán congelados. Los cambios posteriores requerirán una corrección histórica."
        : "¿Cancelar este entrenamiento?\n\nEl entrenamiento quedará cancelado. No se eliminarán sus participantes ni la asistencia registrada. Podrá reactivarse mientras el equipo y la temporada sigan operativos.",
    );

    if (!confirmed) return;

    setErrors({});
    setTransitioningStatus(targetStatus);

    try {
      const result = isCompleting
        ? await actions.completeTraining(training_id)
        : await actions.cancelTraining(training_id);

      if (!result.ok) {
        if ([
          "INVALID_TRAINING_STATUS",
          "TEAM_ARCHIVED",
          "SEASON_CLOSED",
          "TRAINING_ATTENDANCE_INCOMPLETE",
          "TRAINING_ROSTER_EMPTY",
        ].includes(result.code)) {
          await loadTrainingData();
          setErrors({ [result.code]: true });
          return;
        }
        setErrors({ [result.code]: true });
        return;
      }

      setTraining((previous) => ({
        ...previous,
        ...result.data.training,
      }));
      setAttendance({ ...originalAttendance });
      setHasChanges(false);
    } finally {
      setTransitioningStatus(null);
    }
  };

  const handleSyncRoster = async () => {
    if (syncingRoster || transitioningStatus || !training) return;

    if (hasChanges) {
      const discardDraft = window.confirm(
        "Tienes cambios de asistencia sin guardar. Actualizar participantes descartará esos cambios. ¿Deseas continuar?",
      );

      if (!discardDraft) return;
    }

    setErrors({});
    setSyncingRoster(true);

    try {
      const result = await actions.syncTrainingRoster(training_id);
      if (!result.ok) {
        setErrors({ [result.code]: true });
        return;
      }

      const rosterResult = await loadRosterAttendance();
      if (!rosterResult.ok) setErrors({ [rosterResult.code]: true });
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

      setTraining((previous) => ({
        ...previous,
        ...result.data.training,
      }));
      setReactivationOpen(false);
      setReactivationReason("");
      setInfoMessage("Entrenamiento reactivado. Revisa los participantes antes de continuar.");
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

  const handleMarkAllPresent = () => {
    const next = Object.fromEntries(
      players.map((player) => [player.id, "present"]),
    );
    const changed = players.some(
      (player) => originalAttendance[player.id] !== "present",
    );

    setAttendance(next);
    setHasChanges(changed);
    setErrors({});
  };

  const presentCount = players.filter(
    (player) => attendance[player.id] === "present",
  ).length;
  const lateCount = players.filter(
    (player) => attendance[player.id] === "late",
  ).length;
  const absentCount = players.filter(
    (player) => attendance[player.id] === "absent",
  ).length;
  const markedCount = players.filter((player) => attendance[player.id]).length;
  const persistedMarkedCount = players.filter(
    (player) => originalAttendance[player.id],
  ).length;
  const totalPlayers = players.length;
  const allMarked = totalPlayers > 0 && markedCount === totalPlayers;
  const persistedAttendanceComplete = (
    totalPlayers > 0 && persistedMarkedCount === totalPlayers
  );
  const trainingStatus = getTrainingStatus(training?.status);
  const isScheduled = training?.status === "scheduled";
  const isCompleted = training?.status === "completed";
  const isCancelled = training?.status === "cancelled";
  const canTransitionTraining = ["club_owner", "coach"].includes(
    store.user?.role,
  );
  const canManageTraining = canManage(training);
  const canOperateTraining = canManageTraining && teamOperational;
  const attendanceEditable =
    (isScheduled && canOperateTraining) || attendanceCorrection;
  const completeReady = (
    totalPlayers > 0 && persistedAttendanceComplete && !hasChanges
  );
  const completionHelp = totalPlayers === 0
    ? "Agrega participantes antes de completar."
    : hasChanges
    ? "Guarda la asistencia antes de completar."
    : !persistedAttendanceComplete
    ? "Marca la asistencia de todos."
    : "La asistencia está completa. Ya puedes cerrar el entrenamiento.";
  const generalErrorCode = Object.keys(errors).find(
    (code) => errors[code] && errorMessages[code],
  );

  if (loading) return <p role="status">Cargando entrenamiento...</p>;

  if (loadError) {
    return (
      <Card className="page-error-state" role="alert">
        <h2>
          {loadError.code === "TRAINING_NOT_FOUND"
            ? "Entrenamiento no encontrado"
            : loadError.code === "FORBIDDEN"
            ? "No tienes acceso a este entrenamiento"
            : "No pudimos cargar el entrenamiento"}
        </h2>
        <p>{errorMessages[loadError.code] || loadError.message || "Ocurrió un error temporal."}</p>
        <Button type="button" onClick={loadTrainingData}>Volver a intentar</Button>
      </Card>
    );
  }

  return (
    <div className="training-detail-page">
      <PageHeader
        variant="detail"
        eyebrow={training?.category_name || "Entrenamiento"}
        title={training?.team_name || "Entrenamiento"}
        subtitle={!canManageTraining
          ? "Consulta este entrenamiento en modo de solo lectura."
          : isScheduled && canOperateTraining
          ? "Revisa participantes, registra asistencia y completa la sesión."
          : isScheduled
          ? "Esta sesión no admite cambios porque su equipo no está operativo."
          : "Consulta el registro cerrado y sus correcciones históricas."}
        onBack={() => navigate(
          location.state?.from || `/trainings${location.search}`,
        )}
      />

      <div className="training-context-line" aria-label="Contexto del entrenamiento">
        <span>{training?.category_name || "Sin categoría"}</span>
        <span aria-hidden="true">·</span>
        <span>{training?.season_name || "Sin temporada"}</span>
        {training?.season_status === "closed" && (
          <span className="status-badge status-muted">Temporada cerrada</span>
        )}
        {training?.season_status === "planned" && (
          <span className="status-badge status-info">En preparación</span>
        )}
      </div>

      {training && !canManageTraining && (
        <ReadOnlyNotice>
          Estás consultando un entrenamiento de un equipo que no tienes
          asignado.
        </ReadOnlyNotice>
      )}

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

          {!editMode && training && isScheduled && canOperateTraining && (
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
              htmlFor="training-detail-date"
              errorId="training-detail-date-error"
              error={errors.TRAINING_DATE_REQUIRED
                ? errorMessages.TRAINING_DATE_REQUIRED
                : null}
            >
              <Input
                id="training-detail-date"
                aria-describedby={errors.TRAINING_DATE_REQUIRED ? "training-detail-date-error" : undefined}
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
                htmlFor="training-detail-start"
                errorId="training-detail-start-error"
                error={errors.TRAINING_START_TIME_REQUIRED
                  ? errorMessages.TRAINING_START_TIME_REQUIRED
                  : null}
              >
                <Input
                  id="training-detail-start"
                  aria-describedby={errors.TRAINING_START_TIME_REQUIRED ? "training-detail-start-error" : undefined}
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
                htmlFor="training-detail-end"
                errorId="training-detail-end-error"
                error={errors.TRAINING_END_TIME_REQUIRED
                  ? errorMessages.TRAINING_END_TIME_REQUIRED
                  : errors.INVALID_TRAINING_TIME_RANGE
                  ? errorMessages.INVALID_TRAINING_TIME_RANGE
                  : null}
              >
                <Input
                  id="training-detail-end"
                  aria-describedby={errors.TRAINING_END_TIME_REQUIRED || errors.INVALID_TRAINING_TIME_RANGE ? "training-detail-end-error" : undefined}
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
              htmlFor="training-detail-location"
              errorId="training-detail-location-error"
              error={errors.TRAINING_LOCATION_REQUIRED
                ? errorMessages.TRAINING_LOCATION_REQUIRED
                : null}
            >
              <Input
                id="training-detail-location"
                aria-describedby={errors.TRAINING_LOCATION_REQUIRED ? "training-detail-location-error" : undefined}
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
                helper="El motivo quedará registrado en el historial de cambios."
                htmlFor="training-metadata-reason"
                errorId="training-metadata-reason-error"
                error={errors.CORRECTION_REASON_REQUIRED
                  ? errorMessages.CORRECTION_REASON_REQUIRED
                  : null}
              >
                <textarea
                  id="training-metadata-reason"
                  aria-describedby={errors.CORRECTION_REASON_REQUIRED ? "training-metadata-reason-error" : undefined}
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

        {canManageTraining && (isCompleted || isCancelled) && !editMode && (
          <div className="training-status-actions training-history-actions">
            <Button
              type="button"
              variant="secondary"
              onClick={() => openTrainingEditor("correction")}
            >
              Corregir información
            </Button>
            {isCancelled && teamOperational && (
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
            {isCancelled && !teamOperational && (
              <p className="training-operation-note">
                No puede reactivarse porque el equipo está archivado o la temporada no está activa.
              </p>
            )}
          </div>
        )}

        {reactivationOpen && isCancelled && (
          <div className="training-correction-panel">
            <div className="training-correction-heading">
              <strong>Reactivar entrenamiento</strong>
              <span>
                Volverá a Programado, conservará participantes y asistencia,
                y no actualizará el roster automáticamente.
              </span>
            </div>
            <FormField
              label="Motivo de la reactivación *"
              helper="El motivo quedará registrado en el historial de cambios."
              htmlFor="training-reactivation-reason"
              errorId="training-reactivation-reason-error"
              error={errors.CORRECTION_REASON_REQUIRED
                ? errorMessages.CORRECTION_REASON_REQUIRED
                : null}
            >
              <textarea
                id="training-reactivation-reason"
                aria-describedby={errors.CORRECTION_REASON_REQUIRED ? "training-reactivation-reason-error" : undefined}
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

      {infoMessage && (
        <p className="training-info-message" role="status">{infoMessage}</p>
      )}

      <Card className="training-participants-card">
        <div className="training-attendance-heading">
          <div>
            <h3>Participantes</h3>
            <p>
              {totalPlayers > 0
                ? `${totalPlayers} deportistas en el roster de esta sesión.`
                : "Este entrenamiento no tiene participantes."}
            </p>
          </div>
          {isScheduled && canOperateTraining && (
            <Button
              type="button"
              variant="secondary"
              onClick={handleSyncRoster}
              disabled={syncingRoster || Boolean(transitioningStatus)}
            >
              {syncingRoster ? "Actualizando..." : "Actualizar participantes"}
            </Button>
          )}
        </div>
        {isScheduled && canOperateTraining && (
          <p className="training-sync-help">
            Agrega nuevos deportistas elegibles, actualiza dorsales y retira
            quienes ya no son elegibles. Las asistencias existentes se conservan.
          </p>
        )}
      </Card>

      <Card>
        <div className="training-attendance-heading">
          <div>
            <h3>Asistencia</h3>
            <p className={`attendance-state ${
              hasChanges
                ? "is-dirty"
                : persistedAttendanceComplete
                ? "is-complete"
                : ""
            }`}>
              {hasChanges
                ? "Cambios sin guardar"
                : totalPlayers === 0
                ? "Sin participantes"
                : persistedMarkedCount === 0
                ? "Sin comenzar"
                : persistedAttendanceComplete
                ? "Asistencia completa"
                : "Asistencia incompleta"}
            </p>
            <div className="attendance-summary" aria-label="Resumen de asistencia">
              <span>{markedCount} de {totalPlayers} registrados</span>
              <span>{presentCount} presentes</span>
              <span>{lateCount} tarde</span>
              <span>{absentCount} ausentes</span>
            </div>
            {(!isScheduled || !canOperateTraining) && (
              <p>Registro en modo de solo lectura.</p>
            )}
          </div>
          <div className="training-attendance-actions">
            {isScheduled && canOperateTraining && totalPlayers > 0 && (
              <Button
                type="button"
                variant="secondary"
                onClick={handleMarkAllPresent}
                disabled={saving}
              >
                Marcar todos presentes
              </Button>
            )}
            {canManageTraining && isCompleted && !attendanceCorrection && (
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
        </div>

        {attendanceCorrection && (
          <div className="training-correction-heading">
            <strong>Corrección histórica de asistencia</strong>
            <span>Solo se guardarán las deportistas cuyo estado cambie.</span>
          </div>
        )}

        {players.length === 0 ? (
          <p>Este entrenamiento no tiene participantes.</p>
        ) : (
          <div className="attendance-list">
            {players.map((player) => {
              const status = attendance[player.id] || null;
              const playerName = `${player.first_name} ${player.last_name}`;

              return (
                <div key={player.id} className="attendance-row">
                  <div className="attendance-player">
                    <span className="player-number">#{player.player_number}</span>
                    <span className="attendance-player-name">
                      {playerName}
                    </span>
                    {player.team_player_status === "injured" && (
                      <span className="status-badge status-muted">Lesionado/a</span>
                    )}
                    {!player.is_currently_eligible && (
                      <span className="status-badge status-muted">Ya no elegible</span>
                    )}
                  </div>
                  <AttendanceToggle
                    value={status}
                    disabled={!attendanceEditable}
                    playerName={playerName}
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
              helper="El motivo quedará registrado en el historial de cambios."
              htmlFor="training-attendance-reason"
              errorId="training-attendance-reason-error"
              error={errors.CORRECTION_REASON_REQUIRED
                ? errorMessages.CORRECTION_REASON_REQUIRED
                : null}
            >
              <textarea
                id="training-attendance-reason"
                aria-describedby={errors.CORRECTION_REASON_REQUIRED ? "training-attendance-reason-error" : undefined}
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

      {isScheduled && canOperateTraining && (
        <div className="attendance-sticky-bar">
          <div>
            <div className="attendance-progress">
              {markedCount} / {totalPlayers} deportistas marcados
            </div>
            <div className="attendance-summary">
              <span>{presentCount} presentes</span>
              <span>{lateCount} tarde</span>
              <span>{absentCount} ausentes</span>
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
              ? totalPlayers === 0
                ? "Sin participantes"
                : `Faltan ${totalPlayers - markedCount}`
              : hasChanges
              ? "Guardar asistencia"
              : "Sin cambios"}
          </Button>
        </div>
      )}

      {isScheduled && canTransitionTraining && canOperateTraining && (
        <Card className="training-completion-card">
          <div>
            <h3>Finalizar entrenamiento</h3>
            <p>{completionHelp}</p>
          </div>
          <div className="training-status-actions">
            <Button
              type="button"
              onClick={() => handleTrainingTransition("completed")}
              disabled={
                !completeReady ||
                Boolean(transitioningStatus) ||
                syncingRoster
              }
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
        </Card>
      )}

      {(isCompleted || isCancelled) && (
        <Card className="training-closed-summary" role="note">
          <strong>
            {isCompleted ? "Registro cerrado" : "Entrenamiento cancelado"}
          </strong>
          <span>
            {totalPlayers} participantes · {presentCount} presentes · {lateCount} tarde · {absentCount} ausentes
          </span>
          {isCancelled && !persistedAttendanceComplete && (
            <span>La asistencia conservada puede estar incompleta.</span>
          )}
        </Card>
      )}

      {generalErrorCode && (
        <p className="form-error" role="alert">
          {errorMessages[generalErrorCode]}
        </p>
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
            <p role="status">Cargando historial...</p>
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

    </div>
  );
};
