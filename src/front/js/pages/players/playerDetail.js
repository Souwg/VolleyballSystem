import React, { useEffect, useContext, useRef, useState } from "react";
import { Link, useParams, useNavigate, useLocation } from "react-router-dom";
import { Context } from "../../store/appContext";
import {
  AssignedBadge,
  ReadOnlyNotice,
} from "../../component/ui/readOnlyNotice";
import {
  canManage,
  hasField,
  isScopedCoach,
  useTeamAccessLost,
} from "../../utils/coachAccess";
import "../../../styles/playerDetails.css";
import { Card } from "../../component/ui/card";
import { Button } from "../../component/ui/button";
import { Input } from "../../component/ui/input";
import { getAssetUrl } from "../../utils/getAssetUrl";
import { errorMessages } from "../../utils/errorMessages";
import { formatMoney } from "../../utils/money";
import { useToast } from "../../../../context/toastContext";
import { Pencil } from "lucide-react";
import {
  SeasonSelector,
  useSeasonSelection,
} from "../../component/seasonSelector";

const POSITION_LABELS = {
  setter: "Armador",
  outside: "Punta",
  middle: "Central",
  opposite: "Opuesto",
  libero: "Líbero",
};

const MATCH_TYPE_LABELS = {
  official: "Oficial",
  friendly: "Amistoso",
  scrimmage: "Scrimmage",
};

const MATCH_RESULT_LABELS = {
  win: "Victoria",
  loss: "Derrota",
};

const PERFORMANCE_RATE_METRICS = [
  {
    key: "attack_efficiency",
    label: "Eficiencia de ataque",
    help: "(ataques positivos − errores de ataque) / ataques totales",
  },
  { key: "attack_positive_rate", label: "Positividad de ataque" },
  { key: "reception_positive_rate", label: "Positividad de recepción" },
  { key: "defense_positive_rate", label: "Positividad de defensa" },
  { key: "set_positive_rate", label: "Positividad de armado" },
  { key: "serve_ace_rate", label: "Tasa de ace" },
  { key: "block_point_rate", label: "Tasa de bloqueo punto" },
];

const PERFORMANCE_FUNDAMENTALS = [
  {
    label: "Ataque",
    total: "attacks_total",
    primary: "attacks_positive",
    primaryLabel: "Positivos",
    secondary: "attacks_neutral",
    secondaryLabel: "Neutrales",
    negative: "attacks_errors",
    negativeLabel: "Errores",
    rate: "attack_positive_rate",
  },
  {
    label: "Recepción",
    total: "receptions_total",
    primary: "receptions_positive",
    primaryLabel: "Positivas",
    secondary: "receptions_neutral",
    secondaryLabel: "Neutrales",
    negative: "receptions_negative",
    negativeLabel: "Negativas",
    rate: "reception_positive_rate",
  },
  {
    label: "Defensa",
    total: "defenses_total",
    primary: "defenses_positive",
    primaryLabel: "Positivas",
    secondary: "defenses_neutral",
    secondaryLabel: "Neutrales",
    negative: "defenses_negative",
    negativeLabel: "Negativas",
    rate: "defense_positive_rate",
  },
  {
    label: "Armado",
    total: "sets_total",
    primary: "sets_positive",
    primaryLabel: "Positivos",
    secondary: "sets_neutral",
    secondaryLabel: "Neutrales",
    negative: "sets_errors",
    negativeLabel: "Errores",
    rate: "set_positive_rate",
  },
  {
    label: "Saque",
    total: "serves_total",
    primary: "serves_aces",
    primaryLabel: "Aces",
    secondary: "serves_in",
    secondaryLabel: "En juego",
    negative: "serves_errors",
    negativeLabel: "Errores",
    rate: "serve_ace_rate",
  },
  {
    label: "Bloqueo",
    total: "blocks_total",
    primary: "blocks_points",
    primaryLabel: "Puntos",
    secondary: "blocks_neutral",
    secondaryLabel: "Neutrales",
    negative: "blocks_errors",
    negativeLabel: "Errores",
    rate: "block_point_rate",
  },
];

const PAYMENT_STATUS_LABELS = {
  pending: "Pendiente",
  paid: "Pagado",
  overdue: "Atrasado",
  cancelled: "Cancelado",
};

const PAYMENT_STATUS_CLASSES = {
  pending: "status-badge status-warning",
  paid: "status-badge status-success",
  overdue: "status-badge status-danger",
  cancelled: "status-badge status-muted",
};

const PAYMENT_TYPE_LABELS = {
  enrollment: "Inscripción",
  monthly: "Mensualidad",
  uniform: "Uniforme",
  tournament: "Torneo",
  extra: "Extra",
};

