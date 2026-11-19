import React, { useContext, useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { Trophy } from "lucide-react";
import { Context } from "../../store/appContext";
import { PageHeader } from "../../component/ui/pageHeader";
import { Card } from "../../component/ui/card";
import { Button } from "../../component/ui/button";
import { Select } from "../../component/ui/select";
import { ReadOnlyBadge } from "../../component/ui/readOnlyNotice";
import { canManage, isScopedCoach } from "../../utils/coachAccess";
import { errorMessages } from "../../utils/errorMessages";
import { getLocalDateOnlyValue } from "../../utils/dateOnly";
import { SeasonSelector, useSeasonSelection } from "../../component/seasonSelector";
import "../../../styles/match.css";

const MATCH_TYPE_LABELS = {
  official: "Oficial",
  friendly: "Amistoso",
  scrimmage: "Partido interno",
};

const readinessLabel = (match) => {
  if (match.is_completed) {
    if (match.result === "win") return "Victoria";
    if (match.result === "loss") return "Derrota";
    return "Finalizado";
  }
  const readiness = match.readiness;
  if (!readiness) return "Preparación pendiente";
  if (!readiness.next_action) return "Listo para finalizar";
  return `${readiness.ready_count} de ${readiness.total_steps} pasos listos`;
};

const readinessClass = (match) => {
  if (match.is_completed) {
    return match.result === "win"
      ? "status-success"
      : match.result === "loss"
      ? "status-danger"
      : "status-muted";
  }
  return match.readiness?.next_action ? "status-warning" : "status-success";
};

const MatchCard = ({ match, location }) => {
  const hasScore = match.is_completed || (match.home_sets ?? 0) > 0 || (match.opponent_sets ?? 0) > 0;
  const tournamentName = match.tournament_team?.tournament?.name;
  return (
    <Link className="match-card-link" to={`/matches/${match.id}${location.search}`} state={{ from: `${location.pathname}${location.search}` }}>
      <Card className="match-card">
        <div className="match-card-content">
          <div className="match-card-main">
            <div className="match-card-heading">
              <span className="match-card-team">{match.team_name}</span>
              {match.category_name && <span>{match.category_name}</span>}
              {!canManage(match) && <ReadOnlyBadge />}
            </div>
            <h3>vs {match.opponent_name || "Partido interno"}</h3>
            <p className="match-card-meta">
              {match.date} · {MATCH_TYPE_LABELS[match.match_type] || "Partido"}
              {tournamentName ? ` · ${tournamentName}` : ""}
            </p>
            <span className={`status-badge ${readinessClass(match)}`}>{readinessLabel(match)}</span>
          </div>
          {hasScore && (
            <span className="match-score" aria-label="Resultado en sets">
              <span className="match-score-label">Sets</span>
              <strong>{match.home_sets ?? 0}<span className="match-score-separator">–</span>{match.opponent_sets ?? 0}</strong>
            </span>
          )}
          <span className="match-card-arrow" aria-hidden="true">→</span>
        </div>
      </Card>
    </Link>
  );
};

const MatchGroup = ({ id, title, subtitle, matches, location }) => {
  if (!matches.length) return null;
  return (
    <section className="match-group" aria-labelledby={id}>
      <div className="section-header"><h2 id={id}>{title}</h2><p>{subtitle}</p></div>
      <div className="match-list">{matches.map((match) => <MatchCard key={match.id} match={match} location={location} />)}</div>
    </section>
  );
};

export const Matches = () => {
  const { store, actions } = useContext(Context);
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const [matches, setMatches] = useState([]);
  const [teams, setTeams] = useState([]);
  const [loading, setLoading] = useState(true);
  const [listError, setListError] = useState(null);
  const loadRequestId = useRef(0);
  const { loadingSeasons, reloadSeasons, seasonError, seasonId, seasons, selectedSeason, selectSeason } = useSeasonSelection();
  const teamFilter = searchParams.get("team") || "all";
  const statusFilter = searchParams.get("status") || "all";
  const tournamentFilter = searchParams.get("tournament") || "all";
  const typeFilter = searchParams.get("type") || "all";
  const selectedTeam = teams.find((team) => team.id === teamFilter);
  const canCreate = Boolean(selectedSeason?.status === "active" && selectedTeam && canManage(selectedTeam));

  const loadMatches = async () => {
    const requestId = ++loadRequestId.current;
    if (loadingSeasons) return;
    setLoading(true);
    setListError(null);
    setMatches([]);
    setTeams([]);
    if (seasonError || !selectedSeason) {
      setListError(seasonError ? { code: seasonError } : { code: "ACTIVE_SEASON_REQUIRED" });
      setLoading(false);
      return;
    }
    const [matchesResult, teamsResult] = await Promise.all([
      actions.getClubMatches({ seasonId }),
      actions.getTeams({ seasonId }),
    ]);
    if (requestId !== loadRequestId.current) return;
    if (!matchesResult.ok) {
      if (matchesResult.code !== "STALE_RESPONSE") setListError(matchesResult);
      setLoading(false);
      return;
    }
    setMatches(matchesResult.data.matches || []);
    setTeams(teamsResult.ok ? teamsResult.data.teams || [] : []);
    setLoading(false);
  };

  useEffect(() => {
    loadMatches();
    return () => { loadRequestId.current += 1; };
  }, [loadingSeasons, seasonError, seasonId, selectedSeason?.id]);

  const setFilter = (key, value) => {
    const next = new URLSearchParams(searchParams);
    if (!value || value === "all") next.delete(key);
    else next.set(key, value);
    setSearchParams(next, { replace: true });
  };

  const filteredMatches = useMemo(() => matches.filter((match) => {
    const tournamentId = match.tournament_team?.tournament?.id;
    const tournamentMatches = tournamentFilter === "all" ||
      (tournamentFilter === "independent" ? !tournamentId : tournamentId === tournamentFilter);
    return (teamFilter === "all" || match.team_id === teamFilter) &&
      (statusFilter === "all" || (statusFilter === "completed") === Boolean(match.is_completed)) &&
      tournamentMatches && (typeFilter === "all" || match.match_type === typeFilter);
  }), [matches, statusFilter, teamFilter, tournamentFilter, typeFilter]);

  const groups = useMemo(() => {
    const today = getLocalDateOnlyValue();
    const open = filteredMatches.filter((match) => !match.is_completed);
    const ascending = (a, b) => a.date.localeCompare(b.date);
    const descending = (a, b) => b.date.localeCompare(a.date);
    return {
      today: open.filter((match) => match.date === today).sort(ascending),
      pending: open.filter((match) => match.date < today).sort(descending),
      upcoming: open.filter((match) => match.date > today).sort(ascending),
      historical: filteredMatches.filter((match) => match.is_completed).sort(descending),
    };
  }, [filteredMatches]);

  const tournamentOptions = useMemo(() => {
    const options = new Map();
    matches.forEach((match) => {
      const tournament = match.tournament_team?.tournament;
      if (tournament?.id) options.set(tournament.id, tournament.name);
    });
    return [...options.entries()].sort((a, b) => a[1].localeCompare(b[1]));
  }, [matches]);

  if (loading || loadingSeasons) return <p role="status">Cargando partidos...</p>;
  const errorCode = listError?.code;
  const scopedCoach = isScopedCoach(store);

  return (
    <div className="matches-page">
      <PageHeader tone="matches" icon={Trophy} eyebrow="Calendario competitivo" title="Partidos del club" subtitle="Prepara, registra y conserva el historial de cada partido." actions={canCreate && <Button onClick={() => navigate(`/teams/${selectedTeam.id}/matches/new`)}>+ Crear partido</Button>} />
      <SeasonSelector loading={loadingSeasons} onChange={selectSeason} seasons={seasons} selectedSeason={selectedSeason} error={seasonError} onRetry={reloadSeasons} />
      {errorCode && <Card className="page-error-state" role="alert"><h2>{errorCode === "ACTIVE_SEASON_REQUIRED" ? "No hay una temporada activa" : "No pudimos cargar los partidos"}</h2><p>{errorMessages[errorCode] || listError?.message || "Ocurrió un error temporal."}</p>{errorCode !== "ACTIVE_SEASON_REQUIRED" && <Button onClick={loadMatches}>Volver a intentar</Button>}</Card>}
      {!errorCode && matches.length > 0 && (
        <Card className="match-filters" aria-label="Filtros de partidos">
          <label>Equipo<Select value={teamFilter} onChange={(event) => setFilter("team", event.target.value)}><option value="all">Todos</option>{teams.map((team) => <option key={team.id} value={team.id}>{team.name}</option>)}</Select></label>
          <label>Estado<Select value={statusFilter} onChange={(event) => setFilter("status", event.target.value)}><option value="all">Todos</option><option value="open">Abiertos</option><option value="completed">Históricos</option></Select></label>
          <label>Torneo<Select value={tournamentFilter} onChange={(event) => setFilter("tournament", event.target.value)}><option value="all">Todos</option><option value="independent">Independientes</option>{tournamentOptions.map(([id, name]) => <option key={id} value={id}>{name}</option>)}</Select></label>
          <label>Tipo<Select value={typeFilter} onChange={(event) => setFilter("type", event.target.value)}><option value="all">Todos</option><option value="official">Oficial</option><option value="friendly">Amistoso</option><option value="scrimmage">Interno</option></Select></label>
        </Card>
      )}
      {!errorCode && !filteredMatches.length && <Card><div className="empty-state"><Trophy size={30} aria-hidden="true" /><h2>{matches.length ? "No hay partidos con estos filtros" : "No hay partidos en esta temporada"}</h2><p>{canCreate ? "Crea el primer partido del equipo seleccionado." : scopedCoach ? "Los partidos de tus equipos aparecerán aquí." : "Selecciona un equipo para crear un partido."}</p></div></Card>}
      {!errorCode && filteredMatches.length > 0 && <div className="match-groups">
        <MatchGroup id="matches-today" title="Hoy" subtitle="Partidos programados para hoy." matches={groups.today} location={location} />
        <MatchGroup id="matches-pending" title="Pendientes" subtitle="Partidos pasados que todavía requieren cierre." matches={groups.pending} location={location} />
        <MatchGroup id="matches-upcoming" title="Próximos" subtitle="Partidos futuros en orden cronológico." matches={groups.upcoming} location={location} />
        <MatchGroup id="matches-history" title="Históricos" subtitle="Partidos completados y de solo lectura." matches={groups.historical} location={location} />
      </div>}
    </div>
  );
};
