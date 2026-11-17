import React, { useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Context } from "../../store/appContext";
import { PageHeader } from "../../component/ui/pageHeader";
import { Card } from "../../component/ui/card";
import { Button } from "../../component/ui/button";
import { Input } from "../../component/ui/input";
import { Select } from "../../component/ui/select";
import { FormField } from "../../component/ui/formField";
import { authFetch, parseResponse } from "../../utils/authFetch";
import { errorMessages } from "../../utils/errorMessages";

import "../../../styles/seasons.css";

const emptyForm = { name: "", start_date: "", end_date: "" };
const lifecycleConflictCodes = new Set([
  "SEASON_NOT_PLANNED",
  "SEASON_TRANSITION_CONFLICT",
  "SEASON_TEAM_REQUIRED",
  "SEASON_HAS_OPEN_ACTIVITIES",
  "TARGET_ROSTER_INVALID",
  "SOURCE_TEAM_NOT_ACTIVE",
  "ROSTER_COPY_CONFLICT",
]);

const request = async (path, options = {}) => {
  try {
    return await parseResponse(await authFetch(path, options));
  } catch (error) {
    return { ok: false, code: "NETWORK_ERROR", message: errorMessages.NETWORK_ERROR };
  }
};

const formatDate = (value) => {
  if (!value) return "Sin fecha final";
  return new Date(`${value}T00:00:00`).toLocaleDateString("es-ES", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
};

const formatRange = (season) =>
  `${formatDate(season.start_date)} – ${formatDate(season.end_date)}`;

const overlaps = (first, second) => {
  if (!first.start_date || !second.start_date) return false;
  return (first.end_date || "9999-12-31") >= second.start_date &&
    (second.end_date || "9999-12-31") >= first.start_date;
};

const getSoftWarnings = (form, seasons, excludedId = null) => {
  const comparable = seasons.filter((season) => season.id !== excludedId);
  const warnings = [];
  if (
    form.name.trim() &&
    comparable.some(
      (season) => season.name.toLowerCase() === form.name.trim().toLowerCase(),
    )
  ) warnings.push("Ya existe otra temporada con este nombre.");
  if (
    form.start_date &&
    comparable.some((season) => overlaps(form, season))
  ) warnings.push("Las fechas se solapan con otra temporada.");
  return warnings;
};

const SeasonMeta = ({ season }) => (
  <>
    <p className="season-dates">{formatRange(season)}</p>
    <p className="season-metrics">
      {season.active_teams ?? season.total_teams ?? 0} equipos activos
      {season.preparation
        ? ` · ${season.preparation.total_players || 0} pertenencias preparadas`
        : ""}
    </p>
  </>
);

const ActivationDialog = ({ preflight, busy, onCancel, onConfirm }) => {
  const cancelRef = useRef(null);

  useEffect(() => {
    cancelRef.current?.focus();
    const handleKeyDown = (event) => {
      if (event.key === "Escape" && !busy) onCancel();
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [busy, onCancel]);

  return (
    <div
      className="season-dialog-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !busy) onCancel();
      }}
    >
      <div
        className="season-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="season-dialog-title"
        aria-describedby="season-dialog-description"
      >
        <h2 id="season-dialog-title">Confirmar activación</h2>
        <div id="season-dialog-description">
          {preflight.mode === "recovery" ? (
            <p>
              No hay una temporada activa. <strong>{preflight.target.name}</strong>{" "}
              pasará a ser la temporada actual del club.
            </p>
          ) : (
            <div className="season-transition-summary">
              <span>Temporada actual: <strong>{preflight.source.name}</strong></span>
              <span aria-hidden="true">↓ se cerrará</span>
              <span>Temporada a activar: <strong>{preflight.target.name}</strong></span>
            </div>
          )}
          <ul>
            <li>Los Teams y memberships históricos se conservarán.</li>
            <li>No se generarán cargos financieros automáticamente.</li>
            <li>Una temporada cerrada no puede reabrirse desde SportFlow.</li>
          </ul>
        </div>
        <div className="form-actions">
          <button
            ref={cancelRef}
            className="button button-secondary"
            type="button"
            disabled={busy}
            onClick={onCancel}
          >
            Cancelar
          </button>
          <Button type="button" disabled={busy} onClick={onConfirm}>
            {busy ? "Activando..." : "Activar temporada"}
          </Button>
        </div>
      </div>
    </div>
  );
};

export const Seasons = () => {
  const { store } = useContext(Context);
  const isOwner = store.user?.role === "club_owner";
  const [seasons, setSeasons] = useState([]);
  const [details, setDetails] = useState({});
  const [loading, setLoading] = useState(true);
  const [listError, setListError] = useState("");
  const [detailError, setDetailError] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [form, setForm] = useState(emptyForm);
  const [editingId, setEditingId] = useState("");
  const [editForm, setEditForm] = useState(emptyForm);
  const [targetId, setTargetId] = useState("");
  const [selectedTeams, setSelectedTeams] = useState([]);
  const [sourceTeamId, setSourceTeamId] = useState("");
  const [targetTeamId, setTargetTeamId] = useState("");
  const [sourcePlayers, setSourcePlayers] = useState([]);
  const [targetPlayers, setTargetPlayers] = useState([]);
  const [rosterDraft, setRosterDraft] = useState({});
  const [rosterLoaded, setRosterLoaded] = useState(false);
  const [preflight, setPreflight] = useState(null);
  const [preflightLoading, setPreflightLoading] = useState(false);
  const [showActivationDialog, setShowActivationDialog] = useState(false);
  const [lastPreparedTeamId, setLastPreparedTeamId] = useState("");
  const activationTriggerRef = useRef(null);

  const activeSeason = useMemo(
    () => seasons.find((season) => season.status === "active") || null,
    [seasons],
  );
  const plannedSeasons = useMemo(
    () => seasons.filter((season) => season.status === "planned").sort(
      (first, second) => first.start_date.localeCompare(second.start_date),
    ),
    [seasons],
  );
  const closedSeasons = useMemo(
    () => seasons.filter((season) => season.status === "closed").sort(
      (first, second) => second.start_date.localeCompare(first.start_date),
    ),
    [seasons],
  );
  const targetSeason = details[targetId] ||
    plannedSeasons.find((season) => season.id === targetId);
  const sourceSeason = activeSeason ? details[activeSeason.id] : null;

  const loadDetail = useCallback(async (seasonId) => {
    if (!seasonId) return null;
    const result = await request(`/api/seasons/${seasonId}`);
    if (!result.ok) {
      setDetailError(
        result.code === "FORBIDDEN"
          ? "No tienes permiso para consultar esta preparación."
          : result.code === "SEASON_NOT_FOUND"
          ? "La temporada ya no está disponible."
          : result.message || "No pudimos cargar el detalle de la temporada.",
      );
      return null;
    }
    setDetailError("");
    setDetails((current) => ({ ...current, [seasonId]: result.data.season }));
    return result.data.season;
  }, []);

  const loadPreflight = useCallback(async (seasonId) => {
    if (!seasonId || !isOwner) return null;
    setPreflightLoading(true);
    try {
      const result = await request(`/api/seasons/${seasonId}/preflight`);
      if (!result.ok) {
        setPreflight(null);
        setDetailError(result.message || "No pudimos revisar esta temporada.");
        return null;
      }
      setPreflight(result.data);
      setDetailError("");
      return result.data;
    } finally {
      setPreflightLoading(false);
    }
  }, [isOwner]);

  const loadSeasons = useCallback(async () => {
    setLoading(true);
    setListError("");
    try {
      const result = await request("/api/seasons");
      if (!result.ok) {
        setSeasons([]);
        setListError(result.message || "No pudimos cargar las temporadas.");
        return false;
      }
      const rows = result.data.seasons || [];
      const planned = rows.filter((season) => season.status === "planned").sort(
        (first, second) => first.start_date.localeCompare(second.start_date),
      );
      const active = rows.find((season) => season.status === "active");
      setSeasons(rows);
      setTargetId((current) => {
        if (planned.some((season) => season.id === current)) return current;
        return planned.length === 1 ? planned[0].id : "";
      });
      if (active) await loadDetail(active.id);
      return true;
    } finally {
      setLoading(false);
    }
  }, [loadDetail]);

  useEffect(() => { loadSeasons(); }, [loadSeasons]);

  useEffect(() => {
    setSelectedTeams([]);
    setSourceTeamId("");
    setTargetTeamId("");
    setSourcePlayers([]);
    setTargetPlayers([]);
    setRosterDraft({});
    setRosterLoaded(false);
    setPreflight(null);
    setLastPreparedTeamId("");
    if (targetId) {
      loadDetail(targetId);
      loadPreflight(targetId);
    }
  }, [targetId, loadDetail, loadPreflight]);

  const refreshPreparation = async () => {
    await loadSeasons();
    if (targetId) await Promise.all([loadDetail(targetId), loadPreflight(targetId)]);
  };

  const run = async (callback, successMessage) => {
    if (busy) return null;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const result = await callback();
      if (!result.ok) {
        if (lifecycleConflictCodes.has(result.code)) {
          setSourcePlayers([]);
          setTargetPlayers([]);
          setRosterDraft({});
          setRosterLoaded(false);
          setPreflight(null);
          await loadSeasons();
          if (targetId) await loadDetail(targetId);
          setError("La temporada cambió mientras preparabas esta operación. Actualiza y vuelve a revisar.");
        } else {
          setError(errorMessages[result.code] || result.message || "No pudimos completar la acción.");
        }
        return null;
      }
      setMessage(successMessage);
      await refreshPreparation();
      return result;
    } finally {
      setBusy(false);
    }
  };

  const createSeason = async (event) => {
    event.preventDefault();
    const result = await run(
      () => request("/api/seasons", { method: "POST", body: JSON.stringify(form) }),
      "La temporada quedó creada en preparación.",
    );
    if (result) {
      setForm(emptyForm);
      setTargetId(result.data.season.id);
    }
  };

  const startEditing = (season) => {
    setEditingId(season.id);
    setEditForm({ name: season.name, start_date: season.start_date, end_date: season.end_date || "" });
  };

  const editSeason = async (event) => {
    event.preventDefault();
    const result = await run(
      () => request(`/api/seasons/${editingId}`, { method: "PATCH", body: JSON.stringify(editForm) }),
      "La temporada en preparación quedó actualizada.",
    );
    if (result) setEditingId("");
  };

  const deleteSeason = async (season) => {
    if (!window.confirm(`¿Eliminar ${season.name}?\n\nEsta temporada está vacía y sin uso. La acción no se puede deshacer.`)) return;
    const result = await run(
      () => request(`/api/seasons/${season.id}`, { method: "DELETE" }),
      "La temporada vacía fue eliminada.",
    );
    if (result && targetId === season.id) setTargetId("");
  };

  const duplicateTeams = async () => {
    if (!activeSeason || !targetId) return;
    const result = await run(
      () => request(`/api/seasons/${targetId}/teams/duplicate`, {
        method: "POST",
        body: JSON.stringify({ source_season_id: activeSeason.id, team_ids: selectedTeams }),
      }),
      "La estructura seleccionada quedó preparada.",
    );
    if (result) {
      setSelectedTeams([]);
      setLastPreparedTeamId(result.data.teams?.[0]?.id || "");
    }
  };

  const loadRoster = async () => {
    if (!sourceTeamId || !targetTeamId) return;
    setError("");
    setRosterLoaded(false);
    const [sourceResult, targetResult] = await Promise.all([
      request(`/api/teams/${sourceTeamId}/players`),
      request(`/api/teams/${targetTeamId}/players`),
    ]);
    if (!sourceResult.ok || !targetResult.ok) {
      setError(sourceResult.message || targetResult.message || "No pudimos cargar el roster.");
      return;
    }
    const sourceRows = sourceResult.data.players || [];
    const targetRows = targetResult.data.players || [];
    setSourcePlayers(sourceRows);
    setTargetPlayers(targetRows);
    setRosterDraft(Object.fromEntries(sourceRows.map((row) => [row.id, {
      selected: false,
      player_number: row.player_number,
      status: row.status,
    }])));
    setRosterLoaded(true);
  };

  const copyRoster = async () => {
    const result = await run(
      () => request(`/api/teams/${targetTeamId}/roster/copy`, {
        method: "POST",
        body: JSON.stringify({
          source_team_id: sourceTeamId,
          players: sourcePlayers.filter((row) => rosterDraft[row.id]?.selected).map((row) => ({
            player_id: row.id,
            player_number: Number(rosterDraft[row.id].player_number),
            status: rosterDraft[row.id].status,
          })),
        }),
      }),
      "El roster seleccionado quedó preparado.",
    );
    if (result) {
      setSourcePlayers([]);
      setTargetPlayers([]);
      setRosterDraft({});
      setRosterLoaded(false);
      setLastPreparedTeamId(targetTeamId);
    }
  };

  const openActivationDialog = async () => {
    const review = await loadPreflight(targetId);
    if (!review?.can_activate) return;
    activationTriggerRef.current = document.activeElement;
    setShowActivationDialog(true);
  };

  const closeActivationDialog = useCallback(() => {
    setShowActivationDialog(false);
    window.requestAnimationFrame(() => activationTriggerRef.current?.focus());
  }, []);

  const transition = async () => {
    if (!targetId || !preflight) return;
    const body = { confirm_activation: true };
    if (preflight.source?.id) body.source_season_id = preflight.source.id;
    const result = await run(
      () => request(`/api/seasons/${targetId}/transition`, { method: "POST", body: JSON.stringify(body) }),
      preflight.mode === "recovery"
        ? "La temporada quedó activa y la operación deportiva fue recuperada."
        : "La nueva temporada está activa y la anterior quedó cerrada.",
    );
    if (result) {
      setShowActivationDialog(false);
      setTargetId("");
    }
  };

  if (loading) return <p role="status">Cargando ciclo de temporadas...</p>;
  if (listError) {
    return (
      <Card className="season-page-error" role="alert">
        <h2>No pudimos cargar las temporadas</h2>
        <p>{listError}</p>
        <Button type="button" variant="secondary" onClick={loadSeasons}>Volver a intentar</Button>
      </Card>
    );
  }

  const selectedSourceTeam = (sourceSeason?.teams || []).find((team) => team.id === sourceTeamId);
  const selectedTargetTeam = (targetSeason?.teams || []).find((team) => team.id === targetTeamId);
  const selectedRoster = sourcePlayers.filter((row) => rosterDraft[row.id]?.selected);
  const rosterIssue = (row) => {
    if (!row.is_active) return "Inactivo en el club";
    if (selectedTargetTeam && selectedTargetTeam.gender !== "mixed" && row.sex !== selectedTargetTeam.gender) return "No compatible con la rama del equipo destino";
    if (targetPlayers.some((target) => target.id === row.id)) return "Ya pertenece al equipo destino";
    const number = Number(rosterDraft[row.id]?.player_number);
    if (!Number.isInteger(number) || number < 1 || number > 99) return "Dorsal destino inválido";
    if (targetPlayers.some((target) => target.player_number === number)) return "Dorsal ocupado en el equipo destino";
    if (selectedRoster.some((selected) => selected.id !== row.id && Number(rosterDraft[selected.id]?.player_number) === number)) return "Dorsal repetido en esta copia";
    return "";
  };
  const hasSelectedIssues = selectedRoster.some((row) => rosterIssue(row));
  const createWarnings = getSoftWarnings(form, seasons);
  const editWarnings = getSoftWarnings(editForm, seasons, editingId);

  return (
    <>
      <PageHeader
        title="Ciclo de temporadas"
        subtitle="Crea, prepara, revisa y activa cada temporada sin alterar el histórico del club."
      />
      {error && <p className="form-error season-live-message" role="alert">{error}</p>}
      {message && <p className="season-success season-live-message" role="status">{message}</p>}

      <section className="season-section" aria-labelledby="current-season-title">
        <h2 id="current-season-title">Temporada actual</h2>
        {activeSeason ? (
          <Card className="season-card season-card-current">
            <div className="season-card-heading">
              <div><span className="season-eyebrow">Operación deportiva actual</span><h3>{activeSeason.name}</h3></div>
              <span className="status-badge status-success">Activa</span>
            </div>
            <SeasonMeta season={activeSeason} />
            <div className="season-activity-summary">
              <span>{activeSeason.open_activities?.scheduled_trainings || 0} entrenamientos programados</span>
              <span>{activeSeason.open_activities?.open_matches || 0} partidos abiertos</span>
              <span>{activeSeason.open_activities?.active_tournaments || 0} torneos activos</span>
            </div>
            <Link className="season-link" to={`/categories?season=${activeSeason.id}`}>Ver estructura actual</Link>
          </Card>
        ) : (
          <Card className="season-recovery-notice" role="note">
            <h3>No hay una temporada activa</h3>
            <p>Selecciona una temporada en preparación para revisarla y recuperar la operación deportiva.</p>
          </Card>
        )}
      </section>

      <section className="season-section" aria-labelledby="planned-seasons-title">
        <div className="season-section-heading">
          <div><h2 id="planned-seasons-title">Temporadas en preparación</h2><p>La preparación siempre se realiza sobre una temporada explícita.</p></div>
        </div>
        {plannedSeasons.length === 0 ? (
          <Card className="empty-state"><h3>No hay temporadas en preparación</h3><p>Cuando quieras preparar otro ciclo, crea una temporada aquí.</p></Card>
        ) : (
          <div className="season-planned-grid">
            {plannedSeasons.map((season) => (
              <Card key={season.id} className={`season-card ${targetId === season.id ? "season-card-selected" : ""}`}>
                <div className="season-card-heading"><h3>{season.name}</h3><span className="status-badge status-info">En preparación</span></div>
                <SeasonMeta season={season} />
                <p className="season-readiness-copy">{season.preparation?.teams_without_players || 0} equipos sin deportistas · {season.preparation?.teams_without_coach || 0} sin entrenador</p>
                {isOwner ? (
                  <div className="season-card-actions">
                    <Button type="button" onClick={() => setTargetId(season.id)}>Preparar</Button>
                    <Button type="button" variant="secondary" onClick={() => startEditing(season)}>Editar datos</Button>
                    {season.can_delete && <button className="season-delete-action" type="button" onClick={() => deleteSeason(season)}>Eliminar temporada vacía</button>}
                  </div>
                ) : <p>Temporada en preparación por el administrador del club.</p>}
                {editingId === season.id && (
                  <form className="form season-edit-form" onSubmit={editSeason}>
                    <FormField label="Nombre" htmlFor={`edit-season-name-${season.id}`}>
                      <Input id={`edit-season-name-${season.id}`} autoFocus required value={editForm.name} onChange={(event) => setEditForm({ ...editForm, name: event.target.value })} />
                    </FormField>
                    <FormField label="Fecha de inicio" htmlFor={`edit-season-start-${season.id}`}>
                      <Input id={`edit-season-start-${season.id}`} type="date" required value={editForm.start_date} onChange={(event) => setEditForm({ ...editForm, start_date: event.target.value })} />
                    </FormField>
                    <FormField label="Fecha final (opcional)" htmlFor={`edit-season-end-${season.id}`}>
                      <Input id={`edit-season-end-${season.id}`} type="date" value={editForm.end_date} onChange={(event) => setEditForm({ ...editForm, end_date: event.target.value })} />
                    </FormField>
                    {editWarnings.map((warning) => <p className="season-soft-warning" role="note" key={warning}>{warning}</p>)}
                    <div className="form-actions"><Button type="button" variant="secondary" onClick={() => setEditingId("")}>Cancelar</Button><Button type="submit" disabled={busy}>{busy ? "Guardando..." : "Guardar cambios"}</Button></div>
                  </form>
                )}
              </Card>
            ))}
          </div>
        )}
      </section>

      {isOwner && (
        <section className="season-section" aria-labelledby="create-season-title">
          <Card className="season-create-card">
            <h2 id="create-season-title">Crear temporada</h2>
            <p>Se creará como temporada en preparación. No reemplazará ni cerrará la temporada actual.</p>
            <form onSubmit={createSeason} className="form season-fields-grid">
              <FormField label="Nombre" htmlFor="create-season-name"><Input id="create-season-name" value={form.name} required onChange={(event) => setForm({ ...form, name: event.target.value })} /></FormField>
              <FormField label="Fecha de inicio" htmlFor="create-season-start"><Input id="create-season-start" type="date" value={form.start_date} required onChange={(event) => setForm({ ...form, start_date: event.target.value })} /></FormField>
              <FormField label="Fecha final (opcional)" htmlFor="create-season-end"><Input id="create-season-end" type="date" value={form.end_date} onChange={(event) => setForm({ ...form, end_date: event.target.value })} /></FormField>
              {createWarnings.map((warning) => <p className="season-soft-warning" role="note" key={warning}>{warning}</p>)}
              <Button type="submit" disabled={busy}>{busy ? "Creando..." : "Crear temporada"}</Button>
            </form>
          </Card>
        </section>
      )}

      {isOwner && targetId && targetSeason && (
        <section className="season-section season-workspace" aria-labelledby="preparation-title">
          <div className="season-workspace-heading">
            <div><span className="season-eyebrow">Destino seleccionado</span><h2 id="preparation-title">Preparación de {targetSeason.name}</h2><p>{formatRange(targetSeason)}</p></div>
            <Button type="button" variant="secondary" onClick={() => setTargetId("")}>Cerrar preparación</Button>
          </div>
          {detailError && <Card className="season-detail-error" role="alert"><p>{detailError}</p><Button type="button" variant="secondary" onClick={() => Promise.all([loadDetail(targetId), loadPreflight(targetId)])}>Volver a intentar</Button></Card>}

          {activeSeason ? (
            <Card className="season-preparation-step">
              <span className="season-step-number">1</span><h3>Copiar estructura de equipos</h3>
              <p>Copia Team, Category y rama. No copia Players, Coaches, Trainings, Matches, Tournaments ni Finance.</p>
              {(sourceSeason?.teams || []).filter((team) => team.status === "active").map((team) => (
                <label key={team.id} className="checkbox-row"><input type="checkbox" checked={selectedTeams.includes(team.id)} onChange={() => setSelectedTeams((rows) => rows.includes(team.id) ? rows.filter((id) => id !== team.id) : [...rows, team.id])} />{team.name} · {team.category?.name || "Sin categoría"}</label>
              ))}
              {(sourceSeason?.teams || []).filter((team) => team.status === "active").length === 0 && <p>No hay equipos activos para copiar desde la temporada actual.</p>}
              <Button type="button" disabled={busy || !selectedTeams.length} onClick={duplicateTeams}>Copiar estructura seleccionada</Button>
            </Card>
          ) : (
            <Card className="season-preparation-step" role="note">
              <span className="season-step-number">1</span><h3>Preparar equipos</h3><p>No existe una temporada actual desde la que copiar estructura. Prepara manualmente los Teams necesarios.</p><Link className="season-link" to={`/categories?season=${targetId}`}>Preparar equipos</Link>
            </Card>
          )}

          {activeSeason && (
            <Card className="season-preparation-step">
              <span className="season-step-number">2</span><h3>Revisar roster</h3>
              <div className="season-fields-grid">
                <FormField label="Equipo origen" htmlFor="season-source-team"><Select id="season-source-team" value={sourceTeamId} onChange={(event) => setSourceTeamId(event.target.value)}><option value="">Selecciona</option>{(sourceSeason?.teams || []).filter((team) => team.status === "active").map((team) => <option key={team.id} value={team.id}>{team.name}</option>)}</Select></FormField>
                <FormField label="Equipo destino" htmlFor="season-target-team"><Select id="season-target-team" value={targetTeamId} onChange={(event) => setTargetTeamId(event.target.value)}><option value="">Selecciona</option>{(targetSeason?.teams || []).filter((team) => team.status === "active").map((team) => <option key={team.id} value={team.id}>{team.name}</option>)}</Select></FormField>
              </div>
              <Button type="button" variant="secondary" disabled={!sourceTeamId || !targetTeamId} onClick={loadRoster}>Preparar vista previa</Button>
              {rosterLoaded && sourcePlayers.length === 0 && <p className="text-muted">El equipo origen no tiene deportistas disponibles para copiar.</p>}
              {sourcePlayers.length > 0 && <p><strong>{activeSeason.name} · {selectedSourceTeam?.name}</strong>{" → "}<strong>{targetSeason?.name} · {selectedTargetTeam?.name}</strong></p>}
              <div className="season-roster-list">
                {sourcePlayers.map((row) => {
                  const player = row.player || row;
                  const draft = rosterDraft[player.id] || {};
                  const issue = rosterIssue(row);
                  const hardBlocked = !row.is_active || issue === "No compatible con la rama del equipo destino" || issue === "Ya pertenece al equipo destino";
                  return (
                    <Card key={player.id} className="roster-copy-player">
                      <label className="checkbox-row"><input type="checkbox" disabled={hardBlocked} checked={Boolean(draft.selected)} onChange={(event) => setRosterDraft((current) => ({ ...current, [player.id]: { ...current[player.id], selected: event.target.checked } }))} /><strong>{player.first_name} {player.last_name}</strong></label>
                      <p>Origen: dorsal #{row.player_number} · {row.is_active ? "Activo en el club" : "Inactivo en el club"} · {row.status === "active" ? "Disponible" : row.status === "injured" ? "Lesionado/a" : "No disponible"}</p>
                      <div className="season-fields-grid">
                        <FormField label="Dorsal destino" htmlFor={`copy-number-${player.id}`}><Input id={`copy-number-${player.id}`} type="number" min="1" max="99" disabled={hardBlocked} value={draft.player_number || ""} onChange={(event) => setRosterDraft((current) => ({ ...current, [player.id]: { ...current[player.id], player_number: event.target.value } }))} /></FormField>
                        <FormField label="Disponibilidad destino" htmlFor={`copy-status-${player.id}`}><Select id={`copy-status-${player.id}`} disabled={hardBlocked} value={draft.status || "active"} onChange={(event) => setRosterDraft((current) => ({ ...current, [player.id]: { ...current[player.id], status: event.target.value } }))}><option value="active">Disponible para este equipo</option><option value="injured">Lesionado/a</option><option value="inactive">No disponible para este equipo</option></Select></FormField>
                      </div>
                      {row.status === "inactive" && !hardBlocked && !draft.selected && <p className="text-muted">No se selecciona por defecto. Inclúyelo solo tras revisar su disponibilidad.</p>}
                      {issue && <p className="form-error">{issue}</p>}
                    </Card>
                  );
                })}
              </div>
              {sourcePlayers.length > 0 && <Button type="button" disabled={busy || !selectedRoster.length || hasSelectedIssues} onClick={copyRoster}>Confirmar copia revisada</Button>}
              {lastPreparedTeamId && <Link className="season-link" to={`/teams/${lastPreparedTeamId}?season=${targetId}`}>Ver Team preparado</Link>}
            </Card>
          )}

          <Card className="season-preparation-step">
            <span className="season-step-number">3</span><h3>Asignar entrenadores</h3><p>Los Coaches no se copian automáticamente. {preflight?.summary?.teams_without_coach || 0} equipos están sin entrenador.</p><Link className="season-link" to={`/categories?season=${targetId}`}>Asignar entrenadores</Link>
          </Card>

          <Card className="season-preparation-step season-preflight">
            <span className="season-step-number">4</span><h3>Revisar antes de activar</h3>
            {preflight?.mode === "recovery" && <p className="season-recovery-copy">No hay una temporada activa. Puedes revisar y activar esta temporada para recuperar la operación deportiva.</p>}
            {preflightLoading ? <p role="status">Revisando preparación...</p> : preflight ? (
              <>
                <div className="season-review-columns">
                  <div><h4>Blockers</h4>{preflight.blockers.length === 0 ? <p className="season-review-ok">Sin bloqueos.</p> : preflight.blockers.map((blocker) => <div className="season-review-item season-review-blocker" key={blocker.code}><strong>{blocker.count ? `${blocker.count} · ` : ""}{blocker.message}</strong>{blocker.action && <Link to={blocker.action.href}>{blocker.action.label}</Link>}</div>)}</div>
                  <div><h4>Warnings</h4>{preflight.warnings.length === 0 ? <p className="season-review-ok">Sin advertencias.</p> : preflight.warnings.map((warning) => <div className="season-review-item season-review-warning" key={warning.code}><strong>{warning.count ? `${warning.count} · ` : ""}{warning.message}</strong>{warning.action && <Link to={warning.action.href}>{warning.action.label}</Link>}</div>)}</div>
                </div>
                {preflight.can_activate && <Button type="button" onClick={openActivationDialog}>{preflight.warnings.length ? "Activar de todas formas" : "Activar temporada"}</Button>}
              </>
            ) : <Button type="button" variant="secondary" onClick={() => loadPreflight(targetId)}>Revisar preparación</Button>}
          </Card>
        </section>
      )}

      <section className="season-section" aria-labelledby="closed-seasons-title">
        <h2 id="closed-seasons-title">Temporadas anteriores</h2>
        {closedSeasons.length === 0 ? <p className="text-muted">Todavía no hay temporadas históricas.</p> : (
          <div className="season-history-list">
            {closedSeasons.map((season) => <Card className="season-history-card" key={season.id}><div><div className="season-card-heading"><h3>{season.name}</h3><span className="status-badge status-muted">Cerrada</span></div><SeasonMeta season={season} /></div><Link className="season-link" to={`/categories?season=${season.id}`}>Ver histórico</Link></Card>)}
          </div>
        )}
      </section>

      {showActivationDialog && preflight && <ActivationDialog preflight={preflight} busy={busy} onCancel={closeActivationDialog} onConfirm={transition} />}
    </>
  );
};
