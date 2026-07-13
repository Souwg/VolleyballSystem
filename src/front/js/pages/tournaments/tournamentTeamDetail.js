import React, { useContext, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Context } from "../../store/appContext";
import { PageHeader } from "../../component/ui/pageHeader";
import { Button } from "../../component/ui/button";
import { Card } from "../../component/ui/card";
import { errorMessages } from "../../utils/errorMessages";
import {
  Users,
  Check,
  AlertCircle,
  ArrowRight,
  CircleCheck,
} from "lucide-react";

import "../../../styles/tournaments.css";

const formatCurrency = (value) => {
  return Number(value || 0).toLocaleString("es", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
  });
};

const getPaymentStatus = (status) => {
  const statuses = {
    pending: {
      label: "Pendiente",
      className: "status-warning",
    },
    paid: {
      label: "Pagado",
      className: "status-success",
    },
    overdue: {
      label: "Vencido",
      className: "status-danger",
    },
    cancelled: {
      label: "Cancelado",
      className: "status-muted",
    },
  };

  return (
    statuses[status] || {
      label: status || "Sin estado",
      className: "status-muted",
    }
  );
};

export const TournamentTeamDetail = () => {
  const { actions } = useContext(Context);
  const { tournament_team_id } = useParams();
  const navigate = useNavigate();

  const [tournamentTeam, setTournamentTeam] = useState(null);
  const [players, setPlayers] = useState([]);
  const [selectedPlayerIds, setSelectedPlayerIds] = useState([]);
  const [preview, setPreview] = useState(null);

  const [loadingPage, setLoadingPage] = useState(true);
  const [savingPlayers, setSavingPlayers] = useState(false);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [generatingCharges, setGeneratingCharges] = useState(false);

  const [errors, setErrors] = useState({});
  const [selectionChanged, setSelectionChanged] = useState(false);
  const [showOnlySelected, setShowOnlySelected] = useState(false);
  const [showPlayerList, setShowPlayerList] = useState(false);
  const [showChargeDetails, setShowChargeDetails] = useState(false);

  const loadTournamentPlayers = async () => {
    setLoadingPage(true);

    try {
      const result = await actions.getTournamentTeamPlayers(tournament_team_id);

      if (!result.ok) {
        setTournamentTeam(null);
        setPlayers([]);
        return;
      }

      const loadedPlayers = result.data.players || [];

      setTournamentTeam(result.data.tournament_team);
      setPlayers(loadedPlayers);

      setSelectedPlayerIds(
        loadedPlayers
          .filter((row) => row.is_registered)
          .map((row) => row.player_id),
      );

      setSelectionChanged(false);
      setShowPlayerList(false);
      setShowOnlySelected(false);
    } finally {
      setLoadingPage(false);
    }
  };

  useEffect(() => {
    loadTournamentPlayers();

    return () => {
      setPreview(null);
    };
  }, [tournament_team_id]);

  const registeredCount = selectedPlayerIds.length;

  const selectablePlayers = useMemo(
    () =>
      players.filter(
        (row) =>
          row.team_status === "active" && row.player?.is_active !== false,
      ),
    [players],
  );

  const visiblePlayers = useMemo(() => {
    if (!showOnlySelected) return players;

    return players.filter((row) => selectedPlayerIds.includes(row.player_id));
  }, [players, selectedPlayerIds, showOnlySelected]);

  const registrationFee = Number(tournamentTeam?.registration_fee || 0);

  const estimatedAmountPerPlayer = useMemo(() => {
    if (registeredCount === 0) return 0;

    return registrationFee / registeredCount;
  }, [registrationFee, registeredCount]);

  const existingChargesCount = preview?.existing_charges_count || 0;

  const allChargesCreated =
    Boolean(preview) &&
    preview.registered_players_count > 0 &&
    existingChargesCount === preview.registered_players_count;

  const clearErrors = (...codes) => {
    setErrors((previousErrors) => {
      const updatedErrors = { ...previousErrors };

      codes.forEach((code) => {
        updatedErrors[code] = false;
      });

      return updatedErrors;
    });
  };

  const togglePlayer = (playerId) => {
    setShowPlayerList(true);
    setSelectedPlayerIds((currentIds) => {
      const isSelected = currentIds.includes(playerId);

      return isSelected
        ? currentIds.filter((id) => id !== playerId)
        : [...currentIds, playerId];
    });

    setSelectionChanged(true);
    setPreview(null);

    clearErrors(
      "TOURNAMENT_PLAYERS_REQUIRED",
      "INVALID_TOURNAMENT_PLAYERS",
      "PLAYER_NOT_IN_TEAM",
    );
  };

  const selectAllPlayers = () => {
    const selectableIds = players
      .filter(
        (row) =>
          row.team_status === "active" && row.player?.is_active !== false,
      )
      .map((row) => row.player_id);

    setSelectedPlayerIds(selectableIds);
    setSelectionChanged(true);
    setPreview(null);
  };

  const clearSelection = () => {
    setSelectedPlayerIds([]);
    setSelectionChanged(true);
    setPreview(null);
  };

  const handleSavePlayers = async () => {
    if (savingPlayers) return;

    setErrors({});
    setSavingPlayers(true);

    const result = await actions.updateTournamentTeamPlayers(
      tournament_team_id,
      selectedPlayerIds,
    );

    setSavingPlayers(false);

    if (!result.ok) {
      setErrors({
        [result.code || "NETWORK_ERROR"]: true,
      });

      return;
    }

    await loadTournamentPlayers();
    setPreview(null);
  };

  const handleLoadPreview = async () => {
    if (loadingPreview) return;

    clearErrors(
      "TOURNAMENT_PLAYERS_REQUIRED",
      "INVALID_TOURNAMENT_REGISTRATION_FEE",
      "TOURNAMENT_REGISTRATION_CHARGES_LOCKED",
      "NETWORK_ERROR",
      "FORBIDDEN",
    );

    setLoadingPreview(true);

    const result = await actions.previewRegistrationCharges(tournament_team_id);

    setLoadingPreview(false);

    if (!result.ok) {
      setErrors((previousErrors) => ({
        ...previousErrors,
        [result.code || "NETWORK_ERROR"]: true,
      }));

      setPreview(null);
      return;
    }

    setPreview(result.data);
  };

  useEffect(() => {
    const canLoadPreview =
      !loadingPage &&
      !selectionChanged &&
      registeredCount > 0 &&
      registrationFee > 0;

    if (!canLoadPreview) {
      setPreview(null);
      setShowChargeDetails(false);
      return;
    }

    handleLoadPreview();
  }, [
    loadingPage,
    selectionChanged,
    registeredCount,
    registrationFee,
    tournament_team_id,
  ]);

  const handleGenerateCharges = async () => {
    if (generatingCharges || !preview) return;

    if (preview.existing_charges_count > 0) {
      const confirmed = window.confirm(
        "Se actualizarán los cobros pendientes con la distribución actual. Los pagos completados y los recibos generados no serán modificados. ¿Deseas continuar?",
      );

      if (!confirmed) return;
    }

    setErrors({});
    setGeneratingCharges(true);

    const result = await actions.generateRegistrationCharges(
      tournament_team_id,
    );

    setGeneratingCharges(false);

    if (!result.ok) {
      setErrors({
        [result.code || "NETWORK_ERROR"]: true,
      });

      return;
    }

    const previewResult = await actions.previewRegistrationCharges(
      tournament_team_id,
    );

    if (previewResult.ok) {
      setPreview(previewResult.data);
      setShowChargeDetails(false);
    }
  };

  const handleGoToPayments = () => {
    navigate(
      `/payments?payment_type=tournament&tournament_team_id=${tournament_team_id}`,
    );
  };

  if (loadingPage) {
    return <p>Cargando inscripción del equipo...</p>;
  }

  if (!tournamentTeam) {
    return <p>Participación de torneo no encontrada.</p>;
  }

  const tournament = tournamentTeam.tournament;
  const team = tournamentTeam.team;

  const canEditPlayers =
    tournamentTeam.status === "active" && tournament?.status === "active";

  return (
    <div className="tournament-team-detail-page">
      <PageHeader
        variant="detail"
        eyebrow={tournament?.name || "Torneo"}
        title={team?.name || "Equipo"}
        subtitle={`${registeredCount} ${
          registeredCount === 1
            ? "deportista inscrita"
            : "deportistas inscritas"
        }`}
        onBack={() => navigate(`/tournaments/${tournamentTeam.tournament_id}`)}
      />

      <section className="tournament-detail-section">
        <div className="tournament-section-title">
          <span className="tournament-section-step">1</span>

          <div>
            <h3>Deportistas inscritas</h3>
            <p>Selecciona quiénes representarán al equipo en este torneo.</p>
          </div>
        </div>

        <Card className="tournament-player-selection-card">
          <div className="tournament-selection-header">
            <div>
              <h4>Plantilla del torneo</h4>

              <p>
                Solo las deportistas guardadas aquí estarán disponibles en los
                partidos de este torneo.
              </p>
            </div>

            {canEditPlayers && (
              <div className="tournament-selection-toolbar">
                <div className="tournament-selection-count">
                  <strong>{registeredCount}</strong>
                  <span>de {selectablePlayers.length} seleccionadas</span>
                </div>

                <div className="tournament-selection-links">
                  <button
                    type="button"
                    onClick={selectAllPlayers}
                    disabled={registeredCount === selectablePlayers.length}
                  >
                    Seleccionar todas
                  </button>

                  <button
                    type="button"
                    onClick={clearSelection}
                    disabled={registeredCount === 0}
                  >
                    Limpiar
                  </button>
                </div>
              </div>
            )}

            {players.length > 0 && (
              <div className="tournament-roster-controls">
                <button
                  type="button"
                  className="tournament-roster-toggle"
                  onClick={() => {
                    setShowPlayerList((current) => !current);
                    setShowOnlySelected(false);
                  }}
                >
                  {showPlayerList ? "Ocultar plantilla" : "Ver plantilla"}
                </button>

                {showPlayerList && registeredCount > 0 && (
                  <button
                    type="button"
                    className={`tournament-selected-filter ${
                      showOnlySelected ? "active" : ""
                    }`}
                    onClick={() => setShowOnlySelected((current) => !current)}
                  >
                    {showOnlySelected ? "Mostrar todas" : "Solo seleccionadas"}
                  </button>
                )}
              </div>
            )}
          </div>

          {players.length === 0 ? (
            <div className="empty-state">
              <Users size={30} />

              <h4>El equipo no tiene deportistas</h4>

              <p>Primero debes agregar deportistas al equipo.</p>
            </div>
          ) : showPlayerList ? (
            <div className="tournament-player-list">
              {visiblePlayers.map((row) => {
                const isSelected = selectedPlayerIds.includes(row.player_id);

                const isUnavailable =
                  !canEditPlayers ||
                  row.team_status !== "active" ||
                  row.player?.is_active === false;

                return (
                  <button
                    type="button"
                    key={row.player_id}
                    className={`tournament-player-option ${
                      isSelected ? "selected" : ""
                    }`}
                    disabled={isUnavailable}
                    onClick={() => togglePlayer(row.player_id)}
                  >
                    <div className="tournament-player-check">
                      {isSelected && <Check size={16} />}
                    </div>

                    <div className="tournament-player-copy">
                      <strong>
                        {row.player?.first_name} {row.player?.last_name}
                      </strong>

                      <span>
                        #{row.player_number}
                        {row.player?.main_position
                          ? ` · ${row.player.main_position}`
                          : ""}
                      </span>
                    </div>

                    {isUnavailable && (
                      <span className="status-badge status-muted">
                        No disponible
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          ) : null}

          {errors.TOURNAMENT_PLAYERS_FINANCIALLY_LOCKED && (
            <div className="tournament-inline-alert danger">
              <AlertCircle size={18} />

              <p>{errorMessages.TOURNAMENT_PLAYERS_FINANCIALLY_LOCKED}</p>
            </div>
          )}

          {errors.INVALID_TOURNAMENT_PLAYERS && (
            <p className="form-error">
              {errorMessages.INVALID_TOURNAMENT_PLAYERS}
            </p>
          )}

          {errors.PLAYER_NOT_IN_TEAM && (
            <p className="form-error">{errorMessages.PLAYER_NOT_IN_TEAM}</p>
          )}

          {selectionChanged && !errors.TOURNAMENT_PLAYERS_FINANCIALLY_LOCKED && (
            <div className="tournament-unsaved-notice">
              <AlertCircle size={17} />
              <span>Tienes cambios sin guardar.</span>
            </div>
          )}

          {canEditPlayers && (
            <div className="form-actions tournament-selection-actions">
              {errors.TOURNAMENT_PLAYERS_FINANCIALLY_LOCKED ? (
                <Button
                  type="button"
                  variant="secondary"
                  onClick={loadTournamentPlayers}
                >
                  Restaurar selección
                </Button>
              ) : (
                <Button
                  type="button"
                  onClick={handleSavePlayers}
                  disabled={
                    savingPlayers || !selectionChanged || players.length === 0
                  }
                >
                  {savingPlayers ? "Guardando..." : "Guardar deportistas"}
                </Button>
              )}
            </div>
          )}
        </Card>
      </section>

      <section className="tournament-detail-section">
        <div className="tournament-section-title">
          <span className="tournament-section-step">2</span>

          <div>
            <h3>Distribución del costo</h3>
            <p>
              Revisa cómo se distribuirá la inscripción entre las deportistas
              guardadas.
            </p>
          </div>
        </div>

        <Card className="tournament-cost-summary-card">
          <div>
            <span>Inscripción del equipo</span>
            <strong>{formatCurrency(registrationFee)}</strong>
          </div>

          <div>
            <span>Deportistas</span>
            <strong>{registeredCount}</strong>
          </div>

          <div>
            <span>Por deportista</span>
            <strong>
              {registeredCount > 0
                ? formatCurrency(estimatedAmountPerPlayer)
                : "—"}
            </strong>
          </div>
        </Card>

        <Card className="tournament-charge-card">
          <div className="tournament-charge-heading">
            <div>
              <h4>Cobros por deportista</h4>

              <p>
                El costo se divide automáticamente entre las deportistas
                guardadas. Confirma para crear los cobros en Pagos.
              </p>
            </div>
          </div>

          {selectionChanged && (
            <div className="tournament-inline-alert">
              <AlertCircle size={18} />

              <p>Guarda la plantilla para calcular la nueva distribución.</p>
            </div>
          )}

          {!selectionChanged && registeredCount === 0 && (
            <div className="tournament-inline-alert">
              <AlertCircle size={18} />

              <p>Selecciona y guarda al menos una deportista.</p>
            </div>
          )}

          {registrationFee <= 0 && (
            <div className="tournament-inline-alert">
              <AlertCircle size={18} />

              <p>
                Este equipo no tiene un costo de inscripción mayor que cero.
              </p>
            </div>
          )}

          {loadingPreview && (
            <div className="tournament-charge-loading">
              Calculando distribución...
            </div>
          )}

          {errors.TOURNAMENT_PLAYERS_REQUIRED && (
            <p className="form-error">
              {errorMessages.TOURNAMENT_PLAYERS_REQUIRED}
            </p>
          )}

          {errors.INVALID_TOURNAMENT_REGISTRATION_FEE && (
            <p className="form-error">
              {errorMessages.INVALID_TOURNAMENT_REGISTRATION_FEE}
            </p>
          )}

          {errors.TOURNAMENT_REGISTRATION_CHARGES_LOCKED && (
            <div className="tournament-inline-alert danger">
              <AlertCircle size={18} />

              <p>{errorMessages.TOURNAMENT_REGISTRATION_CHARGES_LOCKED}</p>
            </div>
          )}

          {preview && (
            <>
              {allChargesCreated ? (
                <div className="tournament-financial-success">
                  <div className="tournament-financial-success-icon">
                    <CircleCheck size={20} />
                  </div>

                  <div>
                    <strong>
                      {existingChargesCount}{" "}
                      {existingChargesCount === 1
                        ? "cobro creado"
                        : "cobros creados"}
                    </strong>

                    <span>Los pagos y recibos se administran desde Pagos.</span>
                  </div>
                </div>
              ) : (
                <div className="tournament-distribution-ready">
                  <span>Distribución lista</span>

                  <strong>
                    {preview.registered_players_count}{" "}
                    {preview.registered_players_count === 1
                      ? "cobro"
                      : "cobros"}{" "}
                    de {formatCurrency(estimatedAmountPerPlayer)}
                  </strong>
                </div>
              )}

              <div className="tournament-charge-summary">
                <div>
                  <span>Monto total</span>
                  <strong>{formatCurrency(preview.registration_fee)}</strong>
                </div>

                <div>
                  <span>Deportistas</span>
                  <strong>{preview.registered_players_count}</strong>
                </div>

                <div>
                  <span>Por deportista</span>
                  <strong>{formatCurrency(estimatedAmountPerPlayer)}</strong>
                </div>
              </div>

              {preview.players?.length > 0 && (
                <button
                  type="button"
                  className="tournament-charge-details-toggle"
                  onClick={() => setShowChargeDetails((current) => !current)}
                >
                  {showChargeDetails
                    ? "Ocultar detalle"
                    : "Ver detalle de cobros"}
                </button>
              )}

              {showChargeDetails && (
                <div className="tournament-charge-list">
                  {preview.players?.map((row) => {
                    const paymentStatus = row.existing_charge
                      ? getPaymentStatus(row.existing_charge.status)
                      : null;

                    return (
                      <div
                        key={row.player_id}
                        className="tournament-charge-row"
                      >
                        <div>
                          <strong>
                            {row.player?.first_name} {row.player?.last_name}
                          </strong>

                          <span>
                            #{row.player_number}
                            {row.existing_charge
                              ? " · Cobro creado"
                              : " · Por crear"}
                          </span>
                        </div>

                        <div className="tournament-charge-row-side">
                          {paymentStatus && (
                            <span
                              className={`status-badge ${paymentStatus.className}`}
                            >
                              {paymentStatus.label}
                            </span>
                          )}

                          <strong>{formatCurrency(row.amount)}</strong>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              <div className="tournament-financial-actions">
                {!allChargesCreated ? (
                  <Button
                    type="button"
                    onClick={handleGenerateCharges}
                    disabled={generatingCharges || !preview.can_generate}
                  >
                    {generatingCharges
                      ? "Creando cobros..."
                      : `Crear ${preview.registered_players_count} ${
                          preview.registered_players_count === 1
                            ? "cobro"
                            : "cobros"
                        } de ${formatCurrency(estimatedAmountPerPlayer)}`}
                  </Button>
                ) : (
                  <Button type="button" onClick={handleGoToPayments}>
                    Ver cobros en Pagos
                    <ArrowRight size={17} />
                  </Button>
                )}
              </div>
            </>
          )}

          {(errors.NETWORK_ERROR || errors.FORBIDDEN) && (
            <p className="form-error">
              {errors.NETWORK_ERROR
                ? errorMessages.NETWORK_ERROR
                : errorMessages.FORBIDDEN}
            </p>
          )}
        </Card>
      </section>
    </div>
  );
};
