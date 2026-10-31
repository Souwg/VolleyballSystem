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
  const requestedSeasonId = searchParams.get("season") || "";

  useEffect(() => {
    let mounted = true;

    const loadSeasons = async () => {
      setLoadingSeasons(true);
      try {
        const response = await authFetch("/api/seasons");
        const result = await parseResponse(response);

        if (mounted) {
          setSeasons(result.ok ? result.data.seasons || [] : []);
        }
      } catch (error) {
        if (mounted) setSeasons([]);
      } finally {
        if (mounted) setLoadingSeasons(false);
      }
    };

    loadSeasons();
    return () => {
      mounted = false;
    };
  }, []);

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
    requestedSeasonId,
    seasonId: requestedSeasonId || null,
    seasons,
    selectedSeason,
    selectSeason,
  };
};


export const SeasonSelector = ({
  includeAll = false,
  loading,
  onChange,
  seasons,
  selectedSeason,
}) => (
  <div className="season-filter" aria-label="Contexto de temporada">
    <label htmlFor="season-filter-select">Temporada</label>
    <Select
      id="season-filter-select"
      value={selectedSeason?.id || ""}
      onChange={(event) => onChange(event.target.value)}
      disabled={loading}
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
);
