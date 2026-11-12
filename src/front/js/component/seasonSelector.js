import React, { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { Select } from "./ui/select";
import { authFetch, parseResponse } from "../utils/authFetch";


const STATUS_LABELS = {
  active: "Activa",
  planned: "Planificada",
  closed: "Cerrada",
};


export const useSeasonSelection = ({ defaultToActive = true } = {}) => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [seasons, setSeasons] = useState([]);
  const [loadingSeasons, setLoadingSeasons] = useState(true);
  const [seasonError, setSeasonError] = useState(null);
  const [retryKey, setRetryKey] = useState(0);
  const requestedSeasonId = searchParams.get("season") || "";

  useEffect(() => {
    let mounted = true;

    const loadSeasons = async () => {
      setLoadingSeasons(true);
      setSeasonError(null);
      try {
        const response = await authFetch("/api/seasons");
        const result = await parseResponse(response);

        if (mounted) {
          setSeasons(result.ok ? result.data.seasons || [] : []);
          setSeasonError(result.ok ? null : result.code || "HTTP_ERROR");
        }
      } catch (error) {
        if (mounted) {
          setSeasons([]);
          setSeasonError("NETWORK_ERROR");
        }
      } finally {
        if (mounted) setLoadingSeasons(false);
      }
    };

    loadSeasons();
    return () => {
      mounted = false;
    };
  }, [retryKey]);

  const activeSeason = useMemo(
    () => seasons.find((season) => season.status === "active") || null,
    [seasons],
  );
  const selectedSeason = useMemo(() => {
    if (requestedSeasonId) {
      return seasons.find((season) => season.id === requestedSeasonId) || null;
    }

    return defaultToActive ? activeSeason : null;
  }, [activeSeason, defaultToActive, requestedSeasonId, seasons]);

  const selectSeason = (seasonId) => {
    const next = new URLSearchParams(searchParams);
    const target = seasons.find((season) => season.id === seasonId);

    if (
      !seasonId ||
      (defaultToActive && target && target.status === "active")
    ) {
      next.delete("season");
    } else {
      next.set("season", seasonId);
    }

    setSearchParams(next, { replace: true });
  };

  return {
    activeSeason,
    loadingSeasons,
    reloadSeasons: () => setRetryKey((current) => current + 1),
    requestedSeasonId,
    seasonId: requestedSeasonId || null,
    seasons,
    selectedSeason,
    seasonError,
    selectSeason,
  };
};


export const SeasonSelector = ({
  includeAll = false,
  loading,
  onChange,
  onRetry,
  seasons,
  selectedSeason,
  error,
}) => (
  <>
    <div className="season-filter" aria-label="Contexto de temporada">
      <label htmlFor="season-filter-select">Temporada</label>
      <Select
        id="season-filter-select"
        value={selectedSeason?.id || ""}
        onChange={(event) => onChange(event.target.value)}
        disabled={loading || Boolean(error)}
      >
        {includeAll && <option value="">Todas las temporadas</option>}
        {!includeAll && !selectedSeason && (
          <option value="">Sin temporada activa</option>
        )}
        {seasons.map((season) => (
          <option key={season.id} value={season.id}>
            {season.name} — {STATUS_LABELS[season.status] || season.status}
          </option>
        ))}
      </Select>
      {selectedSeason?.status === "closed" && (
        <span className="status-badge status-muted">Temporada cerrada</span>
      )}
      {selectedSeason?.status === "planned" && (
        <span className="status-badge status-info">Temporada planificada</span>
      )}
    </div>
    {error && (
      <div className="season-load-error" role="alert">
        <p>No se pudieron cargar las temporadas.</p>
        {onRetry && (
          <button type="button" onClick={onRetry}>
            Volver a intentar
          </button>
        )}
      </div>
    )}
  </>
);
