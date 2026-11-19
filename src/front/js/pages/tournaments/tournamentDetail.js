import React, { useContext, useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { AlertCircle, CalendarDays, CircleDot, Trophy, Users } from "lucide-react";

import { Context } from "../../store/appContext";
import { PageHeader } from "../../component/ui/pageHeader";
import { Input } from "../../component/ui/input";
import { FormField } from "../../component/ui/formField";
import { Select } from "../../component/ui/select";
import { Button } from "../../component/ui/button";
import { Card } from "../../component/ui/card";
import { ConfirmationDialog } from "../../component/ui/confirmationDialog";
import { AssignedBadge, ReadOnlyBadge } from "../../component/ui/readOnlyNotice";
import { FeeEditor } from "../../component/feeEditor";
import { errorMessages } from "../../utils/errorMessages";
import { formatMoney } from "../../utils/money";
import {
  canConfigureSportsFinance,
  canManage,
  getManageableTeams,
  hasField,
  isScopedCoach,
  useTeamAccessLost,
} from "../../utils/coachAccess";
import "../../../styles/tournaments.css";

const formatDate = (value) => value
  ? new Intl.DateTimeFormat("es", {
      day: "2-digit", month: "short", year: "numeric", timeZone: "UTC",
    }).format(new Date(`${value}T00:00:00Z`))
  : "Sin fecha";

const getStatusData = (status) => ({
  active: { label: "Activo", className: "status-success" },
  completed: { label: "Completado", className: "status-info" },
  cancelled: { label: "Cancelado", className: "status-danger" },
}[status] || { label: status || "Sin estado", className: "status-muted" });

const MatchRow = ({ contextQuery, from, match }) => (
  <Link
    className="tournament-match-row"
    to={`/matches/${match.id}${contextQuery ? `?${contextQuery}` : ""}`}
    state={{ from }}
  >
    <div>
      <strong>{match.team_name || "Equipo"} · {match.opponent_name || "Rival"}</strong>
      <span>{formatDate(match.date)}</span>
    </div>
    <div className="tournament-match-side">
      <span className={`status-badge ${match.is_completed ? "status-success" : "status-warning"}`}>
        {match.is_completed ? "Completado" : "Abierto"}
      </span>
      {match.is_completed && <strong>{match.home_sets}–{match.opponent_sets}</strong>}
      {!match.is_completed && <span>Revisar partido</span>}
    </div>
  </Link>
);

export const TournamentDetail = () => {
  const { store, actions } = useContext(Context);
  const { tournament_id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const loadRequestId = useRef(0);
  const teamsRequestId = useRef(0);
  const contextQuery = location.search.replace(/^\?/, "");
  const detailPath = `/tournaments/${tournament_id}${location.search}`;

  const [tournament, setTournament] = useState(null);
  const [teams, setTeams] = useState([]);
  const [loadError, setLoadError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showAddTeam, setShowAddTeam] = useState(false);
  const [showMetadata, setShowMetadata] = useState(false);
  const [dialogTarget, setDialogTarget] = useState(null);
  const [teamId, setTeamId] = useState("");
  const [registrationFee, setRegistrationFee] = useState("");
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);
  const [metadata, setMetadata] = useState({});

  const loadTournament = async () => {
    const requestId = ++loadRequestId.current;
    setLoading(true);
    setLoadError(null);
    setTournament(null);

    const result = await actions.getTournamentDetail(tournament_id);
    if (requestId !== loadRequestId.current || result.code === "STALE_RESPONSE") return;

    if (result.ok) {
      setTournament(result.data.tournament);
      setMetadata({
        name: result.data.tournament.name || "",
        organizer_name: result.data.tournament.organizer_name || "",
        start_date: result.data.tournament.start_date || "",
        end_date: result.data.tournament.end_date || "",
      });
    } else {
      setLoadError(result);
    }
    setLoading(false);
  };

  const loadAvailableTeams = async () => {
    const requestId = ++teamsRequestId.current;
    const result = await actions.getTeams();
    if (requestId !== teamsRequestId.current) return;
    setTeams(result.ok ? result.data.teams || [] : []);
  };

  useEffect(() => {
    loadTournament();
    loadAvailableTeams();
    return () => {
      loadRequestId.current += 1;
      teamsRequestId.current += 1;
    };
  }, [tournament_id]);

  useTeamAccessLost(() => {
    loadTournament();
    loadAvailableTeams();
  });

  const entries = tournament?.teams || [];
  const matches = tournament?.matches || [];
  const scopedCoach = isScopedCoach(store);
  const canConfigureFinance = canConfigureSportsFinance(store);
  const canManageTournament = Boolean(tournament && canManage(tournament));
  const isOperational =
    tournament?.status === "active" && tournament?.season_status === "active";
  const canEditTournament = isOperational && canManageTournament;
  // A scoped Coach cannot mutate Tournament metadata/lifecycle, but can add
  // an assigned Team. The selectable list remains scoped by getManageableTeams.
  const canAddTeam = Boolean(
    isOperational && ["club_owner", "coach"].includes(store.user?.role),
  );
  const availableTeams = getManageableTeams(teams).filter((team) =>
    team.status === "active" &&
    team.season_id === tournament?.season_id &&
    !entries.some((entry) => entry.team_id === team.id),
  );

  const setActionError = (result) => {
    setErrors({
      [result.code || "NETWORK_ERROR"]: true,
      raw: result.raw || null,
      message: result.message,
    });
  };

  const handleAddTeam = async (event) => {
    event.preventDefault();
    if (busy || !teamId) {
      if (!teamId) setErrors({ TEAM_ID_REQUIRED: true });
      return;
    }
    setBusy(true);
    setErrors({});
    const result = await actions.addTeamToTournament(tournament_id, {
      team_id: teamId,
      ...(canConfigureFinance && {
        registration_fee: registrationFee === "" ? 0 : registrationFee,
      }),
    });

    if (!result.ok) {
      setActionError(result);
      if (result.code === "TEAM_ALREADY_IN_TOURNAMENT") {
        await Promise.all([loadTournament(), loadAvailableTeams()]);
      }
      setBusy(false);
      return;
    }

    setShowAddTeam(false);
    setTeamId("");
    setRegistrationFee("");
    await Promise.all([loadTournament(), loadAvailableTeams()]);
    setBusy(false);
  };

  const handleSaveMetadata = async (event) => {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setErrors({});
    const result = await actions.updateTournament(tournament_id, metadata);

    if (!result.ok) {
      setActionError(result);
      if (["TOURNAMENT_NOT_ACTIVE", "INVALID_TOURNAMENT_STATUS", "SEASON_CLOSED"].includes(result.code)) {
        setShowMetadata(false);
        await loadTournament();
      }
      setBusy(false);
      return;
    }

    setShowMetadata(false);
    await loadTournament();
    setBusy(false);
  };

  const saveDefaultFee = async (amount) => {
    const result = await actions.updateTournament(tournament_id, {
      default_referee_fee: amount,
    });
    if (result.ok) await loadTournament();
    else if (result.code === "TOURNAMENT_NOT_ACTIVE") await loadTournament();
    return result;
  };

  const runTransition = async () => {
    const target = dialogTarget;
    if (!target || busy) return;
    setBusy(true);
    setErrors({});
    const result = target === "completed"
      ? await actions.completeTournament(tournament_id)
      : await actions.cancelTournament(tournament_id);

    if (!result.ok) {
      setActionError(result);
      setDialogTarget(null);
      await loadTournament();
      setBusy(false);
      return;
    }

    setDialogTarget(null);
    setShowAddTeam(false);
    setShowMetadata(false);
    await loadTournament();
    setBusy(false);
  };

  if (loading) return <p role="status">Cargando torneo...</p>;

  if (!tournament) {
    const message = loadError?.status === 403
      ? "No tienes acceso a este torneo."
      : loadError?.status === 404
      ? "Torneo no encontrado."
      : "No se pudo cargar el torneo.";
    return <Card><div className="empty-state" role="alert">
      <h3>{message}</h3>
      {loadError?.status !== 404 && <Button onClick={loadTournament}>Volver a intentar</Button>}
      <Button variant="secondary" onClick={() => navigate(`/tournaments${location.search}`)}>Volver a torneos</Button>
    </div></Card>;
  }

  const status = getStatusData(tournament.status);
  const firstErrorCode = Object.keys(errors).find((code) => errors[code] === true);
  const openMatchBlocker = firstErrorCode === "TOURNAMENT_HAS_OPEN_MATCHES";
  const pendingBlocker = ["TOURNAMENT_HAS_PENDING_CHARGES", "FINANCE_DEPENDENCY"].includes(firstErrorCode);
  const canShowLifecycle = isOperational && canManageTournament;
  const canTransition = canShowLifecycle && tournament.open_matches_count === 0;

  return (
    <div className="tournament-detail-page">
      <PageHeader
        variant="detail"
        eyebrow={`${tournament.season_name || "Temporada"} · Torneo`}
        title={tournament.name}
        subtitle={`${formatDate(tournament.start_date)}${tournament.end_date ? ` — ${formatDate(tournament.end_date)}` : ""} · ${tournament.organizer_name || "Organizador no especificado"}`}
        onBack={() => navigate(`/tournaments${location.search}`)}
      />

      {tournament.season_status === "closed" && (
        <div className="tournament-context-banner historical" role="status">
          Consulta histórica · Temporada {tournament.season_name} cerrada
        </div>
      )}

      <div className="tournament-summary-grid tournament-summary-grid-desktop">
        <Card className="tournament-summary-card">
          <span className={`status-badge ${status.className}`}>{status.label}</span>
          <h4>Estado del torneo</h4><p>{isOperational ? "Operación deportiva disponible" : "Información deportiva de solo consulta"}</p>
        </Card>
        <Card className="tournament-summary-card">
          <Users size={18} /><h4>Equipos y roster</h4>
          <p>{tournament.total_teams} equipos · {tournament.active_roster_count}/{tournament.total_roster_count} deportistas</p>
        </Card>
        <Card className="tournament-summary-card">
          <CircleDot size={18} /><h4>Partidos</h4>
          <p>{tournament.open_matches_count} abiertos · {tournament.completed_matches_count} completados</p>
        </Card>
      </div>

      {firstErrorCode && (
        <div className="tournament-inline-alert danger" role="alert">
          <AlertCircle size={18} />
          <div>
            <strong>{errors.message || errorMessages[firstErrorCode] || errorMessages.NETWORK_ERROR}</strong>
            {openMatchBlocker && <p>{errors.raw?.open_matches_count || tournament.open_matches_count} partidos requieren revisión.</p>}
            {pendingBlocker && canConfigureFinance && <Button variant="secondary" onClick={() => navigate("/payments?payment_type=tournament")}>Revisar en Pagos</Button>}
          </div>
        </div>
      )}

      <section className="tournament-detail-section" aria-labelledby="tournament-teams-title">
        <div className="tournament-section-heading">
          <div><h2 id="tournament-teams-title">Equipos inscritos</h2><p>Cada equipo mantiene su propio roster y sus partidos.</p></div>
          {canAddTeam && availableTeams.length > 0 && !showAddTeam && (
            <Button onClick={() => { setShowAddTeam(true); setErrors({}); }}>+ Inscribir equipo</Button>
          )}
        </div>

        {canAddTeam && availableTeams.length === 0 && (
          <div className="tournament-context-banner" role="status">
            {scopedCoach ? "Solo puedes gestionar equipos que tienes asignados. No hay otro equipo disponible para inscribir." : "No hay equipos activos disponibles en esta temporada."}
          </div>
        )}

        {showAddTeam && canAddTeam && (
          <Card className="tournament-form-card">
            <form className="form" onSubmit={handleAddTeam}>
              <FormField label="Equipo" error={errors.TEAM_ID_REQUIRED ? errorMessages.TEAM_ID_REQUIRED : null}>
                <Select value={teamId} onChange={(event) => setTeamId(event.target.value)}>
                  <option value="">Selecciona un equipo</option>
                  {availableTeams.map((team) => <option key={team.id} value={team.id}>{team.category?.name ? `${team.category.name} · ` : ""}{team.name}</option>)}
                </Select>
              </FormField>
              {canConfigureFinance && <FormField label={`Costo de inscripción (${tournament.currency_code || "moneda"})`} helper="Se administrará después, separado del roster deportivo.">
                <Input type="number" min="0" step="0.01" value={registrationFee} onChange={(event) => setRegistrationFee(event.target.value)} />
              </FormField>}
              <div className="form-actions">
                <Button type="button" variant="secondary" onClick={() => setShowAddTeam(false)}>Cancelar</Button>
                <Button type="submit" disabled={busy}>{busy ? "Inscribiendo..." : "Inscribir equipo"}</Button>
              </div>
            </form>
          </Card>
        )}

        {entries.length === 0 ? (
          <Card><div className="empty-state"><Trophy size={30} /><h4>Aún no hay equipos inscritos</h4><p>El torneo puede prepararse progresivamente.</p>{canAddTeam && availableTeams.length > 0 && <Button onClick={() => setShowAddTeam(true)}>Inscribir equipo</Button>}</div></Card>
        ) : (
          <div className="tournament-teams-list">
            {entries.map((entry) => {
              const entryStatus = getStatusData(entry.status);
              return <Link key={entry.id} className="tournament-team-card-link" to={`/tournament-teams/${entry.id}${location.search}`}>
                <Card className="tournament-team-card">
                  <div className="tournament-team-main"><Users size={20} /><div className="tournament-team-info">
                    <h3>{entry.team?.category?.name ? `${entry.team.category.name} · ` : ""}{entry.team?.name || "Equipo"}</h3>
                    <p>{entry.active_roster_count}/{entry.total_roster_count} roster · {entry.open_matches_count} abiertos · {entry.completed_matches_count} completados</p>
                  </div></div>
                  <div className="tournament-team-meta">
                    <span className={`status-badge ${entryStatus.className}`}>{entryStatus.label}</span>
                    {scopedCoach && (entry.is_assigned ? <AssignedBadge /> : <ReadOnlyBadge />)}
                    {hasField(entry, "registration_fee") && <span>Administración disponible</span>}
                  </div>
                </Card>
              </Link>;
            })}
          </div>
        )}
      </section>

      <section className="tournament-detail-section" aria-labelledby="tournament-matches-title">
        <div className="tournament-section-heading"><div><h2 id="tournament-matches-title">Partidos</h2><p>Seguimiento contextual del torneo.</p></div></div>
        {tournament.open_matches_count > 0 && <div className="tournament-inline-alert warning" role="status"><AlertCircle size={18} /><strong>{tournament.open_matches_count} partidos pendientes de cerrar</strong></div>}
        {matches.length === 0 ? <Card><div className="empty-state"><CalendarDays size={28} /><h4>No hay partidos registrados</h4><p>Crea partidos desde la participación de cada equipo.</p></div></Card> : <div className="tournament-match-list">{matches.map((match) => <MatchRow key={match.id} match={match} contextQuery={contextQuery} from={detailPath} />)}</div>}
      </section>

      {canShowLifecycle && (
        <section className="tournament-detail-section" aria-labelledby="tournament-lifecycle-title">
          <div className="tournament-section-heading"><div><h2 id="tournament-lifecycle-title">Cerrar torneo</h2><p>Completar y cancelar son estados terminales.</p></div></div>
          {canTransition ? <Card><div className="tournament-lifecycle-actions">
            <Button variant="secondary" onClick={() => setDialogTarget("completed")}>Completar torneo</Button>
            {tournament.has_pending_admin_dependencies ? <div className="tournament-inline-alert warning" role="status"><AlertCircle size={18} /><span>{canConfigureFinance ? `${tournament.pending_admin_dependencies_count} cargos pendientes impiden cancelar.` : "Existen dependencias administrativas pendientes."}</span>{canConfigureFinance && <Button variant="secondary" onClick={() => navigate("/payments?payment_type=tournament")}>Ir a Pagos</Button>}</div> : <Button variant="danger" onClick={() => setDialogTarget("cancelled")}>Cancelar torneo</Button>}
          </div></Card> : <div className="tournament-inline-alert warning" role="status"><AlertCircle size={18} /><span>Resuelve los partidos abiertos antes de completar o cancelar.</span></div>}
        </section>
      )}

      {(canEditTournament || canConfigureFinance) && (
        <section className="tournament-detail-section tournament-admin-section" aria-labelledby="tournament-admin-title">
          <div className="tournament-section-heading"><div><h2 id="tournament-admin-title">{canConfigureFinance ? "Administración" : "Información del torneo"}</h2><p>La metadata puede editarse mientras el torneo está activo; los históricos existentes no se recalculan.</p></div>{canEditTournament && !showMetadata && <Button variant="secondary" onClick={() => setShowMetadata(true)}>Editar información</Button>}</div>
          {showMetadata && <Card><form className="form" onSubmit={handleSaveMetadata}>
            <FormField label="Nombre"><Input value={metadata.name} onChange={(event) => setMetadata({ ...metadata, name: event.target.value })} /></FormField>
            <FormField label="Organizador"><Input value={metadata.organizer_name} onChange={(event) => setMetadata({ ...metadata, organizer_name: event.target.value })} /></FormField>
            <div className="tournament-form-grid"><FormField label="Inicio"><Input type="date" value={metadata.start_date} onChange={(event) => setMetadata({ ...metadata, start_date: event.target.value })} /></FormField><FormField label="Fin"><Input type="date" min={metadata.start_date} value={metadata.end_date} onChange={(event) => setMetadata({ ...metadata, end_date: event.target.value })} /></FormField></div>
            <div className="form-actions"><Button type="button" variant="secondary" onClick={() => setShowMetadata(false)}>Descartar</Button><Button type="submit" disabled={busy}>{busy ? "Guardando..." : "Guardar información"}</Button></div>
          </form></Card>}
          {canEditTournament && hasField(tournament, "default_referee_fee") && <Card><FeeEditor label="Arbitraje predeterminado por partido" value={tournament.default_referee_fee} currencyCode={tournament.currency_code} helper="Se utiliza como valor predeterminado en nuevos partidos. Los partidos existentes no se modifican." onSave={saveDefaultFee} /></Card>}
          {!canEditTournament && canConfigureFinance && <Card><p>La información deportiva está cerrada. La administración histórica permitida se conserva en sus contextos financieros.</p></Card>}
        </section>
      )}

      {dialogTarget && <ConfirmationDialog
        busy={busy}
        danger={dialogTarget === "cancelled"}
        titleId="tournament-transition-title"
        descriptionId="tournament-transition-description"
        title={dialogTarget === "completed" ? "Completar torneo" : "Cancelar torneo"}
        confirmLabel={dialogTarget === "completed" ? "Confirmar completado" : "Confirmar cancelación"}
        onCancel={() => setDialogTarget(null)}
        onConfirm={runTransition}
      >
        {dialogTarget === "completed" ? <>
          <p>El torneo quedará completado y su información deportiva dejará de ser editable. No podrá reabrirse en SportFlow 1.0.</p>
          {tournament.total_matches === 0 && <p><strong>Este torneo no tiene partidos registrados. Aun así puedes completarlo.</strong></p>}
          <p>El roster y los partidos registrados conservarán su historial.</p>
        </> : <>
          <p>La cancelación es terminal y no permite reactivación.</p>
          <p>El roster, los partidos, los pagos y los recibos conservarán su historial.</p>
        </>}
      </ConfirmationDialog>}
    </div>
  );
};