const formatDate = (date) => {
  if (!date) return null;

  return new Date(`${date}T00:00:00`).toLocaleDateString("es-ES", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
};

const formatMembershipDate = (value) =>
  value
    ? new Date(value).toLocaleDateString("es-ES", {
        day: "2-digit",
        month: "short",
        year: "numeric",
      })
    : null;

const getPerformanceErrorMessage = (error) => {
  if (error?.code === "PLAYER_PERFORMANCE_NOT_SUPPORTED") {
    return "Rendimiento no disponible para este deporte.";
  }

  if (error?.code === "SEASON_NOT_FOUND") {
    return "La temporada seleccionada ya no está disponible.";
  }

  if (error?.code === "PLAYER_NOT_FOUND") {
    return "El perfil de esta deportista ya no está disponible.";
  }

  if (error?.code === "FORBIDDEN") {
    return "No tienes permisos para consultar este rendimiento.";
  }

  if (error?.code === "NETWORK_ERROR") {
    return "No pudimos cargar el rendimiento por un problema de conexión.";
  }

  return error?.message || "No se pudo cargar el rendimiento.";
};

const PerformanceMatchItem = ({ match, provisional = false }) => {
  const typeLabel = MATCH_TYPE_LABELS[match.match_type] || match.match_type;
  const resultLabel = MATCH_RESULT_LABELS[match.result] || match.result;
  const positionLabel = POSITION_LABELS[match.position] || match.position;
  const hasScore =
    Number.isInteger(match.home_sets) && Number.isInteger(match.opponent_sets);

  return (
    <li className="player-match-row">
      <article>
        <div className="player-match-row-header">
          <div className="player-match-row-info">
            <strong>vs. {match.opponent_name || "Rival"}</strong>
            <span>
              {formatDate(match.date)}
              {match.team?.name ? ` · ${match.team.name}` : ""}
            </span>
          </div>
          <div className="player-match-badges">
            {typeLabel && (
              <span className="status-badge status-info">{typeLabel}</span>
            )}
            {provisional && (
              <span className="status-badge status-warning">Provisional</span>
            )}
          </div>
        </div>

        <div className="player-match-context">
          {!provisional && (resultLabel || hasScore) && (
            <span>
              {resultLabel || "Resultado"}
              {hasScore ? ` · ${match.home_sets}–${match.opponent_sets}` : ""}
            </span>
          )}
          {match.player_number !== null && match.player_number !== undefined && (
            <span>Dorsal #{match.player_number}</span>
          )}
          {positionLabel && <span>Posición: {positionLabel}</span>}
          <span>
            {match.points_total} puntos · {match.errors_total} errores contabilizados
          </span>
        </div>
      </article>
    </li>
  );
};

const MEMBERSHIP_STATUS_LABELS = {
  active: "Disponible para este equipo",
  injured: "Lesionado/a",
  inactive: "No disponible para este equipo",
};

const getPaymentDescription = (payment) => {
  if (payment.payment_type === "monthly") {
    return `${formatDate(payment.period_start)} - ${formatDate(
      payment.period_end,
    )}`;
  }

  if (payment.payment_type === "enrollment") {
    return "Pago único de inscripción";
  }

  return payment.notes || "Pago del deportista";
};

const getPaymentMetaText = (payment) => {
  if (payment.status === "paid") {
    const paidText = payment.payment_date
      ? `Pagado el ${formatDate(payment.payment_date)}`
      : "Pagado";

    const dueText = payment.due_date
      ? `Debía pagarse el ${formatDate(payment.due_date)}`
      : null;

    return dueText ? `${paidText} · ${dueText}` : paidText;
  }

  if (payment.status === "overdue" && payment.due_date) {
    return `Atrasado · Debía pagarse el ${formatDate(payment.due_date)}`;
  }

  if (payment.status === "pending" && payment.due_date) {
    return `Pendiente · Pago esperado el ${formatDate(payment.due_date)}`;
  }

  if (payment.status === "cancelled") {
    return "Pago cancelado";
  }

  return null;
};
export const PlayerDetail = () => {
  const { store, actions } = useContext(Context);
  const { player_id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { showToast } = useToast();

  const [player, setPlayer] = useState(null);
  const [summary, setSummary] = useState(null);
  const [history, setHistory] = useState([]);
  const [attendanceSummary, setAttendanceSummary] = useState(null);
  const [trainingHistory, setTrainingHistory] = useState([]);

  const [performance, setPerformance] = useState(null);
  const [officialPerformanceMatches, setOfficialPerformanceMatches] =
    useState([]);
  const [provisionalPerformanceMatches, setProvisionalPerformanceMatches] =
    useState([]);
  const [performanceLoading, setPerformanceLoading] = useState(true);
  const [performanceError, setPerformanceError] = useState(null);
  const [payments, setPayments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadedPlayerId, setLoadedPlayerId] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [editingRepresentative, setEditingRepresentative] = useState(false);
  const [savingRepresentative, setSavingRepresentative] = useState(false);
  const [playerAction, setPlayerAction] = useState(null);
  const [representativeForm, setRepresentativeForm] = useState({
    representative_name: "",
    representative_phone: "",
  });
  const [activeTab, setActiveTab] = useState("profile");
  const playerRequestRef = useRef(0);
  const performanceRequestRef = useRef(0);
  const currentPlayerIdRef = useRef(player_id);
  const currentSeasonIdRef = useRef(null);
  const {
    loadingSeasons,
    reloadSeasons,
    requestedSeasonId,
    seasonId,
    seasonError,
    seasons,
    selectedSeason,
    selectSeason,
  } = useSeasonSelection({ defaultToActive: false });
  currentPlayerIdRef.current = player_id;
  currentSeasonIdRef.current = seasonId;
  const canManagePayments = ["club_owner", "staff"].includes(
    store.user?.role,
  );
  const canViewSports = ["club_owner", "coach"].includes(store.user?.role);
  const canViewPerformance = ["club_owner", "coach", "staff"].includes(
    store.user?.role,
  );
  const canEditPlayer = player?.can_edit_profile === true;
  const canEditMainPosition = player?.can_edit_main_position === true;
  const canRemoveFromTeam = (team) =>
    ["club_owner", "coach"].includes(store.user?.role) &&
    canManage(team) &&
    (store.user?.role === "club_owner" || team.season_status === "active");
  const showAssignment = isScopedCoach(store);
  const canManagePlayerStatus = store.user?.role === "club_owner";
  const canDeletePlayer = player?.can_delete === true;

  useTeamAccessLost(() => loadPlayerData());

  const handleBack = () => {
    if (location.state?.from) {
      navigate(location.state.from);
      return;
    }

    navigate("/players");
  };

  const handleTabKeyDown = (event) => {
    if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return;

    const tabs = Array.from(
      event.currentTarget.parentElement.querySelectorAll('[role="tab"]'),
    );
    const currentIndex = tabs.indexOf(event.currentTarget);

    if (currentIndex < 0) return;

    event.preventDefault();
    const direction = event.key === "ArrowRight" ? 1 : -1;
    const nextIndex = (currentIndex + direction + tabs.length) % tabs.length;
    tabs[nextIndex].focus();
    tabs[nextIndex].click();
  };

  const loadPlayerData = async () => {
    const requestId = ++playerRequestRef.current;
    const requestedPlayerId = player_id;

    setLoading(true);
    setLoadError(null);

    const [detailResult, attendanceResult, paymentsResult] = await Promise.all([
      actions.getPlayerDetail(requestedPlayerId),
      canViewSports ? actions.getPlayerAttendance(requestedPlayerId) : null,
      canManagePayments ? actions.getPlayerPayments(requestedPlayerId) : null,
    ]);

    if (
      requestId !== playerRequestRef.current ||
      requestedPlayerId !== currentPlayerIdRef.current
    ) {
      return;
    }

    if (!detailResult.ok) {
      setPlayer(null);
      setLoadedPlayerId(requestedPlayerId);
      setLoadError(detailResult.code || "HTTP_ERROR");
      setLoading(false);
      return;
    }

    const loadedPlayer = detailResult.data.player;
    setPlayer(loadedPlayer);
    setLoadedPlayerId(requestedPlayerId);
    setRepresentativeForm({
      representative_name: loadedPlayer.representative_name || "",
      representative_phone: loadedPlayer.representative_phone || "",
    });

    if (attendanceResult?.ok) {
      const data = attendanceResult.data;
      setAttendanceSummary(data.summary);
      setTrainingHistory(data.history || []);
    }

    if (paymentsResult?.ok) {
      setPayments(paymentsResult.data.payments || []);
      setPlayer((current) => ({
        ...current,
        enrollment_date: paymentsResult.data.player?.enrollment_date || null,
      }));
    }

    setLoading(false);
  };

  const loadPlayerPerformance = async () => {
    if (!canViewPerformance) return;

    const requestId = ++performanceRequestRef.current;
    const requestedPlayerId = player_id;
    const requestedSeasonId = seasonId;

    setPerformanceLoading(true);
    setPerformanceError(null);
    setPerformance(null);
    setOfficialPerformanceMatches([]);
    setProvisionalPerformanceMatches([]);

    const result = await actions.getPlayerPerformance(requestedPlayerId, {
      seasonId: requestedSeasonId,
    });

    if (
      requestId !== performanceRequestRef.current ||
      requestedPlayerId !== currentPlayerIdRef.current ||
      requestedSeasonId !== currentSeasonIdRef.current
    ) {
      return;
    }

    if (result.ok) {
      setPerformance(result.data);
      setOfficialPerformanceMatches(result.data.official_matches || []);
      setProvisionalPerformanceMatches(result.data.provisional_matches || []);
    } else {
      setPerformanceError({
        code: result.code || "HTTP_ERROR",
        message: result.message,
        status: result.status,
      });
    }

    setPerformanceLoading(false);
  };

  useEffect(() => {
    setPlayer(null);
    setAttendanceSummary(null);
    setTrainingHistory([]);
    setPayments([]);
    loadPlayerData();

    return () => {
      playerRequestRef.current += 1;
    };
  }, [player_id]);

  useEffect(() => {
    setPerformance(null);
    setPerformanceError(null);
    setOfficialPerformanceMatches([]);
    setProvisionalPerformanceMatches([]);

    if (canViewPerformance) {
      loadPlayerPerformance();
    } else {
      setPerformanceLoading(false);
    }

    return () => {
      performanceRequestRef.current += 1;
    };
  }, [player_id, seasonId, canViewPerformance]);

  const handleRepresentativeChange = (event) => {
    const { name, value } = event.target;

    setRepresentativeForm((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleCancelRepresentativeEdit = () => {
    setRepresentativeForm({
      representative_name: player.representative_name || "",
      representative_phone: player.representative_phone || "",
    });

    setEditingRepresentative(false);
  };

  const handleSaveRepresentative = async () => {
    if (savingRepresentative) return;

    setSavingRepresentative(true);

    const result = await actions.updatePlayer(player_id, {
      first_name: player.first_name,
      last_name: player.last_name,
      sex: player.sex,
      birth_date: player.birth_date || null,
      main_position: player.main_position || null,
      representative_name:
        representativeForm.representative_name.trim() || null,
      representative_phone:
        representativeForm.representative_phone.trim() || null,
    });

    if (result.ok) {
      await loadPlayerData();
      setEditingRepresentative(false);
    }

    setSavingRepresentative(false);
  };

  const handleActiveChange = async () => {
    if (playerAction) return;

    const nextIsActive = !player.is_active;
    const confirmed = window.confirm(
      nextIsActive
        ? "¿Reactivar a este deportista?\n\nRecuperará la elegibilidad global. Su disponibilidad seguirá dependiendo del estado de cada equipo, pertenencia y temporada."
        : "¿Inactivar a este deportista?\n\nNo podrá participar en nuevas operaciones deportivas y se detendrán nuevas mensualidades automáticas. Su perfil, histórico y pertenencias a equipos se conservarán.",
    );

    if (!confirmed) return;

    setPlayerAction("status");

    try {
      const result = await actions.updatePlayerActiveStatus(
        player.id,
        nextIsActive,
      );

      if (result.ok) {
        setPlayer((current) => ({
          ...current,
          is_active: nextIsActive,
        }));
      }
    } finally {
      setPlayerAction(null);
    }
  };

  const handleRemoveFromTeam = async (team) => {
    if (playerAction) return;

    const confirmed = window.confirm(
      `¿Quitar a este deportista del equipo?\n\nSe cerrará esta pertenencia. Su perfil y su histórico se conservarán, y sus otros equipos no cambiarán.`,
    );

    if (!confirmed) return;

    setPlayerAction(`team-${team.team_id}`);

    try {
      const result = await actions.removePlayerFromTeam(team.team_id, player.id);

      if (result.ok) {
        setPlayer((current) => ({
          ...current,
          current_memberships: (current.current_memberships || []).filter(
            (item) => item.team_id !== team.team_id,
          ),
          historical_memberships: [
            { ...team, left_at: new Date().toISOString() },
            ...(current.historical_memberships || []),
          ],
        }));
      }
    } finally {
      setPlayerAction(null);
    }
  };

  const handleDeletePlayer = async () => {
    if (playerAction || !canDeletePlayer) return;

    const confirmed = window.confirm(
      "¿Eliminar este perfil del club?\n\nEsta acción es excepcional y solo está disponible porque el perfil no tiene pertenencias ni historial deportivo o financiero.",
    );

    if (!confirmed) return;

    setPlayerAction("delete");

    try {
      const result = await actions.deletePlayer(player.id);

      if (!result.ok) {
        showToast(
          errorMessages[result.code] || result.message ||
            "No se pudo eliminar la jugadora del club",
          "error",
        );
        return;
      }

      navigate("/players", { replace: true });
    } finally {
      setPlayerAction(null);
    }
  };

  const hasFinalizedPerformance = officialPerformanceMatches.length > 0;
  const hasProvisionalPerformance = provisionalPerformanceMatches.length > 0;
  const hasAnyPerformance =
    hasFinalizedPerformance || hasProvisionalPerformance;
  const performanceTeamCount = new Set(
    [...officialPerformanceMatches, ...provisionalPerformanceMatches]
      .map((match) => match.team?.id)
      .filter(Boolean),
  ).size;
  const performancePeriodLabel = selectedSeason?.name ||
    (seasonId ? "Temporada no disponible" : "Todas las temporadas");
  const performanceEmptyMessage = selectedSeason?.status === "planned"
    ? "Aún no hay rendimiento registrado para esta temporada."
    : "Aún no hay partidos registrados para este período.";

  if (loading || loadedPlayerId !== player_id) {
    return <p role="status">Cargando perfil...</p>;
  }

  if (!player) {
    return (
      <Card className="page-error-state" role="alert">
        <p>
          {loadError === "PLAYER_NOT_FOUND"
            ? "Deportista no encontrado."
            : loadError === "FORBIDDEN"
            ? "No tienes permisos para consultar este deportista."
            : "No se pudo cargar el perfil del deportista."}
        </p>
        {loadError !== "PLAYER_NOT_FOUND" && (
          <Button type="button" variant="secondary" onClick={loadPlayerData}>
            Volver a intentar
          </Button>
        )}
      </Card>
    );
  }

  return (
    <div className="player-detail-page">
      <section className="player-profile-hero">
        <button
          type="button"
          className="player-profile-back"
          onClick={handleBack}
        >
          ← Volver
        </button>

        <div className="player-profile-main">
          <div className="player-profile-photo">
            {player.image_url ? (
              <img
                src={getAssetUrl(player.image_url)}
                alt={`${player.first_name} ${player.last_name}`}
              />
            ) : (
              <span>
                {`${player.first_name} ${player.last_name}`
                  .split(" ")
                  .filter(Boolean)
                  .slice(0, 2)
                  .map((word) => word.charAt(0))
                  .join("")
                  .toUpperCase()}
              </span>
            )}
          </div>

          <div className="player-profile-info">
            <span className="player-profile-eyebrow">Perfil de deportista</span>

            <h1>
              {player.first_name} {player.last_name}
            </h1>

            <span
              className={`status-badge player-global-status ${
                player.is_active ? "status-success" : "status-muted"
              }`}
            >
              {player.is_active ? "Activo en el club" : "Inactivo en el club"}
            </span>

            <p>
              {player.current_memberships?.length > 0
                ? player.current_memberships
                    .map(
                      (team) =>
                        `${team.category_name || "Sin categoría"} · ${
                          team.team_name
                        } · #${team.player_number}`,
                    )
                    .join(" • ")
                : "Sin equipo actual"}
            </p>
          </div>
        </div>

        {(canEditPlayer || canEditMainPosition) && (
          <div className="player-profile-actions">
            <Button
              variant="secondary"
              onClick={() => navigate(`/players/${player_id}/edit`)}
            >
              {canEditPlayer ? "Editar perfil" : "Editar posición"}
            </Button>
          </div>
        )}
      </section>

      {player.read_only && (
        <ReadOnlyNotice>
          Solo lectura. Puedes consultar el perfil, la trayectoria y la información administrativa permitida.
        </ReadOnlyNotice>
      )}

      <div className="player-tabs" role="tablist" aria-label="Secciones del deportista">
        <button
          type="button"
          role="tab"
          id="player-tab-profile"
          aria-controls="player-panel-profile"
          aria-selected={activeTab === "profile"}
          tabIndex={activeTab === "profile" ? 0 : -1}
          className={`player-tab ${activeTab === "profile" ? "active" : ""}`}
          onClick={() => setActiveTab("profile")}
          onKeyDown={handleTabKeyDown}
        >
          Perfil
        </button>

        {canViewPerformance && (
          <button
            type="button"
            role="tab"
            id="player-tab-performance"
            aria-controls="player-panel-performance"
            aria-selected={activeTab === "performance"}
            tabIndex={activeTab === "performance" ? 0 : -1}
            className={`player-tab ${
              activeTab === "performance" ? "active" : ""
            }`}
            onClick={() => setActiveTab("performance")}
            onKeyDown={handleTabKeyDown}
          >
            Rendimiento
          </button>
        )}

        {canManagePayments && (
          <button
            type="button"
            role="tab"
            id="player-tab-payments"
            aria-controls="player-panel-payments"
            aria-selected={activeTab === "payments"}
            tabIndex={activeTab === "payments" ? 0 : -1}
            className={`player-tab ${
              activeTab === "payments" ? "active" : ""
            }`}
            onClick={() => setActiveTab("payments")}
            onKeyDown={handleTabKeyDown}
          >
            Pagos
          </button>
        )}
      </div>

      {activeTab === "profile" && (
        <div role="tabpanel" id="player-panel-profile" aria-labelledby="player-tab-profile">
          <Card className="player-info-card player-global-status-card">
            <div className="player-section-header">
              <div>
                <span className="player-card-label">Perfil global</span>
                <h3>Estado en el club</h3>
              </div>

              <span
                className={`status-badge ${
                  player.is_active ? "status-success" : "status-muted"
                }`}
              >
                {player.is_active ? "Activo en el club" : "Inactivo en el club"}
              </span>
            </div>

            {canManagePlayerStatus && (
              <div className="player-global-actions">
                <Button
                  type="button"
                  variant={player.is_active ? "secondary" : "primary"}
                  disabled={playerAction !== null}
                  onClick={handleActiveChange}
                >
                  {playerAction === "status"
                    ? player.is_active
                      ? "Inactivando deportista..."
                      : "Reactivando deportista..."
                    : player.is_active
                    ? "Inactivar deportista"
                    : "Reactivar deportista"}
                </Button>
              </div>
            )}
          </Card>

          <Card className="player-teams-card">
            <div className="player-section-header">
              <div>
                <span className="player-card-label">Equipos</span>
                <h3>Equipos actuales</h3>
              </div>

              <span className="player-teams-count">
                {player.current_memberships?.length || 0}
              </span>
            </div>

            {player.current_memberships?.length > 0 ? (
              <div className="player-teams-list">
                {player.current_memberships.map((team) => (
                  <div key={team.membership_id} className="player-team-row">
                    <div className="player-team-row-info">
                      <strong>{team.category_name || "Sin categoría"}</strong>
                      <span>
                        {team.team_name} · {team.season_name || "Sin temporada"} · Dorsal #{team.player_number}
                        {team.season_status === "planned" ? " · Planificada" : ""}
                        {team.team_status === "archived" ? " · Equipo archivado" : ""}
                      </span>
                      <Link to={`/teams/${team.team_id}?season=${team.season_id}`}>
                        Ver equipo
                      </Link>
                    </div>

                    <div className="player-team-row-actions">
                      {showAssignment && team.is_assigned && <AssignedBadge />}

                      <span className="player-membership-label">
                        Disponibilidad en el equipo
                      </span>
                      <span
                        className={`status-badge ${
                          team.status === "active"
                            ? "status-success"
                            : team.status === "injured"
                            ? "status-warning"
                            : "status-muted"
                        }`}
                      >
                        {MEMBERSHIP_STATUS_LABELS[team.status] || team.status}
                      </span>

                      {canRemoveFromTeam(team) && (
                        <Button
                          type="button"
                          variant="secondary"
                          disabled={playerAction !== null}
                          onClick={() => handleRemoveFromTeam(team)}
                        >
                          {playerAction === `team-${team.team_id}`
                            ? "Quitando..."
                            : "Quitar del equipo"}
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="player-empty-membership">
                <p className="player-empty-text">
                  Este deportista aún no pertenece a un equipo actual.
                </p>
                {store.user?.role === "club_owner" && (
                  <Button type="button" variant="secondary" onClick={() => navigate("/players")}>Agregar a un equipo</Button>
                )}
              </div>
            )}
          </Card>

          {/* 🔥 PERFIL GENERAL */}
          <Card className="player-info-card">
            <h3>Perfil general</h3>

            <div className="player-info-list">
              <div className="player-info-row">
                <span>Sexo</span>
                <strong>
                  {player.sex === "female" ? "Femenino" : "Masculino"}
                </strong>
              </div>

              {hasField(player, "birth_date") && (
                <div className="player-info-row">
                  <span>Fecha de nacimiento</span>
                  <strong>
                    {player.birth_date
                      ? formatDate(player.birth_date)
                      : "Sin definir"}
                  </strong>
                </div>
              )}

              <div className="player-info-row">
                <span>Posición principal</span>
                <strong>
                  {POSITION_LABELS[player.main_position] || "Sin definir"}
                </strong>
              </div>
            </div>
          </Card>
          {/* 👤 REPRESENTANTE */}

          {hasField(player, "representative_name") && (
          <Card className="player-info-card">
            <div className="player-card-edit-header">
              <h3>Contacto del representante</h3>

              {canEditPlayer && !editingRepresentative && (
                <button
                  type="button"
                  className="player-inline-edit-button"
                  onClick={() => setEditingRepresentative(true)}
                  aria-label="Editar contacto del representante"
                >
                  <Pencil size={16} />
                </button>
              )}
            </div>

            {editingRepresentative ? (
              <div className="player-inline-form">
                <label className="field-group">
                  <span>Representante</span>
                  <Input
                    name="representative_name"
                    value={representativeForm.representative_name}
                    onChange={handleRepresentativeChange}
                    placeholder="Ej: María González"
                  />
                </label>

                <label className="field-group">
                  <span>Teléfono</span>
                  <Input
                    name="representative_phone"
                    value={representativeForm.representative_phone}
                    onChange={handleRepresentativeChange}
                    placeholder="+584121234567"
                  />
                </label>

                <div className="player-inline-actions">
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={handleCancelRepresentativeEdit}
                  >
                    Cancelar
                  </Button>

                  <Button
                    type="button"
                    onClick={handleSaveRepresentative}
                    disabled={savingRepresentative}
                  >
                    {savingRepresentative ? "Guardando..." : "Guardar"}
                  </Button>
                </div>
              </div>
            ) : (
              <div className="player-info-list">
                <div className="player-info-row">
                  <span>Representante</span>
                  <strong>{player.representative_name || "Sin definir"}</strong>
                </div>

                <div className="player-info-row">
                  <span>Teléfono</span>

                  {player.representative_phone ? (
                    <strong>
                      <a href={`tel:${player.representative_phone}`}>
                        {player.representative_phone}
                      </a>
                    </strong>
                  ) : (
                    <strong>Sin definir</strong>
                  )}
                </div>
              </div>
            )}
          </Card>
          )}
          {player.historical_memberships?.length > 0 && (
            <Card className="player-teams-card">
              <div className="player-section-header">
                <div>
                  <span className="player-card-label">Historial</span>
                  <h3>Equipos anteriores</h3>
                </div>

                <span className="player-teams-count">
                  {player.historical_memberships.length}
                </span>
              </div>

              <div className="player-teams-list">
                {player.historical_memberships.map((team) => (
                  <div key={team.membership_id} className="player-team-row">
                    <div className="player-team-row-info">
                      <strong>{team.season_name || "Sin temporada"}</strong>
                      <span>
                        {team.category_name || "Sin categoría"} · {team.team_name} · Dorsal #{team.player_number}
                      </span>
                      <span>
                        {formatMembershipDate(team.joined_at) || "Inicio sin definir"} – {formatMembershipDate(team.left_at) || (team.season_status === "closed" ? "Temporada cerrada" : "Actual")}
                        {team.team_status === "archived"
                          ? " · Equipo archivado"
                          : ""}
                      </span>
                      <Link to={`/teams/${team.team_id}?season=${team.season_id}`}>
                        Ver equipo histórico
                      </Link>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {canViewSports && (
            <Card className="player-summary-card">
              <div className="player-section-header">
                <div>
                  <span className="player-card-label">Entrenamientos</span>
                  <h3>Resumen de asistencia</h3>
                </div>
              </div>

              {attendanceSummary ? (
                <div className="player-summary-grid">
                  <div>
                    <strong>{attendanceSummary.present}</strong>
                    <span>Presentes</span>
                  </div>
                  <div>
                    <strong>{attendanceSummary.late}</strong>
                    <span>Tardes</span>
                  </div>
                  <div>
                    <strong>{attendanceSummary.absent}</strong>
                    <span>Ausencias</span>
                  </div>
                  <div>
                    <strong>{attendanceSummary.attendance_rate}%</strong>
                    <span>Asistencia</span>
                  </div>
                </div>
              ) : (
                <p className="player-empty-text">
                  No hay asistencia de entrenamientos registrada.
                </p>
              )}
            </Card>
          )}

          {canDeletePlayer && (
            <Card className="player-delete-card">
              <div>
                <span className="player-card-label">Acción excepcional</span>
                <h3>Eliminar perfil</h3>
                <p>
                  Este perfil no tiene pertenencias ni historial deportivo o
                  financiero. La eliminación no se puede deshacer.
                </p>
              </div>

              <Button
                type="button"
                variant="danger"
                disabled={playerAction !== null}
                onClick={handleDeletePlayer}
              >
                {playerAction === "delete"
                  ? "Eliminando perfil..."
                  : "Eliminar perfil"}
              </Button>
            </Card>
          )}
        </div>
      )}

      {canViewPerformance && activeTab === "performance" && (
        <div
          role="tabpanel"
          id="player-panel-performance"
          aria-labelledby="player-tab-performance"
          aria-busy={performanceLoading}
          className="player-performance-panel"
        >
          <Card className="player-performance-context">
            <span className="player-card-label">Contexto</span>
            <h2>
              Rendimiento de {player.first_name} {player.last_name}
            </h2>
            <p>
              Período: <strong>{performancePeriodLabel}</strong>
            </p>
            <p>
              El rendimiento consolidado incluye todos los partidos finalizados.
            </p>
            {performanceTeamCount > 1 && (
              <p>
                El consolidado incluye partidos de distintos equipos dentro del
                período seleccionado.
              </p>
            )}
          </Card>

          <SeasonSelector
            includeAll
            loading={loadingSeasons}
            onChange={selectSeason}
            onRetry={reloadSeasons}
            requestedSeasonId={requestedSeasonId}
            seasons={seasons}
            selectedSeason={selectedSeason}
            error={seasonError}
          />

          {performanceLoading && (
            <Card className="player-performance-state" role="status">
              <p>Cargando rendimiento...</p>
            </Card>
          )}

          {!performanceLoading && performanceError && (
            <Card className="player-performance-state page-error-state" role="alert">
              <p>{getPerformanceErrorMessage(performanceError)}</p>
              <Button
                type="button"
                variant="secondary"
                onClick={loadPlayerPerformance}
              >
                Volver a intentar
              </Button>
            </Card>
          )}

          {!performanceLoading && !performanceError && performance && (
            <>
              {!hasAnyPerformance ? (
                <Card className="player-performance-state">
                  <h2>Rendimiento consolidado</h2>
                  <p className="player-empty-text">{performanceEmptyMessage}</p>
                </Card>
              ) : (
                <Card className="player-summary-card">
                  <div className="player-section-header">
                    <div>
                      <span className="player-card-label">Partidos finalizados</span>
                      <h2>Rendimiento consolidado</h2>
                    </div>
                  </div>

                  {!hasFinalizedPerformance ? (
                    <p className="player-empty-text">
                      Aún no hay partidos finalizados para este período.
                    </p>
                  ) : (
                    <>
                      <div className="player-summary-grid player-performance-kpis">
                        <div>
                          <strong>{performance.summary.matches_played}</strong>
                          <span>Partidos jugados</span>
                        </div>
                        <div>
                          <strong>{performance.summary.points_total}</strong>
                          <span>Puntos</span>
                          <small>
                            Ataques positivos + aces + bloqueos punto.
                          </small>
                        </div>
                        <div>
                          <strong>{performance.summary.errors_total}</strong>
                          <span>Errores contabilizados</span>
                          <small>Errores de ataque, armado, saque y bloqueo.</small>
                        </div>
                        <div>
                          <strong>{performance.summary.actions_total}</strong>
                          <span>Acciones</span>
                          <small>Suma de acciones de los seis fundamentos.</small>
                        </div>
                      </div>
                      <p className="player-stats-completeness">
                        Estadísticas registradas: {performance.summary.matches_with_stats}
                        {" "}de {performance.summary.matches_played} partidos jugados.
                      </p>
                    </>
                  )}
                </Card>
              )}

              {hasFinalizedPerformance && (
                <Card className="player-info-card">
                  <h2>Eficiencia y tasas</h2>
                  <div className="player-rate-grid">
                    {PERFORMANCE_RATE_METRICS.map((metric) => (
                      <div key={metric.key} className="player-rate-card">
                        <strong>{performance.summary[metric.key]}%</strong>
                        <span>{metric.label}</span>
                        {metric.help && <small>{metric.help}</small>}
                      </div>
                    ))}
                  </div>
                </Card>
              )}

              {hasFinalizedPerformance && (
                <Card className="player-info-card">
                  <h2>Detalle técnico por fundamento</h2>
                  <p className="player-section-help">
                    Abre cada fundamento para consultar sus componentes.
                  </p>
                  <div className="player-performance-list">
                    {PERFORMANCE_FUNDAMENTALS.map((fundamental) => (
                      <details
                        key={fundamental.label}
                        className="player-performance-row"
                      >
                        <summary>
                          <span>
                            <strong>{fundamental.label}</strong>
                            <small>
                              {performance.totals[fundamental.primary]} de{" "}
                              {performance.totals[fundamental.total]} acciones
                            </small>
                          </span>
                          <strong>{performance.summary[fundamental.rate]}%</strong>
                        </summary>
                        <dl className="player-fundamental-breakdown">
                          <div>
                            <dt>Total</dt>
                            <dd>{performance.totals[fundamental.total]}</dd>
                          </div>
                          <div>
                            <dt>{fundamental.primaryLabel}</dt>
                            <dd>{performance.totals[fundamental.primary]}</dd>
                          </div>
                          <div>
                            <dt>{fundamental.secondaryLabel}</dt>
                            <dd>{performance.totals[fundamental.secondary]}</dd>
                          </div>
                          <div>
                            <dt>{fundamental.negativeLabel}</dt>
                            <dd>{performance.totals[fundamental.negative]}</dd>
                          </div>
                        </dl>
                      </details>
                    ))}
                  </div>
                </Card>
              )}

              {hasFinalizedPerformance && (
                <Card className="player-info-card">
                  <div className="player-section-header">
                    <div>
                      <span className="player-card-label">Historial consolidado</span>
                      <h2>Partidos finalizados</h2>
                    </div>
                    <span className="player-teams-count">
                      {officialPerformanceMatches.length}
                    </span>
                  </div>
                  <ul className="player-match-history">
                    {officialPerformanceMatches.map((match) => (
                      <PerformanceMatchItem
                        key={match.match_player_id}
                        match={match}
                      />
                    ))}
                  </ul>
                </Card>
              )}

              {hasProvisionalPerformance && (
                <Card className="player-info-card player-provisional-card">
                  <div className="player-section-header">
                    <div>
                      <span className="player-card-label">En curso</span>
                      <h2>Partidos provisionales</h2>
                    </div>
                    <span className="player-teams-count">
                      {provisionalPerformanceMatches.length}
                    </span>
                  </div>
                  <p className="player-section-help">
                    Estas estadísticas aún no forman parte del rendimiento
                    consolidado.
                  </p>
                  <ul className="player-match-history">
                    {provisionalPerformanceMatches.map((match) => (
                      <PerformanceMatchItem
                        key={match.match_player_id}
                        match={match}
                        provisional
                      />
                    ))}
                  </ul>
                </Card>
              )}

              {performance.memberships?.length > 0 && (
                <Card className="player-info-card">
                  <div className="player-section-header">
                    <div>
                      <span className="player-card-label">Trayectoria</span>
                      <h2>Trayectoria deportiva</h2>
                    </div>
                  </div>
                  <div className="player-teams-list">
                    {performance.memberships.map((membership) => (
                      <div key={membership.id} className="player-team-row">
                        <div className="player-team-row-info">
                          <strong>{membership.team.name}</strong>
                          <span>
                            {membership.season?.name || "Temporada sin definir"}
                            {membership.team.category?.name
                              ? ` · ${membership.team.category.name}`
                              : ""}
                            {` · Dorsal #${membership.player_number}`}
                          </span>
                          <span>
                            {membership.left_at ? "Membresía finalizada" : "Membresía vigente"}
                            {membership.team.status === "archived"
                              ? " · Equipo archivado"
                              : ""}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </Card>
              )}
            </>
          )}
        </div>
      )}
      {canManagePayments && activeTab === "payments" && (
        <div role="tabpanel" id="player-panel-payments" aria-labelledby="player-tab-payments">
          {" "}
          {/* 💳 PAGOS */}
          {!player.enrollment_date ? (
            <Card className="player-payment-warning-card">
              <div>
                <span className="player-card-label">Pagos</span>
                <h3>Cobro mensual no configurado</h3>
                <p>
                  Define desde cuándo se cobra a esta deportista y cómo quieres
                  iniciar su estado de pagos.
                </p>
              </div>

              <Button
                type="button"
                onClick={() => navigate(`/players/${player_id}/payments`)}
              >
                Configurar cobro
              </Button>
            </Card>
          ) : (
            <Card className="player-payments-card">
              <div className="player-section-header">
                <div>
                  <span className="player-card-label">Pagos</span>
                  <h3>Resumen de pagos</h3>
                </div>

                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => navigate(`/players/${player_id}/payments`)}
                >
                  Gestionar
                </Button>
              </div>

              {payments.length === 0 ? (
                <p className="player-empty-text">
                  Este deportista aún no tiene pagos registrados.
                </p>
              ) : (
                <div className="player-payments-list">
                  {payments.slice(0, 2).map((payment) => (
                    <div key={payment.id} className="player-payment-row">
                      <div className="player-payment-row-info">
                        <strong>
                          {PAYMENT_TYPE_LABELS[payment.payment_type] || "Pago"}{" "}
                          · {formatMoney(payment.amount, payment.currency_code)}
                        </strong>

                        <span>{getPaymentDescription(payment)}</span>

                        {getPaymentMetaText(payment) && (
                          <span>{getPaymentMetaText(payment)}</span>
                        )}
                      </div>

                      <span
                        className={`status-badge ${
                          PAYMENT_STATUS_CLASSES[payment.status]
                        }`}
                      >
                        {PAYMENT_STATUS_LABELS[payment.status]}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          )}
        </div>
      )}
    </div>
  );
};
