import React, { useCallback, useContext, useEffect, useMemo, useState } from "react";
import { Context } from "../../store/appContext";
import { PageHeader } from "../../component/ui/pageHeader";
import { Card } from "../../component/ui/card";
import { Button } from "../../component/ui/button";
import { Input } from "../../component/ui/input";
import { Select } from "../../component/ui/select";
import { FormField } from "../../component/ui/formField";
import { authFetch, parseResponse } from "../../utils/authFetch";
import { errorMessages } from "../../utils/errorMessages";

const request = async (path, options = {}) => {
  const response = await authFetch(path, options);
  return parseResponse(response);
};

const seasonStatus = {
  active: "Activa",
  planned: "Planificada",
  closed: "Cerrada",
};

export const Seasons = () => {
  const { store } = useContext(Context);
  const [seasons, setSeasons] = useState([]);
  const [details, setDetails] = useState({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [form, setForm] = useState({ name: "", start_date: "", end_date: "" });
  const [targetId, setTargetId] = useState("");
  const [selectedTeams, setSelectedTeams] = useState([]);
  const [sourceTeamId, setSourceTeamId] = useState("");
  const [targetTeamId, setTargetTeamId] = useState("");
  const [sourcePlayers, setSourcePlayers] = useState([]);
  const [selectedPlayers, setSelectedPlayers] = useState([]);

  const activeSeason = useMemo(
    () => seasons.find((season) => season.status === "active"),
    [seasons]
  );
  const plannedSeasons = useMemo(
    () => seasons.filter((season) => season.status === "planned"),
    [seasons]
  );
  const targetSeason = details[targetId];
  const sourceSeason = activeSeason ? details[activeSeason.id] : null;

  const loadDetail = useCallback(async (seasonId) => {
    if (!seasonId) return null;
    const result = await request(`/api/seasons/${seasonId}`);
    if (!result.ok) return null;
    setDetails((current) => ({ ...current, [seasonId]: result.data.season }));
    return result.data.season;
  }, []);

  const loadSeasons = useCallback(async () => {
    setLoading(true);
    const result = await request("/api/seasons");
    if (result.ok) {
      const rows = result.data.seasons || [];
      setSeasons(rows);
      const active = rows.find((season) => season.status === "active");
      const planned = rows.find((season) => season.status === "planned");
      if (active) await loadDetail(active.id);
      if (planned) {
        setTargetId((current) => current || planned.id);
        await loadDetail(planned.id);
      }
    } else {
      setError(result.message || "No pudimos cargar las temporadas.");
    }
    setLoading(false);
  }, [loadDetail]);

  useEffect(() => {
    loadSeasons();
  }, [loadSeasons]);

  useEffect(() => {
    if (targetId) loadDetail(targetId);
    setSelectedTeams([]);
    setSourceTeamId("");
    setTargetTeamId("");
    setSourcePlayers([]);
    setSelectedPlayers([]);
  }, [targetId, loadDetail]);

  const run = async (callback, successMessage) => {
    if (busy) return;
    setBusy(true);
    setError("");
    setMessage("");
    const result = await callback();
    if (!result.ok) {
      setError(errorMessages[result.code] || result.message || "No pudimos completar la acción.");
      setBusy(false);
      return false;
    }
    setMessage(successMessage);
    await loadSeasons();
    setBusy(false);
    return true;
  };

  const createSeason = async (event) => {
    event.preventDefault();
    const ok = await run(
      () => request("/api/seasons", { method: "POST", body: JSON.stringify(form) }),
      "La próxima temporada quedó creada como planificada."
    );
    if (ok) setForm({ name: "", start_date: "", end_date: "" });
  };

  const duplicateTeams = async () => {
    if (!activeSeason || !targetId) return;
    const ok = await run(
      () => request(`/api/seasons/${targetId}/teams/duplicate`, {
        method: "POST",
        body: JSON.stringify({
          source_season_id: activeSeason.id,
          team_ids: selectedTeams,
        }),
      }),
      "Los equipos seleccionados quedaron preparados."
    );
    if (ok) setSelectedTeams([]);
  };

  const loadRoster = async () => {
    if (!sourceTeamId) return;
    setError("");
    const result = await request(`/api/teams/${sourceTeamId}/players`);
    if (!result.ok) {
      setError(result.message || "No pudimos cargar el roster.");
      return;
    }
    setSourcePlayers(result.data.players || []);
    setSelectedPlayers([]);
  };

  const copyRoster = async () => {
    const ok = await run(
      () => request(`/api/teams/${targetTeamId}/roster/copy`, {
        method: "POST",
        body: JSON.stringify({ source_team_id: sourceTeamId, player_ids: selectedPlayers }),
      }),
      "El roster seleccionado quedó preparado."
    );
    if (ok) {
      setSourcePlayers([]);
      setSelectedPlayers([]);
      await loadDetail(targetId);
    }
  };

  const transition = async () => {
    if (!activeSeason || !targetId) return;
    await run(
      () => request(`/api/seasons/${targetId}/transition`, {
        method: "POST",
        body: JSON.stringify({ source_season_id: activeSeason.id }),
      }),
      "La nueva temporada está activa."
    );
  };

  if (loading) return <p>Cargando temporadas...</p>;

  if (store.user?.role !== "club_owner") {
    return <p>Solo el dueño del club puede preparar temporadas.</p>;
  }

  return (
    <>
      <PageHeader
        title="Temporadas"
        subtitle="Prepara la próxima estructura sin interrumpir la temporada actual."
      />

      {error && <p className="form-error">{error}</p>}
      {message && <p>{message}</p>}

      <div className="form-grid">
        <Card>
          <h3>Temporadas del club</h3>
          {seasons.map((season) => (
            <p key={season.id}>
              <strong>{season.name}</strong> · {seasonStatus[season.status] || season.status}
              {season.total_teams !== undefined ? ` · ${season.total_teams} equipos` : ""}
            </p>
          ))}
        </Card>

        <Card>
          <h3>Crear próxima temporada</h3>
          <form onSubmit={createSeason} className="form">
            <FormField label="Nombre">
              <Input value={form.name} required onChange={(event) => setForm({ ...form, name: event.target.value })} />
            </FormField>
            <FormField label="Fecha de inicio">
              <Input type="date" value={form.start_date} required onChange={(event) => setForm({ ...form, start_date: event.target.value })} />
            </FormField>
            <FormField label="Fecha final (opcional)">
              <Input type="date" value={form.end_date} onChange={(event) => setForm({ ...form, end_date: event.target.value })} />
            </FormField>
            <Button type="submit" disabled={busy}>Crear planificada</Button>
          </form>
        </Card>
      </div>

      {plannedSeasons.length > 0 && activeSeason && (
        <Card>
          <h3>Preparar próxima temporada</h3>
          <FormField label="Temporada destino">
            <Select value={targetId} onChange={(event) => setTargetId(event.target.value)}>
              {plannedSeasons.map((season) => <option key={season.id} value={season.id}>{season.name}</option>)}
            </Select>
          </FormField>

          <h4>1. Duplicar equipos desde {activeSeason.name}</h4>
          {(sourceSeason?.teams || []).filter((team) => team.status === "active").map((team) => (
            <label key={team.id} className="checkbox-row">
              <input
                type="checkbox"
                checked={selectedTeams.includes(team.id)}
                onChange={() => setSelectedTeams((rows) => rows.includes(team.id) ? rows.filter((id) => id !== team.id) : [...rows, team.id])}
              />
              {team.name} · {team.category?.name || "Sin categoría"}
            </label>
          ))}
          <Button type="button" disabled={busy || !selectedTeams.length} onClick={duplicateTeams}>Duplicar seleccionados</Button>

          <h4>2. Seleccionar roster</h4>
          <div className="form-grid">
            <FormField label="Equipo origen">
              <Select value={sourceTeamId} onChange={(event) => setSourceTeamId(event.target.value)}>
                <option value="">Selecciona</option>
                {(sourceSeason?.teams || []).map((team) => <option key={team.id} value={team.id}>{team.name}</option>)}
              </Select>
            </FormField>
            <FormField label="Equipo destino">
              <Select value={targetTeamId} onChange={(event) => setTargetTeamId(event.target.value)}>
                <option value="">Selecciona</option>
                {(targetSeason?.teams || []).filter((team) => team.status === "active").map((team) => <option key={team.id} value={team.id}>{team.name}</option>)}
              </Select>
            </FormField>
          </div>
          <Button type="button" variant="secondary" disabled={!sourceTeamId} onClick={loadRoster}>Cargar roster</Button>
          {sourcePlayers.map((row) => {
            const player = row.player || row;
            return (
              <label key={player.id} className="checkbox-row">
                <input
                  type="checkbox"
                  checked={selectedPlayers.includes(player.id)}
                  onChange={() => setSelectedPlayers((rows) => rows.includes(player.id) ? rows.filter((id) => id !== player.id) : [...rows, player.id])}
                />
                #{row.player_number} {player.first_name} {player.last_name}
              </label>
            );
          })}
          {sourcePlayers.length > 0 && (
            <Button type="button" disabled={busy || !targetTeamId || !selectedPlayers.length} onClick={copyRoster}>Copiar seleccionadas</Button>
          )}

          <h4>3. Activar nueva temporada</h4>
          <p>La transición cerrará {activeSeason.name} y activará {targetSeason?.name}. No modifica equipos ni memberships históricas.</p>
          <Button type="button" disabled={busy || !(targetSeason?.active_teams > 0)} onClick={transition}>Activar nueva temporada</Button>
        </Card>
      )}
    </>
  );
};
