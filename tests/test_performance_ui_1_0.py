from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAYER_DETAIL = ROOT / "src/front/js/pages/players/playerDetail.js"
SEASON_SELECTOR = ROOT / "src/front/js/component/seasonSelector.js"
ERROR_MESSAGES = ROOT / "src/front/js/utils/errorMessages.js"
STYLES = ROOT / "src/front/styles/playerDetails.css"


def _read(path):
    return path.read_text(encoding="utf-8")


def test_performance_requests_reject_stale_player_and_season_responses():
    detail = _read(PLAYER_DETAIL)

    assert "const playerRequestRef = useRef(0)" in detail
    assert "const performanceRequestRef = useRef(0)" in detail
    assert "requestedPlayerId !== currentPlayerIdRef.current" in detail
    assert "requestedSeasonId !== currentSeasonIdRef.current" in detail
    assert "requestId !== performanceRequestRef.current" in detail
    assert "loadedPlayerId !== player_id" in detail


def test_performance_has_local_loading_error_retry_and_busy_states():
    detail = _read(PLAYER_DETAIL)

    assert "performanceLoading" in detail
    assert "performanceError" in detail
    assert 'aria-busy={performanceLoading}' in detail
    assert 'role="status"' in detail
    assert 'role="alert"' in detail
    assert "onClick={loadPlayerPerformance}" in detail
    assert "setPerformanceError({" in detail


def test_performance_errors_are_distinct_from_successful_empty_state():
    detail = _read(PLAYER_DETAIL)
    errors = _read(ERROR_MESSAGES)

    for code in (
        "PLAYER_PERFORMANCE_NOT_SUPPORTED",
        "SEASON_NOT_FOUND",
        "PLAYER_NOT_FOUND",
        "FORBIDDEN",
        "NETWORK_ERROR",
    ):
        assert code in detail

    assert "Rendimiento no disponible para este deporte." in errors
    assert "performanceEmptyMessage" in detail
    assert "!performanceLoading && !performanceError && performance" in detail


def test_performance_uses_finalized_terminology_and_real_match_types():
    detail = _read(PLAYER_DETAIL)

    assert "Partidos oficiales" not in detail
    assert "Rendimiento oficial" not in detail
    assert "Partidos finalizados" in detail
    assert 'official: "Oficial"' in detail
    assert 'friendly: "Amistoso"' in detail
    assert 'scrimmage: "Scrimmage"' in detail
    assert "El rendimiento consolidado incluye todos los partidos finalizados." in detail


def test_performance_summary_uses_closed_kpis_and_backend_rates():
    detail = _read(PLAYER_DETAIL)

    for label in (
        "Partidos jugados",
        "Puntos",
        "Errores contabilizados",
        "Acciones",
        "Eficiencia y tasas",
        "Estadísticas registradas:",
    ):
        assert label in detail

    for metric in (
        "attack_efficiency",
        "attack_positive_rate",
        "reception_positive_rate",
        "defense_positive_rate",
        "set_positive_rate",
        "serve_ace_rate",
        "block_point_rate",
    ):
        assert metric in detail

    assert "Math.round" not in detail
    assert ".toFixed(" not in detail


def test_performance_keeps_provisional_zero_and_history_contracts():
    detail = _read(PLAYER_DETAIL)

    assert "Partidos provisionales" in detail
    assert "aún no forman parte del rendimiento" in detail
    assert "performance.summary.matches_played" in detail
    assert "performance.summary.matches_with_stats" in detail
    assert "performance.memberships?.length > 0" in detail
    assert "Trayectoria deportiva" in detail
    assert "selectedSeason &&" not in detail


def test_all_seasons_and_invalid_query_are_explicit_and_retryable():
    detail = _read(PLAYER_DETAIL)
    selector = _read(SEASON_SELECTOR)

    assert '"Todas las temporadas"' in detail
    assert "requestedSeasonId={requestedSeasonId}" in detail
    assert "error={seasonError}" in detail
    assert "onRetry={reloadSeasons}" in detail
    assert "invalidRequestedSeason" in selector
    assert "Temporada no disponible" in selector


def test_performance_accessibility_and_responsive_contract():
    detail = _read(PLAYER_DETAIL)
    styles = _read(STYLES)

    assert 'tabIndex={activeTab === "performance" ? 0 : -1}' in detail
    assert 'event.key === "ArrowRight"' in detail
    assert '<ul className="player-match-history">' in detail
    assert '<li className="player-match-row">' in detail
    assert '<details' in detail and '<summary>' in detail
    assert ".player-match-history" in styles
    assert ".player-match-row" in styles
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in styles


def test_performance_roles_remain_read_only_and_broad_read():
    detail = _read(PLAYER_DETAIL)

    assert '["club_owner", "coach", "staff"].includes' in detail
    assert "getPlayerPerformance" in detail
    assert "savePlayerMatchStats" not in detail
    assert "createMatchEvent" not in detail