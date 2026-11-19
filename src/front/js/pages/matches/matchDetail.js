import React, { useEffect, useState, useContext, useMemo, useRef } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import {
  DollarSign,
  Users,
  ReceiptText,
  AlertCircle,
  CircleCheck,
  ArrowRight,
  Check,
} from "lucide-react";
import { Context } from "../../store/appContext";
import { PageHeader } from "../../component/ui/pageHeader";
import { Card } from "../../component/ui/card";
import { Button } from "../../component/ui/button";
import { Select } from "../../component/ui/select";
import { FormField } from "../../component/ui/formField";
import { errorMessages } from "../../utils/errorMessages";
import { formatMoney } from "../../utils/money";
import { ReadOnlyNotice } from "../../component/ui/readOnlyNotice";
import { FeeEditor } from "../../component/feeEditor";
import {
  canManage,
  resolveTeamOperational,
  useTeamAccessLost,
} from "../../utils/coachAccess";
import "../../../styles/matchDetail.css";

const STEPS = ["Convocadas", "Estado"];
const MATCH_STATUS_LABELS = {
  present: "Presente",
  late: "Llegó tarde",
  absent: "Ausente",
  injured: "Lesionada",
};
const PLAYABLE_STATUSES = ["present", "late"];
const PREFLIGHT_LABELS = {
  callup: "Convocatoria",
  attendance: "Asistencia",
  capture_mode: "Modo de captura",
  lineup: "Alineación y participación",
  stats: "Estadísticas",
  result: "Resultado",
};

const POSITION_LABELS = {
  setter: "Armador",
  outside: "Punta",
  middle: "Central",
  opposite: "Opuesto",
  libero: "Líbero",
};

const POSITION_OPTIONS = [
  { value: "setter", label: "Armador" },
  { value: "outside", label: "Punta" },
  { value: "middle", label: "Central" },
  { value: "opposite", label: "Opuesto" },
  { value: "libero", label: "Líbero" },
];

const hasValidSavedResult = (match) => {
  if (!match || !["win", "loss"].includes(match.result)) return false;

  const homeSets = Number(match.home_sets);
  const opponentSets = Number(match.opponent_sets);

  if (!Number.isInteger(homeSets) || !Number.isInteger(opponentSets)) {
    return false;
  }

  if (homeSets < 0 || opponentSets < 0) return false;
  if (homeSets > 3 || opponentSets > 3) return false;
  if (homeSets === opponentSets) return false;
  if (Math.max(homeSets, opponentSets) !== 3) return false;
  if (Math.min(homeSets, opponentSets) > 2) return false;

  const expectedResult = homeSets > opponentSets ? "win" : "loss";

  return match.result === expectedResult;
};

const getPaymentStatusData = (status) => {
  const statuses = {
    pending: {
      label: "Pendiente",
      className: "status-warning",
    },
    paid: {
      label: "Pagado",
      className: "status-success",
    },
    overdue: {
      label: "Vencido",
      className: "status-danger",
    },
    cancelled: {
      label: "Cancelado",
      className: "status-muted",
    },
  };

  return (
    statuses[status] || {
      label: status || "Sin estado",
      className: "status-muted",
    }
  );
};

