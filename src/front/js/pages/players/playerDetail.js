import React, { useEffect, useContext, useState } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import { Context } from "../../store/appContext";
import "../../../styles/playerDetails.css";
import { Card } from "../../component/ui/card";
import { Button } from "../../component/ui/button";
import { Input } from "../../component/ui/input";
import { getAssetUrl } from "../../utils/getAssetUrl";
import { errorMessages } from "../../utils/errorMessages";
import { formatMoney } from "../../utils/money";
import { useToast } from "../../../../context/toastContext";
import { Pencil } from "lucide-react";

const POSITION_LABELS = {
  setter: "Armador",
  outside: "Punta",
  middle: "Central",
  opposite: "Opuesto",
  libero: "Líbero",
};

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
  const [payments, setPayments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editingRepresentative, setEditingRepresentative] = useState(false);
  const [savingRepresentative, setSavingRepresentative] = useState(false);
  const [playerAction, setPlayerAction] = useState(null);
  const [representativeForm, setRepresentativeForm] = useState({
    representative_name: "",
    representative_phone: "",
  });
  const [activeTab, setActiveTab] = useState("profile");
  const canManagePayments = ["club_owner", "staff"].includes(
    store.user?.role,
  );
  const canViewSports = ["club_owner", "coach"].includes(store.user?.role);
  const canViewPerformance = ["club_owner", "coach", "staff"].includes(
    store.user?.role,
  );
  const canEditPlayer = ["club_owner", "coach"].includes(store.user?.role);
  const canManagePlayerStatus = store.user?.role === "club_owner";
  const canDeletePlayer = store.user?.role === "club_owner";

  const handleBack = () => {
    if (location.state?.from) {
      navigate(location.state.from);
      return;
    }

    navigate("/players");
  };

  const loadPlayerData = async () => {
    setLoading(true);

    const [playersResult, attendanceResult, performanceResult, paymentsResult] =
      await Promise.all([
        canViewSports ? null : actions.getPlayers(),
        canViewSports ? actions.getPlayerAttendance(player_id) : null,
        canViewPerformance ? actions.getPlayerPerformance(player_id) : null,
        canManagePayments ? actions.getPlayerPayments(player_id) : null,
      ]);

    if (playersResult?.ok) {
      const loadedPlayer = playersResult.data.players.find(
        (item) => item.id === player_id,
      );

      if (loadedPlayer) {
        setPlayer(loadedPlayer);
        setRepresentativeForm({
          representative_name: loadedPlayer.representative_name || "",
          representative_phone: loadedPlayer.representative_phone || "",
        });
      }
    }

    if (attendanceResult?.ok) {
      const data = attendanceResult.data;

      setPlayer(data.player);
      setAttendanceSummary(data.summary);
      setTrainingHistory(data.history || []);

      setRepresentativeForm({
        representative_name: data.player.representative_name || "",
        representative_phone: data.player.representative_phone || "",
      });
    }

    if (performanceResult?.ok) {
      setPerformance(performanceResult.data);
      setOfficialPerformanceMatches(
        performanceResult.data.official_matches || [],
      );
      setProvisionalPerformanceMatches(
        performanceResult.data.provisional_matches || [],
      );
    } else {
      setPerformance(null);
      setOfficialPerformanceMatches([]);
      setProvisionalPerformanceMatches([]);
    }

    if (paymentsResult?.ok) {
      setPayments(paymentsResult.data.payments || []);
    }

    setLoading(false);
  };

  useEffect(() => {
    loadPlayerData();
  }, [player_id]);

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
        ? "¿Reactivar a esta jugadora?\n\nVolverá a estar disponible para nuevas operaciones deportivas según las reglas actuales."
        : "¿Desactivar a esta jugadora?\n\nLa jugadora permanecerá registrada y conservará su historial, pero dejará de estar disponible para nuevas operaciones deportivas según las reglas actuales.",
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
      `¿Quitar a esta jugadora del equipo?\n\nContinuará registrada en el club y su historial no se eliminará.`,
    );

    if (!confirmed) return;

    setPlayerAction(`team-${team.id}`);

    try {
      const result = await actions.removePlayerFromTeam(team.id, player.id);

      if (result.ok) {
        setPlayer((current) => ({
          ...current,
          teams: (current.teams || []).filter((item) => item.id !== team.id),
        }));
      }
    } finally {
      setPlayerAction(null);
    }
  };

  const handleDeletePlayer = async () => {
    if (playerAction || !canDeletePlayer) return;

    const confirmed = window.confirm(
      "¿Eliminar esta jugadora del club?\n\nEsta acción solo está disponible si la jugadora no tiene historial que deba conservarse.",
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

  if (loading) {
    return <p>Cargando perfil...</p>;
  }

  if (!player) {
    return <p>No se pudo cargar el deportista.</p>;
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

            <p>
              {player.teams?.length > 0
                ? player.teams
                    .map(
                      (team) =>
                        `${team.category_name || "Sin categoría"} · ${
                          team.name
                        } · #${team.player_number}`,
                    )
                    .join(" • ")
                : "Sin equipo asignado"}
            </p>
          </div>
        </div>

        {canEditPlayer && (
          <div className="player-profile-actions">
            <Button
              variant="secondary"
              onClick={() => navigate(`/players/${player_id}/edit`)}
            >
              Editar perfil
            </Button>
          </div>
        )}
      </section>

      <div className="player-tabs">
        <button
          className={`player-tab ${activeTab === "profile" ? "active" : ""}`}
          onClick={() => setActiveTab("profile")}
        >
          Perfil
        </button>

        {canViewPerformance && (
          <button
            className={`player-tab ${
              activeTab === "performance" ? "active" : ""
            }`}
            onClick={() => setActiveTab("performance")}
          >
            Rendimiento
          </button>
        )}

        {canManagePayments && (
          <button
            className={`player-tab ${
              activeTab === "payments" ? "active" : ""
            }`}
            onClick={() => setActiveTab("payments")}
          >
            Pagos
          </button>
        )}
      </div>

      {activeTab === "profile" && (
        <>
          <Card className="player-info-card player-global-status-card">
            <div className="player-section-header">
              <div>
                <span className="player-card-label">Estado del Club</span>
                <h3>Disponibilidad de la jugadora</h3>
              </div>

              <span
                className={`status-badge ${
                  player.is_active ? "status-success" : "status-muted"
                }`}
              >
                {player.is_active ? "Activa" : "Inactiva"}
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
                      ? "Desactivando jugadora..."
                      : "Reactivando jugadora..."
                    : player.is_active
                    ? "Desactivar jugadora"
                    : "Reactivar jugadora"}
                </Button>
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

              <div className="player-info-row">
                <span>Fecha de nacimiento</span>
                <strong>
                  {player.birth_date
                    ? formatDate(player.birth_date)
                    : "Sin definir"}
                </strong>
              </div>

              <div className="player-info-row">
                <span>Posición principal</span>
                <strong>
                  {POSITION_LABELS[player.main_position] || "Sin definir"}
                </strong>
              </div>
            </div>
          </Card>
          {/* 👤 REPRESENTANTE */}

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
          {/* 🏐 MEMBERSHIP CARDS */}
          <Card className="player-teams-card">
            <div className="player-section-header">
              <div>
                <span className="player-card-label">Equipos</span>
                <h3>Participación deportiva</h3>
              </div>

              <span className="player-teams-count">
                {player.teams?.length || 0}
              </span>
            </div>

            {player.teams?.length > 0 ? (
              <div className="player-teams-list">
                {player.teams.map((team) => (
                  <div key={team.id} className="player-team-row">
                    <div className="player-team-row-info">
                      <strong>{team.category_name || "Sin categoría"}</strong>
                      <span>
                        {team.name} · Número #{team.player_number}
                      </span>
                    </div>

                    <div className="player-team-row-actions">
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

                      {canEditPlayer && (
                        <Button
                          type="button"
                          variant="secondary"
                          disabled={playerAction !== null}
                          onClick={() => handleRemoveFromTeam(team)}
                        >
                          {playerAction === `team-${team.id}`
                            ? "Quitando..."
                            : "Quitar del equipo"}
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="player-empty-text">Sin equipo asignado</p>
            )}
          </Card>

          {canDeletePlayer && (
            <Card className="player-delete-card">
              <div>
                <span className="player-card-label">Acción excepcional</span>
                <h3>Eliminar jugadora del club</h3>
                <p>
                  Solo puede eliminarse si no posee historial deportivo o
                  financiero. Si tiene historial, desactívala para conservarlo.
                </p>
              </div>

              <Button
                type="button"
                variant="danger"
                disabled={playerAction !== null}
                onClick={handleDeletePlayer}
              >
                {playerAction === "delete"
                  ? "Eliminando jugadora..."
                  : "Eliminar jugadora del club"}
              </Button>
            </Card>
          )}
        </>
      )}

      {canViewPerformance && activeTab === "performance" && (
        <>
          {/* ===== RENDIMIENTO EN PARTIDOS ===== */}

          <Card className="player-summary-card">
            <div className="player-section-header">
              <div>
                <span className="player-card-label">Partidos</span>

                <h3>Rendimiento oficial</h3>
              </div>
            </div>

            {!performance || performance.summary.matches_played === 0 ? (
              <p className="player-empty-text">
                Esta deportista todavía no tiene rendimiento oficial en
                partidos finalizados.
              </p>
            ) : (
              <div className="player-summary-grid">
                <div>
                  <strong>{performance.summary.matches_played}</strong>

                  <span>Partidos jugados</span>
                </div>

                <div>
                  <strong>{performance.summary.points_total}</strong>

                  <span>Puntos generados</span>
                </div>

                <div>
                  <strong>{performance.summary.attack_efficiency}%</strong>

                  <span>Eficiencia de ataque</span>
                </div>

                <div>
                  <strong>
                    {performance.summary.reception_positive_rate}%
                  </strong>

                  <span>Recepción positiva</span>
                </div>
              </div>
            )}
          </Card>

          {/* ===== DETALLE POR FUNDAMENTO ===== */}

          {performance && performance.summary.matches_played > 0 && (
            <Card className="player-info-card">
              <h3>Detalle por fundamento</h3>

              <div className="player-performance-list">
                <div className="player-performance-row">
                  <div>
                    <strong>Ataque</strong>
                    <span>
                      {performance.totals.attacks_positive} positivos de{" "}
                      {performance.totals.attacks_total}
                    </span>
                  </div>

                  <strong>{performance.summary.attack_positive_rate}%</strong>
                </div>

                <div className="player-performance-row">
                  <div>
                    <strong>Recepción</strong>
                    <span>
                      {performance.totals.receptions_positive} positivas de{" "}
                      {performance.totals.receptions_total}
                    </span>
                  </div>

                  <strong>
                    {performance.summary.reception_positive_rate}%
                  </strong>
                </div>

                <div className="player-performance-row">
                  <div>
                    <strong>Defensa</strong>
                    <span>
                      {performance.totals.defenses_positive} positivas de{" "}
                      {performance.totals.defenses_total}
                    </span>
                  </div>

                  <strong>{performance.summary.defense_positive_rate}%</strong>
                </div>

                <div className="player-performance-row">
                  <div>
                    <strong>Armado</strong>
                    <span>
                      {performance.totals.sets_positive} positivos de{" "}
                      {performance.totals.sets_total}
                    </span>
                  </div>

                  <strong>{performance.summary.set_positive_rate}%</strong>
                </div>

                <div className="player-performance-row">
                  <div>
                    <strong>Saque</strong>
                    <span>
                      {performance.totals.serves_aces} aces de{" "}
                      {performance.totals.serves_total}
                    </span>
                  </div>

                  <strong>{performance.summary.serve_ace_rate}%</strong>
                </div>

                <div className="player-performance-row">
                  <div>
                    <strong>Bloqueo</strong>
                    <span>
                      {performance.totals.blocks_points} puntos de{" "}
                      {performance.totals.blocks_total}
                    </span>
                  </div>

                  <strong>{performance.summary.block_point_rate}%</strong>
                </div>
              </div>
            </Card>
          )}

          {/* ===== PARTIDOS OFICIALES ===== */}

          <Card className="player-info-card">
            <div className="player-section-header">
              <div>
                <span className="player-card-label">Historial</span>

                <h3>Partidos oficiales</h3>
              </div>

              <span className="player-teams-count">
                {officialPerformanceMatches.length}
              </span>
            </div>

            {officialPerformanceMatches.length === 0 ? (
              <p className="player-empty-text">
                No hay partidos finalizados con participación registrada.
              </p>
            ) : (
              <div className="player-match-history">
                {officialPerformanceMatches.map((match) => (
                  <div key={match.match_player_id} className="player-match-row">
                    <div className="player-match-row-info">
                      <strong>vs. {match.opponent_name}</strong>

                      <span>
                        {formatDate(match.date)}
                        {match.team?.name ? ` · ${match.team.name}` : ""}
                      </span>

                      <span>
                        {match.points_total} puntos · {match.errors_total}{" "}
                        errores
                      </span>

                      <span>Oficial · Partido finalizado</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>

          {provisionalPerformanceMatches.length > 0 && (
            <Card className="player-info-card">
              <div className="player-section-header">
                <div>
                  <span className="player-card-label">Pendientes</span>

                  <h3>Partidos pendientes de confirmar</h3>
                </div>

                <span className="player-teams-count">
                  {provisionalPerformanceMatches.length}
                </span>
              </div>

              <p className="text-muted">
                Estas estadísticas todavía no forman parte del rendimiento
                oficial.
              </p>

              <div className="player-match-history">
                {provisionalPerformanceMatches.map((match) => (
                  <div key={match.match_player_id} className="player-match-row">
                    <div className="player-match-row-info">
                      <strong>vs. {match.opponent_name}</strong>

                      <span>
                        {formatDate(match.date)}
                        {match.team?.name ? ` · ${match.team.name}` : ""}
                      </span>

                      <span>
                        {match.points_total} puntos · {match.errors_total}{" "}
                        errores
                      </span>

                      <span>Provisional · Partido sin finalizar</span>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* ===== ENTRENAMIENTOS ===== */}

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
        </>
      )}
      {canManagePayments && activeTab === "payments" && (
        <>
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
        </>
      )}
    </div>
  );
};
