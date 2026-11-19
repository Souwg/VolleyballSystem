import React, { useContext, useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { AlertCircle, ArrowRight, CalendarDays, Check, CircleCheck, Users } from "lucide-react";

import { Context } from "../../store/appContext";
import { PageHeader } from "../../component/ui/pageHeader";
import { Button } from "../../component/ui/button";
import { Card } from "../../component/ui/card";
import { ConfirmationDialog } from "../../component/ui/confirmationDialog";
import { ReadOnlyNotice } from "../../component/ui/readOnlyNotice";
import { FeeEditor } from "../../component/feeEditor";
import { errorMessages } from "../../utils/errorMessages";
import { formatMoney } from "../../utils/money";
import { canManage, useTeamAccessLost } from "../../utils/coachAccess";
import "../../../styles/tournaments.css";

const formatDate = (value) => value
  ? new Intl.DateTimeFormat("es", {
      day: "2-digit", month: "short", year: "numeric", timeZone: "UTC",
    }).format(new Date(`${value}T00:00:00Z`))
  : "Sin fecha";

const paymentStatus = (status) => ({
  pending: ["Pendiente", "status-warning"],
  paid: ["Pagado", "status-success"],
  overdue: ["Vencido", "status-danger"],
  cancelled: ["Cancelado", "status-muted"],
}[status] || [status || "Sin estado", "status-muted"]);

export const TournamentTeamDetail = () => {
  const { store, actions } = useContext(Context);
  const { tournament_team_id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const loadRequestId = useRef(0);
  const contextQuery = location.search.replace(/^\?/, "");

  const [tournamentTeam, setTournamentTeam] = useState(null);
  const [players, setPlayers] = useState([]);
  const [matches, setMatches] = useState([]);
  const [originalIds, setOriginalIds] = useState([]);
  const [selectedIds, setSelectedIds] = useState([]);
  const [eligibleCount, setEligibleCount] = useState(0);
  const [loadError, setLoadError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState({});
  const [search, setSearch] = useState("");
  const [showOnlySelected, setShowOnlySelected] = useState(false);
  const [confirmType, setConfirmType] = useState(null);
  const [preview, setPreview] = useState(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [generatingCharges, setGeneratingCharges] = useState(false);
  const [showChargeDetails, setShowChargeDetails] = useState(false);

  const loadRoster = async ({ preserveError = false } = {}) => {
    const requestId = ++loadRequestId.current;
    setLoading(true);
    setLoadError(null);
    setTournamentTeam(null);
    setPlayers([]);
    setMatches([]);
    if (!preserveError) setErrors({});

    const result = await actions.getTournamentTeamPlayers(tournament_team_id);
    if (requestId !== loadRequestId.current || result.code === "STALE_RESPONSE") return;

    if (!result.ok) {
      setLoadError(result);
      setLoading(false);
      return;
    }

    const rows = result.data.players || [];
    const registered = rows.filter((row) => row.is_registered).map((row) => row.player_id);
    setTournamentTeam(result.data.tournament_team);
    setPlayers(rows);
    setMatches(result.data.matches || []);
    setEligibleCount(result.data.currently_eligible_count || 0);
    setOriginalIds(registered);
    setSelectedIds(registered);
    setPreview(null);
    setLoading(false);
  };

  useEffect(() => {
    loadRoster();
    return () => { loadRequestId.current += 1; };
  }, [tournament_team_id]);

  useTeamAccessLost(() => loadRoster());

  const tournament = tournamentTeam?.tournament;
  const team = tournamentTeam?.team;
  const canManageFinancial = store.user?.role === "club_owner";
  const canEditRoster = Boolean(
    tournamentTeam &&
    ["club_owner", "coach"].includes(store.user?.role) &&
    canManage(tournamentTeam) &&
    team?.status === "active" &&
    tournamentTeam.status === "active" &&
    tournament?.status === "active" &&
    tournament?.season_status === "active",
  );

  const currentRows = useMemo(() => players.filter((row) =>
    canEditRoster
      ? row.membership_open !== false || row.is_registered
      : row.is_registered,
  ), [players, canEditRoster]);
  const historicalRows = useMemo(() => players.filter(
    (row) => row.registration_status === "withdrawn",
  ), [players]);
  const visibleRows = useMemo(() => {
    const normalized = search.trim().toLowerCase();
    return currentRows.filter((row) => {
      if (showOnlySelected && !selectedIds.includes(row.player_id)) return false;
      if (!normalized) return true;
      return `${row.player?.first_name || ""} ${row.player?.last_name || ""}`
        .toLowerCase().includes(normalized);
    });
  }, [currentRows, search, selectedIds, showOnlySelected]);

  const originalSet = useMemo(() => new Set(originalIds), [originalIds]);
  const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds]);
  const additions = selectedIds.filter((id) => !originalSet.has(id));
  const removals = originalIds.filter((id) => !selectedSet.has(id));
  const remains = selectedIds.filter((id) => originalSet.has(id));
  const selectionChanged = additions.length > 0 || removals.length > 0;

  const nameFor = (playerId) => {
    const row = players.find((item) => item.player_id === playerId);
    return `${row?.player?.first_name || ""} ${row?.player?.last_name || ""}`.trim();
  };

  const togglePlayer = (row) => {
    if (!canEditRoster) return;
    const selected = selectedSet.has(row.player_id);
    if (!selected && !row.currently_eligible) return;
    setSelectedIds((current) => selected
      ? current.filter((id) => id !== row.player_id)
      : [...current, row.player_id]);
    setErrors({});
    setPreview(null);
  };

  const selectAll = () => {
    const eligible = players.filter((row) => row.currently_eligible).map((row) => row.player_id);
    const existingIneligible = originalIds.filter((id) =>
      players.some((row) => row.player_id === id && !row.currently_eligible),
    );
    setSelectedIds([...new Set([...eligible, ...existingIneligible])]);
    setErrors({});
  };

  const saveRoster = async () => {
    if (saving || !selectionChanged) return;
    if (removals.length > 0 && confirmType !== "withdraw") {
      setConfirmType("withdraw");
      return;
    }

    setSaving(true);
    setErrors({});
    const result = await actions.updateTournamentTeamPlayers(
      tournament_team_id,
      selectedIds,
    );
    setConfirmType(null);

    if (!result.ok) {
      setErrors({
        [result.code || "NETWORK_ERROR"]: true,
        message: result.message,
      });
      await loadRoster({ preserveError: true });
      setSaving(false);
      return;
    }

    await loadRoster();
    setSaving(false);
  };

  const loadPreview = async () => {
    if (!canManageFinancial || loadingPreview) return;
    setLoadingPreview(true);
    const result = await actions.previewRegistrationCharges(tournament_team_id);
    setLoadingPreview(false);
    if (result.ok) setPreview(result.data);
    else setErrors({ [result.code || "NETWORK_ERROR"]: true, message: result.message });
  };

  useEffect(() => {
    if (
      canManageFinancial && !loading && !selectionChanged &&
      originalIds.length > 0 && Number(tournamentTeam?.registration_fee || 0) > 0
    ) loadPreview();
    else setPreview(null);
  }, [loading, selectionChanged, originalIds.length, tournamentTeam?.registration_fee]);

  const generateCharges = async () => {
    if (!preview || generatingCharges) return;
    if (preview.existing_charges_count > 0 && confirmType !== "charges") {
      setConfirmType("charges");
      return;
    }
    setGeneratingCharges(true);
    const result = await actions.generateRegistrationCharges(tournament_team_id);
    setConfirmType(null);
    if (!result.ok) setErrors({ [result.code || "NETWORK_ERROR"]: true, message: result.message });
    else await loadPreview();
    setGeneratingCharges(false);
  };

  const saveRegistrationFee = async (amount) => {
    const result = await actions.updateTournamentTeamRegistrationFee(tournament_team_id, amount);
    if (result.ok) await loadRoster();
    return result;
  };

  const createMatch = () => {
    const params = new URLSearchParams(location.search);
    params.set("tournament_team", tournament_team_id);
    navigate(`/teams/${team.id}/matches/new?${params.toString()}`);
  };

  if (loading) return <p role="status">Cargando participación del torneo...</p>;

  if (!tournamentTeam) {
    const message = loadError?.status === 403
      ? "No tienes acceso a esta participación."
      : loadError?.status === 404
      ? "Participación de torneo no encontrada."
      : "No se pudo cargar la participación del torneo.";
    return <Card><div className="empty-state" role="alert"><h3>{message}</h3>{loadError?.status !== 404 && <Button onClick={loadRoster}>Volver a intentar</Button>}</div></Card>;
  }

  const registrationFee = Number(tournamentTeam.registration_fee || 0);
  const estimatedPerPlayer = originalIds.length ? registrationFee / originalIds.length : 0;
  const canCreateMatch = canEditRoster && eligibleCount > 0;
  const backPath = `/tournaments/${tournamentTeam.tournament_id}${location.search}`;
  const thisPath = `/tournament-teams/${tournament_team_id}${location.search}`;
  const firstErrorCode = Object.keys(errors).find((code) => errors[code] === true);

  return (
    <div className="tournament-team-detail-page">
      <PageHeader
        variant="detail"
        eyebrow={`${tournament?.name || "Torneo"} · ${team?.category?.name || "Categoría"}`}
        title={team?.name || "Equipo"}
        subtitle={`${originalIds.length} en roster actual · ${historicalRows.length} retirados`}
        onBack={() => navigate(backPath)}
      />

      {tournament?.season_status === "closed" && <div className="tournament-context-banner historical" role="status">Consulta histórica · Temporada {tournament.season_name} cerrada</div>}
      {!canManage(tournamentTeam) && <ReadOnlyNotice>Solo consulta · este equipo no está dentro de tu scope de gestión.</ReadOnlyNotice>}
      {tournament?.status !== "active" && <ReadOnlyNotice>Torneo {tournament?.status === "completed" ? "completado" : "cancelado"} · la información deportiva es histórica.</ReadOnlyNotice>}

      {firstErrorCode && <div className="tournament-inline-alert danger" role="alert"><AlertCircle size={18} /><div><strong>{errors.message || errorMessages[firstErrorCode] || errorMessages.NETWORK_ERROR}</strong>{["FINANCE_DEPENDENCY", "TOURNAMENT_PLAYERS_FINANCIALLY_LOCKED"].includes(firstErrorCode) && <p>El roster real fue actualizado de nuevo y ningún retiro bloqueado se aplicó.</p>}{["PLAYER_NOT_AVAILABLE_FOR_TOURNAMENT", "TOURNAMENT_ROSTER_CHANGED"].includes(firstErrorCode) && <p>La elegibilidad cambió durante el guardado. Revisa la selección actual.</p>}</div></div>}

      <section className="tournament-detail-section" aria-labelledby="current-roster-title">
        <div className="tournament-section-heading"><div><h2 id="current-roster-title">Roster actual</h2><p>El roster del torneo define quiénes pueden participar en nuevos partidos. Cada partido mantiene su propia convocatoria y elegibilidad.</p></div></div>
        <Card className="tournament-player-selection-card">
          {canEditRoster && <div className="tournament-roster-toolbar">
            <input className="input" type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Buscar deportista" aria-label="Buscar deportista" />
            <Button type="button" variant="secondary" onClick={selectAll}>Seleccionar elegibles</Button>
            <Button type="button" variant="secondary" onClick={() => setSelectedIds([])}>Limpiar selección</Button>
            <button type="button" className="tournament-selected-filter" aria-pressed={showOnlySelected} onClick={() => setShowOnlySelected((current) => !current)}>{showOnlySelected ? "Mostrar todas" : "Solo seleccionadas"}</button>
          </div>}

          {visibleRows.length === 0 ? <div className="empty-state"><Users size={28} /><p>No hay deportistas en este grupo.</p></div> : <div className="tournament-player-list">
            {visibleRows.map((row) => {
              const selected = selectedSet.has(row.player_id);
              const unavailable = !row.currently_eligible;
              return canEditRoster ? <button
                type="button"
                key={row.player_id}
                className={`tournament-player-option ${selected ? "selected" : ""}`}
                aria-pressed={selected}
                disabled={!selected && unavailable}
                onClick={() => togglePlayer(row)}
              >
                <span className="tournament-player-check" aria-hidden="true">{selected && <Check size={16} />}</span>
                <span className="tournament-player-copy"><strong>{row.player?.first_name} {row.player?.last_name}</strong><span>#{row.player_number || "—"}{row.player?.main_position ? ` · ${row.player.main_position}` : ""}</span></span>
                {row.registration_status === "withdrawn" && !selected && !unavailable
                  ? <span className="status-badge status-muted">Retirado · disponible para reactivar</span>
                  : unavailable && <span className="status-badge status-warning">No elegible para nuevos partidos</span>}
              </button> : row.is_registered ? <div key={row.player_id} className="tournament-player-history-row"><div><strong>{row.player?.first_name} {row.player?.last_name}</strong><span>#{row.player_number || "—"}</span></div>{unavailable ? <span className="status-badge status-warning">Actualmente no elegible</span> : <span className="status-badge status-success">Inscrito al cierre</span>}</div> : null;
            })}
          </div>}

          {canEditRoster && selectionChanged && <div className="tournament-roster-diff" role="status">
            <div><strong>{remains.length}</strong><span>Permanecen</span></div>
            <div><strong>{additions.length}</strong><span>Se incorporan</span>{additions.slice(0, 3).map((id) => <small key={id}>{nameFor(id)}</small>)}</div>
            <div><strong>{removals.length}</strong><span>Se retiran</span>{removals.slice(0, 3).map((id) => <small key={id}>{nameFor(id)}</small>)}</div>
          </div>}
          <p className="tournament-history-help">Los partidos ya registrados conservan su historial.</p>
          {canEditRoster && <div className="form-actions"><Button type="button" onClick={saveRoster} disabled={!selectionChanged || saving}>{saving ? "Guardando..." : "Guardar roster"}</Button></div>}
        </Card>
      </section>

      <section className="tournament-detail-section" aria-labelledby="roster-history-title">
        <div className="tournament-section-heading"><div><h2 id="roster-history-title">Historial de inscripciones</h2><p>Los retiros se conservan; nunca se convierten en personas que “nunca estuvieron”.</p></div></div>
        <Card>{historicalRows.length === 0 ? <p>No hay participantes retirados.</p> : <div className="tournament-player-history-list">{historicalRows.map((row) => <div key={row.player_id} className="tournament-player-history-row"><div><strong>{row.player?.first_name} {row.player?.last_name}</strong><span>#{row.player_number || "—"}</span></div><span className="status-badge status-muted">Retirado</span></div>)}</div>}</Card>
      </section>

      <section className="tournament-detail-section" aria-labelledby="team-matches-title">
        <div className="tournament-section-heading"><div><h2 id="team-matches-title">Partidos</h2><p>Partidos de este equipo dentro del torneo.</p></div>{canCreateMatch && <Button onClick={createMatch}>Crear partido</Button>}</div>
        {canEditRoster && eligibleCount === 0 && <div className="tournament-inline-alert warning" role="status"><AlertCircle size={18} /><span>Necesitas al menos una persona elegible en el roster para crear un partido.</span></div>}
        {matches.length === 0 ? <Card><div className="empty-state"><CalendarDays size={28} /><p>No hay partidos registrados para este equipo.</p></div></Card> : <div className="tournament-match-list">{matches.map((match) => <Link key={match.id} className="tournament-match-row" to={`/matches/${match.id}${contextQuery ? `?${contextQuery}` : ""}`} state={{ from: thisPath }}><div><strong>{match.opponent_name || "Rival"}</strong><span>{formatDate(match.date)}</span></div><div className="tournament-match-side"><span className={`status-badge ${match.is_completed ? "status-success" : "status-warning"}`}>{match.is_completed ? "Completado" : "Abierto"}</span>{match.is_completed ? <strong>{match.home_sets}–{match.opponent_sets}</strong> : <span>Revisar partido</span>}</div></Link>)}</div>}
      </section>

      {canManageFinancial && <section className="tournament-detail-section tournament-admin-section" aria-labelledby="registration-admin-title">
        <div className="tournament-section-heading"><div><h2 id="registration-admin-title">Inscripción y pagos</h2><p>Administración financiera separada del roster y los partidos.</p></div></div>
        {canEditRoster && <Card><FeeEditor label="Costo de inscripción" value={tournamentTeam.registration_fee} currencyCode={tournamentTeam.currency_code} helper="Los cobros pendientes no cambian automáticamente. Los pagos y recibos existentes se conservan." onSave={saveRegistrationFee} /></Card>}
        <Card className="tournament-cost-summary-card"><div><span>Inscripción del equipo</span><strong>{formatMoney(registrationFee, tournamentTeam.currency_code)}</strong></div><div><span>Deportistas</span><strong>{originalIds.length}</strong></div><div><span>Por deportista</span><strong>{originalIds.length ? formatMoney(estimatedPerPlayer, tournamentTeam.currency_code) : "—"}</strong></div></Card>
        {loadingPreview && <p role="status">Calculando distribución...</p>}
        {preview && <Card className="tournament-charge-card">
          <div className="tournament-charge-heading"><div><h3>Cobros por deportista</h3><p>Los pagos y recibos se administran desde Pagos.</p></div></div>
          <div className="tournament-charge-summary"><div><span>Cobros existentes</span><strong>{preview.existing_charges_count}</strong></div><div><span>Participantes</span><strong>{preview.registered_players_count}</strong></div></div>
          {preview.players?.length > 0 && <button type="button" className="tournament-charge-details-toggle" aria-expanded={showChargeDetails} onClick={() => setShowChargeDetails((current) => !current)}>{showChargeDetails ? "Ocultar detalle" : "Ver detalle de cobros"}</button>}
          {showChargeDetails && <div className="tournament-charge-list">{preview.players.map((row) => { const [label, className] = paymentStatus(row.existing_charge?.status); return <div key={row.player_id} className="tournament-charge-row"><div><strong>{row.player?.first_name} {row.player?.last_name}</strong><span>#{row.player_number || "—"}</span></div><div className="tournament-charge-row-side">{row.existing_charge && <span className={`status-badge ${className}`}>{label}</span>}<strong>{formatMoney(row.amount, preview.currency_code)}</strong></div></div>; })}</div>}
          <div className="tournament-financial-actions">{preview.can_generate && <Button onClick={generateCharges} disabled={generatingCharges}>{generatingCharges ? "Actualizando..." : "Crear o actualizar cobros"}</Button>}<Button variant="secondary" onClick={() => navigate(`/payments?payment_type=tournament&tournament_team_id=${tournament_team_id}`)}>Ver en Pagos <ArrowRight size={17} /></Button></div>
        </Card>}
      </section>}

      {confirmType === "withdraw" && <ConfirmationDialog busy={saving} danger title="Confirmar retiros del roster" titleId="roster-withdraw-title" descriptionId="roster-withdraw-copy" confirmLabel={`Retirar ${removals.length}`} onCancel={() => setConfirmType(null)} onConfirm={saveRoster}><p>Se retirarán {removals.length} participantes del roster activo. Los partidos ya registrados conservarán su historial.</p><p>Los pagos realizados o con recibo pueden bloquear la operación; ningún retiro se aplicará parcialmente.</p></ConfirmationDialog>}
      {confirmType === "charges" && <ConfirmationDialog busy={generatingCharges} title="Actualizar cobros" titleId="charges-update-title" descriptionId="charges-update-copy" confirmLabel="Actualizar distribución" onCancel={() => setConfirmType(null)} onConfirm={generateCharges}><p>Se actualizarán los cobros pendientes con la distribución actual. Los pagos completados y recibos no se modificarán.</p></ConfirmationDialog>}
    </div>
  );
};