export const MatchDetail = () => {
  const { store, actions } = useContext(Context);
  const { match_id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();

  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [match, setMatch] = useState(null);
  const [preflight, setPreflight] = useState(null);
  const [events, setEvents] = useState([]);
  const [roster, setRoster] = useState([]);
  const loadRequestId = useRef(0);
  const [currentStep, setCurrentStep] = useState(0);
  const [resultError, setResultError] = useState("");
  const [captureModeError, setCaptureModeError] = useState("");
  const [savingCaptureMode, setSavingCaptureMode] = useState(false);
  const [showParticipationEditor, setShowParticipationEditor] =
    useState(false);
  const [selectedParticipantIds, setSelectedParticipantIds] = useState([]);
  const [savingParticipation, setSavingParticipation] = useState(false);
  const [participationError, setParticipationError] = useState("");
  const [participationMessage, setParticipationMessage] = useState("");

  const [teamPlayers, setTeamPlayers] = useState([]);
  const [selectedPlayers, setSelectedPlayers] = useState([]);
  const MATCH_STATES = ["present", "late", "absent", "injured"];

  const [homeSets, setHomeSets] = useState(0);
  const [opponentSets, setOpponentSets] = useState(0);
  const [savingResult, setSavingResult] = useState(false);
  const [showResultEditor, setShowResultEditor] = useState(false);
  const [finalizingMatch, setFinalizingMatch] = useState(false);
  const [showFinalizeDialog, setShowFinalizeDialog] = useState(false);
  const [finalizeError, setFinalizeError] = useState("");
  const finalizeRequestInFlight = useRef(false);
  const finalizeDialogRef = useRef(null);
  const finalizeReturnFocusRef = useRef(null);
  const finalizingMatchRef = useRef(false);
  const [statusDirty, setStatusDirty] = useState(false);
  const [rosterError, setRosterError] = useState("");
  const [statusError, setStatusError] = useState("");
  const [savingRoster, setSavingRoster] = useState(false);
  const [savingStatus, setSavingStatus] = useState(false);
  const [selectedLineupIds, setSelectedLineupIds] = useState([]);
  const [savingLineup, setSavingLineup] = useState(false);
  const [lineupError, setLineupError] = useState("");

  const [refereePreview, setRefereePreview] = useState(null);
  const [loadingRefereePreview, setLoadingRefereePreview] = useState(false);
  const [generatingRefereeCharges, setGeneratingRefereeCharges] =
    useState(false);
  const [refereeError, setRefereeError] = useState("");
  const [refereeErrorCode, setRefereeErrorCode] = useState("");
  const [teamOperational, setTeamOperational] = useState(true);

  useTeamAccessLost(() => loadMatch());

  const totalSets = homeSets + opponentSets;
  const disableHomeIncrease = homeSets >= 3 || totalSets >= 5;
  const disableOpponentIncrease = opponentSets >= 3 || totalSets >= 5;

  useEffect(() => {
    loadMatch();
    return () => {
      loadRequestId.current += 1;
    };
  }, [match_id]);

  useEffect(() => {
    finalizingMatchRef.current = finalizingMatch;
  }, [finalizingMatch]);

  useEffect(() => {
    if (!showFinalizeDialog) return undefined;

    const dialog = finalizeDialogRef.current;
    const focusableSelector = [
      "button:not([disabled])",
      "[href]",
      "input:not([disabled])",
      "select:not([disabled])",
      "textarea:not([disabled])",
      "[tabindex]:not([tabindex='-1'])",
    ].join(",");
    const focusable = () => [...(dialog?.querySelectorAll(focusableSelector) || [])];
    (focusable()[0] || dialog)?.focus();

    const keepFocusInside = (event) => {
      if (event.key === "Escape" && !finalizingMatchRef.current) {
        setShowFinalizeDialog(false);
        return;
      }

      if (event.key !== "Tab") return;
      const controls = focusable();
      if (!controls.length) {
        event.preventDefault();
        dialog?.focus();
        return;
      }
      const first = controls[0];
      const last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", keepFocusInside);
    return () => {
      document.removeEventListener("keydown", keepFocusInside);
      finalizeReturnFocusRef.current?.focus?.();
    };
  }, [showFinalizeDialog]);

  const loadMatch = async () => {
    const requestId = loadRequestId.current + 1;
    loadRequestId.current = requestId;
    setLoading(true);
    setLoadError(null);
    setMatch(null);
    setPreflight(null);
    setRoster([]);
    setTeamPlayers([]);
    setEvents([]);

    const matchResult = await actions.getMatchDetail(match_id);

    if (requestId !== loadRequestId.current) return;
    if (!matchResult.ok) {
      setLoadError(matchResult);
      setStatusDirty(false);
      setLoading(false);
      return;
    }

    const matchData = matchResult.data.match;

    setMatch(matchData);
    setPreflight(matchResult.data.preflight || null);
    setHomeSets(matchData.home_sets || 0);
    setOpponentSets(matchData.opponent_sets || 0);
    setCurrentStep(
      matchData.is_completed || matchResult.data.preflight?.readonly_reason
        ? 0
        : matchResult.data.preflight?.callup?.ready
        ? 1
        : 0,
    );

    const [rosterResult, eventsResult, operational] = await Promise.all([
      actions.getMatchRoster(match_id),
      actions.getMatchEvents(match_id),
      resolveTeamOperational(actions, matchData.team_id),
    ]);

    if (requestId !== loadRequestId.current) return;
    setTeamOperational(operational);

    if (rosterResult.ok) {
      const rosterData = rosterResult.data || [];

      const normalizedRoster = rosterData.map((player) => ({
        ...player,
        position: player.position || "",
      }));

      setRoster(normalizedRoster);
      setTeamPlayers(normalizedRoster);
      setSelectedPlayers(
        rosterData.filter((p) => p.is_called).map((p) => p.player_id),
      );
      setSelectedParticipantIds(
        rosterData
          .filter(
            (player) =>
              player.is_called &&
              PLAYABLE_STATUSES.includes(player.attendance_status) &&
              player.did_play,
          )
          .map((player) => player.match_player_id),
      );
      setSelectedLineupIds(
        rosterData
          .filter((player) => player.is_on_court)
          .map((player) => player.match_player_id),
      );
    }

    setEvents(eventsResult.ok ? eventsResult.data.events || [] : []);

    setLoading(false);
  };

  const togglePlayerSelection = (player) => {
    setRosterError("");

    setRefereePreview(null);
    setRefereeError("");
    setRefereeErrorCode("");

    setSelectedPlayers((prev) => {
      const exists = prev.includes(player.player_id);

      if (exists) {
        return prev.filter((id) => id !== player.player_id);
      }

      return [...prev, player.player_id];
    });
  };

  const toggleMatchStatus = (matchPlayerId) => {
    setStatusDirty(true);
    setStatusError("");

    setRoster((prev) =>
      prev.map((player) => {
        if (player.match_player_id !== matchPlayerId) return player;

        const currentIndex = MATCH_STATES.indexOf(player.attendance_status);
        const nextStatus =
          MATCH_STATES[(currentIndex + 1) % MATCH_STATES.length];

        const isPlayable = nextStatus === "present" || nextStatus === "late";

        return {
          ...player,
          attendance_status: nextStatus,
          did_play: isPlayable ? player.did_play : false,
          position: player.position,
        };
      }),
    );
  };

  const setMatchStatus = (matchPlayerId, attendanceStatus) => {
    setStatusDirty(true);
    setStatusError("");
    setRoster((previous) => previous.map((player) =>
      player.match_player_id === matchPlayerId
        ? {
            ...player,
            attendance_status: attendanceStatus,
            did_play: PLAYABLE_STATUSES.includes(attendanceStatus)
              ? player.did_play
              : false,
            is_on_court: PLAYABLE_STATUSES.includes(attendanceStatus)
              ? player.is_on_court
              : false,
          }
        : player,
    ));
  };

  const markAllCalledPresent = () => {
    setStatusDirty(true);
    setStatusError("");
    setRoster((previous) => previous.map((player) =>
      player.is_called
        ? { ...player, attendance_status: "present" }
        : player,
    ));
  };

  const updatePlayerPosition = (matchPlayerId, newPosition) => {
    setStatusDirty(true);
    setStatusError("");

    setRoster((prev) =>
      prev.map((player) => {
        if (player.match_player_id !== matchPlayerId) return player;

        return {
          ...player,
          position: newPosition,
        };
      }),
    );
  };

  const saveStepOne = async () => {
    if (savingRoster) return;

    if (selectedPlayers.length === 0) {
      setRosterError(errorMessages.MATCH_ROSTER_REQUIRED);
      return;
    }

    setRosterError("");
    setSavingRoster(true);

    const playersPayload = teamPlayers
      .filter((p) => selectedPlayers.includes(p.player_id))
      .map((p) => ({
        player_id: p.player_id,
        player_number: p.player_number,
      }));

    const result = await actions.saveMatchRoster(match_id, playersPayload);

    setSavingRoster(false);

    if (!result?.ok) {
      setRosterError(
        errorMessages[result.code] ||
          result.message ||
          "No se pudo guardar la convocatoria",
      );

      // Nada se guardó: la selección vuelve a la convocatoria real.
      if (result.code === "FINANCE_DEPENDENCY") {
        setSelectedPlayers(
          roster.filter((p) => p.is_called).map((p) => p.player_id),
        );
      }

      return;
    }
    setCurrentStep(1);
    setRefereePreview(null);
    await loadMatch();
  };

  const saveStepTwo = async () => {
    if (savingStatus) return;

    const calledPlayers = roster.filter((p) => p.is_called);

    const hasMissingStatus = calledPlayers.some((p) => !p.attendance_status);

    if (hasMissingStatus) {
      setStatusError(errorMessages.MATCH_STATUS_REQUIRED);
      return;
    }

    setStatusError("");
    setSavingStatus(true);

    const playersPayload = calledPlayers.map((player) => ({
      match_player_id: player.match_player_id,
      attendance_status: player.attendance_status,
      position: player.position || null,
    }));

    const result = await actions.saveMatchStatus(match_id, playersPayload);

    setSavingStatus(false);

    if (!result?.ok) {
      setStatusError(result.message || "No se pudo guardar el estado");
      return;
    }

    setMatch((prev) => ({
      ...prev,
      match_step: 2,
    }));

    setStatusDirty(false);
    setCurrentStep(1);
    await loadMatch();
  };

  const saveMatchResult = async () => {
    setResultError("");
    setFinalizeError("");
    setSavingResult(true);

    const result = await actions.saveMatchResult(match_id, {
      home_sets: homeSets,
      opponent_sets: opponentSets,
    });

    setSavingResult(false);

    if (!result?.ok) {
      setResultError(result.message || "Resultado inválido");
      return;
    }

    setShowResultEditor(false);
    await loadMatch();
  };

  const updateCaptureMode = async (captureMode) => {
    if (savingCaptureMode || match?.capture_mode === captureMode) return;

    setCaptureModeError("");
    setSavingCaptureMode(true);

    const result = await actions.updateMatchCaptureMode(
      match_id,
      captureMode,
    );

    setSavingCaptureMode(false);

    if (!result?.ok) {
      setCaptureModeError(
        errorMessages[result.code] ||
          result.message ||
          "No se pudo actualizar el modo de captura",
      );
      return;
    }

    setMatch(result.data.match);
    setShowParticipationEditor(false);
    setParticipationError("");
    setParticipationMessage("");
  };

  const toggleParticipant = (matchPlayerId) => {
    setParticipationError("");
    setParticipationMessage("");

    setSelectedParticipantIds((currentIds) =>
      currentIds.includes(matchPlayerId)
        ? currentIds.filter((id) => id !== matchPlayerId)
        : [...currentIds, matchPlayerId],
    );
  };

  const saveSummaryParticipation = async () => {
    if (savingParticipation) return;

    const eligiblePlayers = roster.filter(
      (player) =>
        player.is_called &&
        PLAYABLE_STATUSES.includes(player.attendance_status),
    );

    if (eligiblePlayers.length === 0) {
      setParticipationError(
        "No hay jugadoras presentes o que hayan llegado tarde.",
      );
      return;
    }

    setParticipationError("");
    setParticipationMessage("");
    setSavingParticipation(true);

    const result = await actions.saveMatchParticipation(
      match_id,
      eligiblePlayers.map((player) => ({
        match_player_id: player.match_player_id,
        did_play: selectedParticipantIds.includes(player.match_player_id),
      })),
    );

    setSavingParticipation(false);

    if (!result?.ok) {
      setParticipationError(
        errorMessages[result.code] ||
          result.message ||
          "No se pudo guardar la participación",
      );
      return;
    }

    setParticipationMessage("Participación guardada correctamente.");
    await loadMatch();
  };

  const toggleLineupPlayer = (matchPlayerId) => {
    setLineupError("");
    setSelectedLineupIds((current) => {
      if (current.includes(matchPlayerId)) {
        return current.filter((id) => id !== matchPlayerId);
      }
      if (current.length >= 6) {
        setLineupError("Solo puedes seleccionar seis titulares.");
        return current;
      }
      return [...current, matchPlayerId];
    });
  };

  const saveSummaryLineup = async () => {
    if (savingLineup || selectedLineupIds.length !== 6) return;
    setLineupError("");
    setSavingLineup(true);
    const result = await actions.saveStartingLineup(match_id, selectedLineupIds);
    setSavingLineup(false);
    if (!result.ok) {
      setLineupError(result.message || "No se pudo guardar la alineación.");
      if (["MATCH_ROSTER_CHANGED", "MATCH_ATTENDANCE_CHANGED"].includes(result.code)) {
        await loadMatch();
      }
      return;
    }
    await loadMatch();
  };

  const finalizeMatch = async () => {
    if (finalizeRequestInFlight.current) return;

    finalizeRequestInFlight.current = true;

    setFinalizeError("");
    setFinalizingMatch(true);

    const result = await actions.finalizeMatch(match_id);

    if (!result?.ok) {
      setFinalizeError(
        result.message ||
          errorMessages[result.code] ||
          "No se pudo finalizar el partido",
      );
      setFinalizingMatch(false);
      finalizeRequestInFlight.current = false;
      if (result.raw?.preflight) setPreflight(result.raw.preflight);
      return;
    }

    setShowFinalizeDialog(false);
    setShowResultEditor(false);
    await loadMatch();
    setFinalizingMatch(false);
    finalizeRequestInFlight.current = false;
  };

  const filteredPlayers = useMemo(() => {
    if (currentStep === 0) return roster;

    if (currentStep === 1) {
      return roster.filter((p) => p.is_called);
    }

    return [];
  }, [roster, currentStep]);

  const hasUnsavedRosterChanges = useMemo(() => {
    const savedIds = roster
      .filter((p) => p.is_called)
      .map((p) => p.player_id)
      .sort();

    const selectedIds = [...selectedPlayers].sort();

    return JSON.stringify(savedIds) !== JSON.stringify(selectedIds);
  }, [roster, selectedPlayers]);

  const maxUnlockedStep = preflight?.callup?.ready ? 1 : 0;

  const canOpenLiveMode = Boolean(preflight?.attendance?.ready);

  const hasPlayersWhoPlayed = roster.some(
    (player) =>
      player.is_called &&
      PLAYABLE_STATUSES.includes(player.attendance_status) &&
      player.did_play,
  );

  const participationEligiblePlayers = roster.filter(
    (player) =>
      player.is_called &&
      PLAYABLE_STATUSES.includes(player.attendance_status),
  );

  const initialPlayersOnCourt = roster.filter(
    (player) =>
      player.is_called &&
      PLAYABLE_STATUSES.includes(player.attendance_status) &&
      player.did_play &&
      player.is_on_court,
  );

  const hasInitialSix = initialPlayersOnCourt.length === 6;

  const statusSaved = Boolean(preflight?.attendance?.ready);
  const isMatchCompleted = match?.is_completed;
  const canOperateMatch = canManage(match) && teamOperational;
  const parentReadonly = Boolean(
    preflight?.readonly_reason &&
      !["MATCH_COMPLETED", "TEAM_NOT_ASSIGNED"].includes(preflight.readonly_reason),
  );
  const isReadOnlyMatch = isMatchCompleted || !canOperateMatch || parentReadonly;
  const canFinalizeMatch = Boolean(preflight?.can_finalize) && !isReadOnlyMatch;
  const canManageMatchFinance = store.user?.role === "club_owner";

  const refereeFeeConfigured =
    match?.referee_fee !== null && match?.referee_fee !== undefined;

  const refereeFee = Number(match?.referee_fee || 0);

  const calledPlayersCount = roster.filter((player) => player.is_called).length;
  const attendanceRecorded = preflight?.attendance?.counts?.recorded || 0;
  const attendanceRequired = preflight?.attendance?.counts?.required || calledPlayersCount;
  const statsReviewed = preflight?.stats?.counts?.reviewed || 0;
  const statsRequired = preflight?.stats?.counts?.required || 0;
  const callupLocked = Boolean(
    attendanceRecorded > 0 ||
      preflight?.lineup?.ready ||
      preflight?.participation?.counts?.participants > 0 ||
      statsReviewed > 0,
  );

  const existingRefereeChargesCount =
    refereePreview?.existing_charges_count || 0;

  const hasGeneratedRefereeCharges = existingRefereeChargesCount > 0;

  const canPreviewRefereeCharges =
    canManageMatchFinance &&
    refereeFeeConfigured &&
    refereeFee > 0 &&
    calledPlayersCount > 0 &&
    !hasUnsavedRosterChanges;

  const getResultButtonText = () => {
    if (showResultEditor) return "Ocultar resultado";
    if (match?.result) return "Actualizar resultado";

    return "Registrar sets";
  };

  const openFinalizeDialog = () => {
    finalizeReturnFocusRef.current = document.activeElement;
    setShowFinalizeDialog(true);
  };

  const loadRefereePreview = async () => {
    if (!canManageMatchFinance || loadingRefereePreview) return;

    setRefereeError("");
    setRefereeErrorCode("");
    setLoadingRefereePreview(true);

    const result = await actions.previewRefereeCharges(match_id);

    setLoadingRefereePreview(false);

    if (!result.ok) {
      setRefereePreview(null);
      setRefereeErrorCode(result.code || "NETWORK_ERROR");
      setRefereeError(
        result.message ||
          errorMessages[result.code] ||
          "No se pudo calcular el reparto de arbitraje",
      );

      return;
    }

    setRefereePreview(result.data);
  };

  const handleGenerateRefereeCharges = async () => {
    if (
      !canManageMatchFinance ||
      generatingRefereeCharges ||
      !refereePreview
    ) {
      return;
    }

    if (refereePreview.existing_charges_count > 0) {
      const confirmed = window.confirm(
        "Se reemplazarán los cargos pendientes con la nueva distribución. Los cargos pagados o con recibo no serán modificados. ¿Deseas continuar?",
      );

      if (!confirmed) return;
    }

    setRefereeError("");
    setRefereeErrorCode("");
    setGeneratingRefereeCharges(true);

    const result = await actions.generateRefereeCharges(match_id);

    setGeneratingRefereeCharges(false);

    if (!result.ok) {
      setRefereeErrorCode(result.code || "NETWORK_ERROR");
      setRefereeError(
        result.message ||
          errorMessages[result.code] ||
          "No se pudieron generar los cargos de arbitraje",
      );

      return;
    }

    const previewResult = await actions.previewRefereeCharges(match_id);

    if (previewResult.ok) {
      setRefereePreview(previewResult.data);
    }
  };

  const handleSaveRefereeFee = async (amount) => {
    const result = await actions.updateMatchRefereeFee(match_id, amount);

    if (result.ok) {
      setMatch((prev) => ({
        ...prev,
        referee_fee: result.data.match.referee_fee,
      }));
      setRefereePreview(null);
      setRefereeError("");
      setRefereeErrorCode("");
    }

    return result;
  };

  const handleGoToRefereePayments = () => {
    navigate(`/payments?payment_type=referee&match_id=${match_id}`);
  };

  const handleBack = () => {
    if (typeof location.state?.from === "string" && location.state.from.startsWith("/")) {
      navigate(location.state.from);
      return;
    }

    if (location.state?.from === "clubMatches") {
      navigate("/matches");
      return;
    }

    if (location.state?.from === "teamMatches" && location.state?.teamId) {
      navigate(`/teams/${location.state.teamId}/matches`);
      return;
    }

    if (location.search) {
      navigate(`/matches${location.search}`);
      return;
    }

    if (!match?.team_id) {
      navigate("/matches");
      return;
    }

    navigate(`/teams/${match?.team_id}/matches`);
  };

  if (loading) {
    return <p>Cargando partido...</p>;
  }

  if (!match) {
    return (
      <>
        <PageHeader
          variant="detail"
          eyebrow="Partido"
          title="No pudimos cargar el partido"
          onBack={handleBack}
        />
        <Card className="page-error-state" role="alert">
          <p>
            {errorMessages[loadError?.code] ||
              loadError?.message ||
              "Ocurrió un error temporal al consultar el partido."}
          </p>
          <Button onClick={loadMatch}>Volver a intentar</Button>
        </Card>
      </>
    );
  }

  return (
    <>
      <PageHeader
        variant="detail"
        eyebrow="Partido"
        title={`vs ${match?.opponent_name || "Partido interno"}`}
        subtitle={match?.date}
        onBack={handleBack}
      />
      {!isMatchCompleted && !canOperateMatch && (
        <ReadOnlyNotice>
          Estás consultando este partido. Convocatoria, asistencia y estadísticas
          están disponibles en modo de solo lectura.
        </ReadOnlyNotice>
      )}

      {!isMatchCompleted && parentReadonly && (
        <ReadOnlyNotice>
          El torneo o la temporada vinculada ya no está activa. La información
          deportiva queda disponible en modo de solo lectura.
        </ReadOnlyNotice>
      )}

      {preflight && (
        <Card className="match-preflight mb-4" aria-labelledby="match-preflight-title">
          <div className="match-preflight-heading">
            <div>
              <h2 id="match-preflight-title">Preparación del partido</h2>
              <p>{preflight.summary.ready_count} de {preflight.summary.total_steps} pasos listos</p>
            </div>
            <span className={`status-badge ${preflight.can_finalize ? "status-success" : "status-warning"}`}>
              {preflight.can_finalize ? "Listo para finalizar" : "Preparación pendiente"}
            </span>
          </div>
          <ol className="match-preflight-list">
            {Object.keys(PREFLIGHT_LABELS).map((key) => {
              const section = preflight[key];
              const ready = key === "lineup"
                ? section?.ready && preflight.participation?.ready
                : section?.ready;
              return <li key={key} className={ready ? "is-ready" : ""}>
                <span aria-hidden="true">{ready ? "✓" : "•"}</span>
                <div><strong>{PREFLIGHT_LABELS[key]}</strong>{!ready && <small>{key === "lineup" && section?.ready ? preflight.participation?.message : section?.message}</small>}</div>
              </li>;
            })}
          </ol>
        </Card>
      )}

      {(isMatchCompleted || preflight?.stats?.ready) && (
      <>
      <Card className="mb-4">
        <div className="d-flex justify-content-between align-items-center gap-3">
          <div>
            <small className="text-muted">
              {isMatchCompleted
                ? "Resultado confirmado en sets"
                : "Resultado provisional en sets"}
            </small>

            <h2 className="mb-1">
              {homeSets} - {opponentSets}
            </h2>

            <p
              className={`match-result-status ${
                match?.result === "win"
                  ? "match-result-win"
                  : match?.result === "loss"
                  ? "match-result-loss"
                  : ""
              }`}
            >
              {isMatchCompleted
                ? `Completado · ${match?.result === "win" ? "Victoria" : "Derrota"}`
                : match?.result === "win"
                ? "Provisional · Victoria"
                : match?.result === "loss"
                ? "Provisional · Derrota"
                : "Pendiente"}
            </p>
          </div>

          {!isReadOnlyMatch && (
            <Button
              variant="primary"
              onClick={() => setShowResultEditor((prev) => !prev)}
            >
              {getResultButtonText()}
            </Button>
          )}
        </div>

      </Card>

      {showResultEditor && !isReadOnlyMatch && (
        <Card className="mb-4">
          <h3>Registrar o actualizar resultado</h3>

          <div className="d-flex justify-content-between align-items-center my-3">
            <div>
              <p className="mb-1">Tu equipo</p>
              <h2>{homeSets}</h2>
            </div>

            <div className="text-center">
              <small>SETS GANADOS</small>
              <h2>-</h2>
            </div>

            <div className="text-end">
              <p className="mb-1">{match?.opponent_name}</p>
              <h2>{opponentSets}</h2>
            </div>
          </div>

          {resultError && <p className="form-error">{resultError}</p>}
          <div className="d-flex gap-2 flex-wrap">
            <Button
              onClick={() => setHomeSets((prev) => Math.max(0, prev - 1))}
            >
              - Tu equipo
            </Button>

            <Button
              onClick={() => setHomeSets((prev) => prev + 1)}
              disabled={disableHomeIncrease}
            >
              + Tu equipo
            </Button>

            <Button
              onClick={() => setOpponentSets((prev) => Math.max(0, prev - 1))}
            >
              - Rival
            </Button>

            <Button
              onClick={() => setOpponentSets((prev) => prev + 1)}
              disabled={disableOpponentIncrease}
            >
              + Rival
            </Button>

            <Button
              variant="primary"
              onClick={saveMatchResult}
              disabled={savingResult}
            >
              {savingResult ? "Guardando..." : "Guardar resultado"}
            </Button>
          </div>
        </Card>
      )}
      </>
      )}

      {canFinalizeMatch && (
        <Card className="mb-4">
          <h3>Finalizar partido</h3>

          <p className="text-muted">
            Confirma el cierre cuando hayas revisado el marcador. Después de
            finalizar, el resultado ya no podrá modificarse desde este flujo.
          </p>

          {finalizeError && <p className="form-error">{finalizeError}</p>}

          <Button
            variant="primary"
            onClick={openFinalizeDialog}
            disabled={finalizingMatch}
          >
            {finalizingMatch ? "Finalizando..." : "Finalizar partido"}
          </Button>
        </Card>
      )}
      {showFinalizeDialog && (
        <div className="match-dialog-backdrop" role="presentation">
          <div ref={finalizeDialogRef} tabIndex="-1" className="match-dialog" role="dialog" aria-modal="true" aria-labelledby="finalize-dialog-title" aria-describedby="finalize-dialog-copy">
            <h2 id="finalize-dialog-title">Finalizar partido</h2>
            <p id="finalize-dialog-copy">
              Se confirmará el resultado {homeSets}–{opponentSets} y el partido
              quedará en modo de solo lectura.
            </p>
            {finalizeError && <p className="form-error">{finalizeError}</p>}
            <div className="match-dialog-actions">
              <Button variant="secondary" onClick={() => setShowFinalizeDialog(false)} disabled={finalizingMatch}>Cancelar</Button>
              <Button variant="primary" onClick={finalizeMatch} disabled={finalizingMatch}>{finalizingMatch ? "Finalizando..." : "Confirmar cierre"}</Button>
            </div>
          </div>
        </div>
      )}
      <Card className="mb-4">
        <h3>Estadísticas</h3>

        {!match?.capture_mode ? (
          <>
            {!isReadOnlyMatch && (
              <p className="text-muted">
                ¿Cómo registrarás el partido?
              </p>
            )}

            {isMatchCompleted ? (
              <p className="text-muted mb-0">
                Partido histórico sin modo de captura verificable. Sus datos
                permanecen disponibles en modo de solo lectura.
              </p>
            ) : isReadOnlyMatch ? (
              <p className="text-muted mb-0">
                Este partido aún no tiene modo de captura definido.
              </p>
            ) : (
              <div className="match-capture-mode-options">
                <button
                  type="button"
                  className="match-capture-mode-option"
                  disabled={savingCaptureMode}
                  onClick={() => updateCaptureMode("live")}
                >
                  <strong>En vivo</strong>
                  <span>Registrar acciones durante el partido.</span>
                </button>

                <button
                  type="button"
                  className="match-capture-mode-option"
                  disabled={savingCaptureMode}
                  onClick={() => updateCaptureMode("summary")}
                >
                  <strong>Resumen</strong>
                  <span>Cargar estadísticas manualmente después.</span>
                </button>
              </div>
            )}
          </>
        ) : (
          <>
            <div className="match-capture-mode-current">
              <div>
                <small>Modo de captura</small>
                <strong>
                  {match.capture_mode === "live" ? "En vivo" : "Resumen"}
                </strong>
              </div>

              {!isReadOnlyMatch && (
                <Button
                  variant="secondary"
                  disabled={savingCaptureMode}
                  onClick={() =>
                    updateCaptureMode(
                      match.capture_mode === "live" ? "summary" : "live",
                    )
                  }
                >
                  {match.capture_mode === "live"
                    ? "Cambiar a resumen"
                    : "Cambiar a en vivo"}
                </Button>
              )}
            </div>

            {match.capture_mode === "live" ? (
              !isReadOnlyMatch && canOpenLiveMode ? (
                <>
                  <p className="text-muted">
                    {hasInitialSix
                      ? "Continúa capturando acciones y cambios en vivo."
                      : "Primero seleccionarás las 6 iniciales."}
                  </p>
                  <Button
                    variant="primary"
                    onClick={() => navigate(`/matches/${match_id}/live${location.search}`)}
                  >
                    {hasInitialSix
                      ? "Continuar modo en vivo"
                      : "Iniciar modo en vivo"}
                  </Button>
                </>
              ) : (
                <p className="text-muted mb-0">
                  {isMatchCompleted
                    ? "El partido está finalizado. Las estadísticas provienen de LiveMatch."
                    : isReadOnlyMatch
                    ? "La captura en vivo no está disponible en modo de consulta."
                    : "Completa convocatoria y estado para iniciar el modo en vivo."}
                </p>
              )
            ) : (
              <>
                <p className="text-muted">
                  {isReadOnlyMatch
                    ? "El resumen estadístico está disponible en modo de solo lectura."
                    : "Las estadísticas se cargarán como un resumen manual."}
                </p>

                {!isReadOnlyMatch && statusSaved && (
                  <div className="match-summary-lineup">
                    <div>
                      <strong>Alineación inicial</strong>
                      <p className="text-muted mb-0">
                        Selecciona exactamente seis titulares. Quedarán marcadas
                        como participantes.
                      </p>
                    </div>
                    <span className="status-badge status-info">{selectedLineupIds.length}/6</span>
                    <div className="match-participation-options">
                      {participationEligiblePlayers.map((player) => {
                        const selected = selectedLineupIds.includes(player.match_player_id);
                        return <button type="button" key={player.match_player_id} className={`match-participation-option ${selected ? "selected" : ""}`} onClick={() => toggleLineupPlayer(player.match_player_id)} disabled={savingLineup}>
                          <span className="match-player-option-check">{selected && <Check size={16} />}</span>
                          <span><strong>#{player.player_number} {player.first_name} {player.last_name}</strong><small>{MATCH_STATUS_LABELS[player.attendance_status]}</small></span>
                        </button>;
                      })}
                    </div>
                    {lineupError && <p className="form-error mb-0">{lineupError}</p>}
                    <Button variant="secondary" onClick={saveSummaryLineup} disabled={savingLineup || selectedLineupIds.length !== 6}>
                      {savingLineup ? "Guardando..." : hasInitialSix ? "Actualizar titulares" : "Guardar titulares"}
                    </Button>
                  </div>
                )}

                {!isReadOnlyMatch && (
                  <div className="match-participation-section">
                    <Button
                      variant="secondary"
                      onClick={() => {
                        setShowParticipationEditor((current) => !current);
                        setParticipationError("");
                        setParticipationMessage("");
                      }}
                      disabled={
                        !statusSaved ||
                        statusDirty ||
                        hasUnsavedRosterChanges
                      }
                    >
                      {showParticipationEditor
                        ? "Ocultar participación"
                        : hasPlayersWhoPlayed
                        ? "Editar participación"
                        : "Registrar participación"}
                    </Button>

                    {!statusSaved && (
                      <small className="text-muted">
                        Guarda primero el estado de las convocadas.
                      </small>
                    )}

                    {showParticipationEditor && statusSaved && (
                      <div className="match-participation-editor">
                        <div>
                          <strong>Jugadoras que participaron</strong>
                          <p className="text-muted mb-0">
                            Selecciona únicamente quienes realmente jugaron.
                          </p>
                        </div>

                        {participationEligiblePlayers.length > 0 ? (
                          <div className="match-participation-options">
                            {participationEligiblePlayers.map((player) => {
                              const isSelected = selectedParticipantIds.includes(
                                player.match_player_id,
                              );

                              return (
                                <button
                                  type="button"
                                  key={player.match_player_id}
                                  className={`match-participation-option ${
                                    isSelected ? "selected" : ""
                                  }`}
                                  disabled={savingParticipation || player.is_on_court}
                                  onClick={() =>
                                    toggleParticipant(player.match_player_id)
                                  }
                                >
                                  <span className="match-player-option-check">
                                    {isSelected && <Check size={16} />}
                                  </span>

                                  <span>
                                    <strong>
                                      #{player.player_number} {player.first_name}{" "}
                                      {player.last_name}
                                    </strong>
                                    <small>
                                      {MATCH_STATUS_LABELS[
                                        player.attendance_status
                                      ]}{player.is_on_court ? " · Titular" : ""}
                                    </small>
                                  </span>
                                </button>
                              );
                            })}
                          </div>
                        ) : (
                          <p className="text-muted mb-0">
                            No hay jugadoras presentes o que hayan llegado
                            tarde.
                          </p>
                        )}

                        {participationError && (
                          <p className="form-error mb-0">
                            {participationError}
                          </p>
                        )}

                        {participationMessage && (
                          <p className="text-success mb-0">
                            {participationMessage}
                          </p>
                        )}

                        <Button
                          variant="primary"
                          onClick={saveSummaryParticipation}
                          disabled={
                            savingParticipation ||
                            participationEligiblePlayers.length === 0
                          }
                        >
                          {savingParticipation
                            ? "Guardando..."
                            : "Guardar participación"}
                        </Button>
                      </div>
                    )}
                  </div>
                )}

                {isReadOnlyMatch && (
                  <p className="text-muted">
                    Participación registrada: {" "}
                    <strong>
                      {
                        roster.filter((player) => player.did_play).length
                      }
                    </strong>
                  </p>
                )}

                <Button
                  variant="primary"
                  onClick={() => navigate(`/matches/${match_id}/stats${location.search}`)}
                  disabled={!hasPlayersWhoPlayed}
                >
                  {isReadOnlyMatch
                    ? "Consultar estadísticas"
                    : "Cargar resumen estadístico"}
                </Button>

                {statsRequired > 0 && (
                  <p className="match-stats-progress" role="status">
                    Estadísticas revisadas: <strong>{statsReviewed} de {statsRequired}</strong>
                  </p>
                )}

                {!hasPlayersWhoPlayed && !isReadOnlyMatch && (
                  <small className="text-muted d-block mt-2">
                    Podrás cargar el resumen cuando exista participación
                    registrada.
                  </small>
                )}

                {!hasPlayersWhoPlayed && isReadOnlyMatch && (
                  <small className="text-muted d-block mt-2">
                    El partido no tiene participantes con estadísticas
                    individuales para consultar.
                  </small>
                )}
              </>
            )}
          </>
        )}

        {captureModeError && (
          <p className="form-error mt-3">{captureModeError}</p>
        )}
      </Card>

      {isMatchCompleted && (
        <Card className="mb-4">
          <h3>Partido cerrado</h3>
          <p className="text-muted mb-0">
            La convocatoria, asistencia, participación y estadísticas están
            disponibles en modo de solo lectura.
          </p>
        </Card>
      )}

      {(isMatchCompleted || match?.capture_mode === "live") && (
        <Card className="mb-4">
          <h3>Historial de acciones</h3>
          {events.length === 0 ? (
            <p className="text-muted mb-0">No hay acciones registradas.</p>
          ) : (
            <ol className="match-event-history">
              {events.map((event) => (
                <li key={event.id}>
                  <strong>Set {event.set_number}</strong>
                  <span>#{event.player?.player_number} {event.player?.first_name} {event.player?.last_name}</span>
                  <span>{event.action_type} · {event.result}</span>
                </li>
              ))}
            </ol>
          )}
        </Card>
      )}

      {/* Stepper */}
      <div className="stepper-mobile mb-4">
        {STEPS.map((step, index) => {
          const isLocked = index > maxUnlockedStep;
          const isBlockedByChanges =
            index > currentStep && hasUnsavedRosterChanges;

          return (
            <Button
              key={step}
              variant={currentStep === index ? "primary" : "secondary"}
              disabled={
                isLocked || (!isReadOnlyMatch && isBlockedByChanges)
              }
              onClick={() => {
                if (
                  isLocked ||
                  (!isReadOnlyMatch && isBlockedByChanges)
                ) return;
                setCurrentStep(index);
              }}
              className={`me-2 mb-2 ${isLocked ? "opacity-50" : ""}`}
            >
              {index + 1}. {step}
            </Button>
          );
        })}
      </div>
      {currentStep === 0 && !isReadOnlyMatch && (
        <p className="mb-3">
          {callupLocked
            ? "La convocatoria está bloqueada porque ya existe información deportiva."
            : "Selecciona las jugadoras convocadas para este partido y guarda para continuar."}
        </p>
      )}
      {currentStep === 0 && rosterError && (
        <p className="form-error">{rosterError}</p>
      )}

      {currentStep === 0 && hasUnsavedRosterChanges && (
        <p className="text-warning mb-3">
          ⚠️ Tienes cambios sin guardar en la convocatoria
        </p>
      )}
      {currentStep === 1 && statusError && (
        <p className="form-error">{statusError}</p>
      )}
      {currentStep === 1 && !isReadOnlyMatch && (
        <div className="match-attendance-toolbar">
          <span>{attendanceRecorded} de {attendanceRequired} registradas</span>
          <Button type="button" variant="secondary" onClick={markAllCalledPresent}>
            Marcar todas presentes
          </Button>
        </div>
      )}
      {/* Players list */}
      {teamPlayers.length === 0 ? (
        <Card className="mb-4">
          <p className="text-muted mb-0">
            Este partido no tiene convocatoria registrada.
          </p>
        </Card>
      ) : currentStep === 0 ? (
        <div className="match-player-selection-list">
          {teamPlayers.map((player) => {
            const isSelected = selectedPlayers.includes(player.player_id);

            return (
              <button
                type="button"
                key={player.player_id}
                className={`match-player-option ${
                  isSelected ? "selected" : ""
                }`}
                disabled={isReadOnlyMatch || callupLocked}
                onClick={() => togglePlayerSelection(player)}
              >
                <div className="match-player-option-check">
                  {isSelected && <Check size={16} />}
                </div>

                <div className="match-player-option-copy">
                  <strong>
                    #{player.player_number} {player.first_name}{" "}
                    {player.last_name}
                  </strong>

                  <span>
                    {POSITION_LABELS[player.position || player.main_position] ||
                      "Sin posición definida"}
                  </span>
                </div>

                <span className="match-player-option-state">
                  {isSelected
                    ? "Convocada"
                    : isReadOnlyMatch
                    ? "No convocada"
                    : "Convocar"}
                </span>
              </button>
            );
          })}
        </div>
      ) : (
        <div className="match-player-status-list">
          {filteredPlayers.map((player) => (
            <Card
              key={player.match_player_id}
              className="mb-3"
            >
              <h3>
                #{player.player_number} {player.first_name} {player.last_name}
              </h3>

              {PLAYABLE_STATUSES.includes(player.attendance_status) &&
              !isReadOnlyMatch ? (
                <FormField label="Posición hoy">
                  <Select
                    value={player.position || ""}
                    onClick={(event) => event.stopPropagation()}
                    onChange={(event) => {
                      event.stopPropagation();

                      updatePlayerPosition(
                        player.match_player_id,
                        event.target.value,
                      );
                    }}
                  >
                    <option value="">Sin definir</option>

                    {POSITION_OPTIONS.map((position) => (
                      <option key={position.value} value={position.value}>
                        {position.label}
                      </option>
                    ))}
                  </Select>
                </FormField>
              ) : (
                <p className="text-muted mb-1">
                  Posición:{" "}
                  {POSITION_LABELS[player.position || player.main_position] ||
                    "Sin definir"}
                </p>
              )}

              {isReadOnlyMatch ? (
                <p className="mb-1">Estado: {MATCH_STATUS_LABELS[player.attendance_status] || "Sin estado"}</p>
              ) : (
                <div className="match-attendance-options" role="group" aria-label={`Asistencia de ${player.first_name} ${player.last_name}`}>
                  {MATCH_STATES.map((status) => (
                    <button type="button" key={status} className={player.attendance_status === status ? "is-selected" : ""} aria-pressed={player.attendance_status === status} onClick={() => setMatchStatus(player.match_player_id, status)}>
                      {MATCH_STATUS_LABELS[status]}
                    </button>
                  ))}
                </div>
              )}
            </Card>
          ))}
        </div>
      )}
      {/* Footer CTA */}
      {!isReadOnlyMatch && (
        <div className="mt-4 mb-4 d-flex gap-2">
        {currentStep === 0 ? (
          <Button
            variant="primary"
            onClick={saveStepOne}
            disabled={savingRoster || !hasUnsavedRosterChanges || callupLocked}
          >
            {savingRoster ? "Guardando..." : "Guardar convocadas"}
          </Button>
        ) : currentStep === 1 ? (
          statusSaved && !statusDirty ? (
            <div className="match-status-saved">
              <div className="match-status-saved-icon">✓</div>

              <div className="match-status-saved-content">
                <strong>Estado guardado</strong>
                <span>La preparación del partido está lista.</span>
              </div>
            </div>
          ) : (
            <Button
              variant="primary"
              onClick={saveStepTwo}
              disabled={savingStatus}
            >
              {savingStatus
                ? "Guardando..."
                : statusSaved
                ? "Guardar cambios"
                : "Guardar estado"}
            </Button>
          )
        ) : null}
        </div>
      )}

      {canManageMatchFinance && (
        <Card className="mb-4">
          <FeeEditor
            label="Costo de arbitraje"
            value={match?.referee_fee}
            currencyCode={match?.currency_code}
            helper="Los cargos pendientes no cambian solos: revisa la distribución y actualízala después de guardar."
            onSave={handleSaveRefereeFee}
          />
        </Card>
      )}

      {canManageMatchFinance && (calledPlayersCount === 0 ? (
        <Card className="match-referee-locked-card mb-4">
          <div className="match-referee-locked-icon">
            <DollarSign size={19} />
          </div>

          <div>
            <strong>Arbitraje</strong>

            <span>Disponible después de guardar la convocatoria.</span>
          </div>
        </Card>
      ) : (
        <Card className="match-referee-card mb-4">
          <div className="match-referee-flow-title">
            <span className="match-referee-step">3</span>

            <div>
              <h3>Costo de arbitraje</h3>

              <p>
                Revisa cómo se distribuirá el costo entre las deportistas
                convocadas.
              </p>
            </div>
          </div>

          <div className="match-referee-heading">
            <div className="match-referee-title-row">
              <div className="match-referee-icon">
                <DollarSign size={18} />
              </div>

              <div>
                <h4>Distribución del arbitraje</h4>

                <p>
                  El partido calcula los cargos. Los pagos y recibos se
                  administran después desde Pagos.
                </p>
              </div>
            </div>

            {refereeFeeConfigured && refereeFee > 0 && (
              <strong className="match-referee-total">
                {formatMoney(refereeFee, match.currency_code)}
              </strong>
            )}
          </div>

          <div className="match-referee-rule">
            <Users size={17} />

            <span>
              El costo se divide entre todas las deportistas convocadas,
              independientemente de su asistencia o participación.
            </span>
          </div>

          {!refereeFeeConfigured && (
            <div className="match-referee-alert">
              <AlertCircle size={18} />

              <p>Este partido no tiene un costo de arbitraje configurado.</p>
            </div>
          )}

          {refereeFeeConfigured && refereeFee <= 0 && (
            <div className="match-referee-alert">
              <AlertCircle size={18} />

              <p>El costo de arbitraje está configurado en cero.</p>
            </div>
          )}

          {hasUnsavedRosterChanges && (
            <div className="match-referee-alert">
              <AlertCircle size={18} />

              <p>
                Guarda los cambios de la convocatoria antes de calcular el
                reparto.
              </p>
            </div>
          )}

          {!refereePreview && (
            <div className="match-referee-actions">
              <Button
                type="button"
                variant="secondary"
                onClick={loadRefereePreview}
                disabled={loadingRefereePreview || !canPreviewRefereeCharges}
              >
                {loadingRefereePreview
                  ? "Calculando..."
                  : "Revisar distribución"}
              </Button>
            </div>
          )}

          {refereeError && (
            <div
              className={`match-referee-alert ${
                refereeErrorCode === "REFEREE_CHARGES_LOCKED" ? "danger" : ""
              }`}
            >
              <AlertCircle size={18} />
              <p>{refereeError}</p>
            </div>
          )}

          {refereePreview && (
            <>
              {hasGeneratedRefereeCharges && (
                <div className="match-referee-success">
                  <div className="match-referee-success-icon">
                    <CircleCheck size={20} />
                  </div>

                  <div>
                    <strong>
                      {existingRefereeChargesCount}{" "}
                      {existingRefereeChargesCount === 1
                        ? "cargo creado"
                        : "cargos creados"}
                    </strong>

                    <span>
                      Registra los pagos y genera los recibos desde Pagos.
                    </span>
                  </div>
                </div>
              )}

              <div className="match-referee-summary">
                <div>
                  <DollarSign size={18} />
                  <span>Costo total</span>
                  <strong>
                    {formatMoney(
                      refereePreview.referee_fee,
                      refereePreview.currency_code || match.currency_code,
                    )}
                  </strong>
                </div>

                <div>
                  <Users size={18} />
                  <span>Convocadas</span>
                  <strong>{refereePreview.called_players_count}</strong>
                </div>

                <div>
                  <ReceiptText size={18} />
                  <span>Cargos existentes</span>
                  <strong>{refereePreview.existing_charges_count}</strong>
                </div>
              </div>

              {refereePreview.has_paid_charges && (
                <div className="match-referee-alert danger">
                  <AlertCircle size={18} />

                  <p>
                    Ya existen cargos pagados o con recibo. La distribución no
                    puede modificarse.
                  </p>
                </div>
              )}

              <div className="match-referee-list">
                {refereePreview.players?.map((row) => {
                  const paymentStatus = row.existing_charge
                    ? getPaymentStatusData(row.existing_charge.status)
                    : null;

                  return (
                    <div key={row.player_id} className="match-referee-row">
                      <div className="match-referee-player">
                        <strong>
                          #{row.player_number} {row.player?.first_name}{" "}
                          {row.player?.last_name}
                        </strong>

                        <span>
                          {row.existing_charge ? "Cargo creado" : "Sin cargo"}
                        </span>
                      </div>

                      <div className="match-referee-row-side">
                        {paymentStatus && (
                          <span
                            className={`status-badge ${paymentStatus.className}`}
                          >
                            {paymentStatus.label}
                          </span>
                        )}

                        <strong>
                          {formatMoney(
                            row.amount,
                            refereePreview.currency_code || match.currency_code,
                          )}
                        </strong>
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="match-referee-actions">
                <button
                  type="button"
                  className="match-referee-recalculate"
                  onClick={loadRefereePreview}
                  disabled={loadingRefereePreview}
                >
                  {loadingRefereePreview
                    ? "Calculando..."
                    : "Recalcular distribución"}
                </button>

                <Button
                  type="button"
                  variant={hasGeneratedRefereeCharges ? "secondary" : "primary"}
                  onClick={handleGenerateRefereeCharges}
                  disabled={
                    generatingRefereeCharges || !refereePreview.can_generate
                  }
                >
                  {generatingRefereeCharges
                    ? "Procesando..."
                    : hasGeneratedRefereeCharges
                    ? "Actualizar distribución"
                    : "Generar cargos"}
                </Button>

                {hasGeneratedRefereeCharges && (
                  <Button type="button" onClick={handleGoToRefereePayments}>
                    Ver cargos en Pagos
                    <ArrowRight size={17} />
                  </Button>
                )}
              </div>
            </>
          )}
        </Card>
      ))}
    </>
  );
};
