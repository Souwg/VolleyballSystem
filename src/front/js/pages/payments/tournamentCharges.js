import React, { useContext, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Context } from "../../store/appContext";
import { PageHeader } from "../../component/ui/pageHeader";
import { Button } from "../../component/ui/button";
import { Card } from "../../component/ui/card";
import { errorMessages } from "../../utils/errorMessages";
import { formatMoney } from "../../utils/money";
import { AlertCircle, ArrowRight, CircleCheck, ReceiptText } from "lucide-react";

import "../../../styles/tournaments.css";

export const TournamentCharges = () => {
  const { actions } = useContext(Context);
  const navigate = useNavigate();

  const [entries, setEntries] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [errorCode, setErrorCode] = useState(null);

  const loadEntries = async () => {
    setLoading(true);

    const result = await actions.getTournamentRegistrationChargeContexts();

    if (result.ok) {
      setEntries(result.data.entries || []);
      setErrorCode(null);
    } else {
      setEntries([]);
      setErrorCode(result.code || "NETWORK_ERROR");
    }

    setLoading(false);
  };

  useEffect(() => {
    loadEntries();
  }, []);

  const loadPreview = async (tournamentTeamId) => {
    if (loadingPreview) return;

    setSelectedId(tournamentTeamId);
    setPreview(null);
    setErrorCode(null);
    setLoadingPreview(true);

    const result = await actions.previewRegistrationCharges(tournamentTeamId);

    if (result.ok) {
      setPreview(result.data);
    } else {
      setErrorCode(result.code || "NETWORK_ERROR");
    }

    setLoadingPreview(false);
  };

  const handleGenerate = async () => {
    if (!selectedId || !preview || generating) return;

    if (preview.existing_charges_count > 0) {
      const confirmed = window.confirm(
        "Se actualizarán los cobros pendientes con la distribución actual. Los pagos completados y los recibos generados no serán modificados. ¿Deseas continuar?",
      );

      if (!confirmed) return;
    }

    setGenerating(true);
    setErrorCode(null);

    const result = await actions.generateRegistrationCharges(selectedId);

    if (!result.ok) {
      setErrorCode(result.code || "NETWORK_ERROR");
      setGenerating(false);
      return;
    }

    await loadEntries();
    await loadPreview(selectedId);
    setGenerating(false);
  };

  const allChargesCreated =
    Boolean(preview) &&
    preview.registered_players_count > 0 &&
    preview.existing_charges_count === preview.registered_players_count;

  return (
    <div className="tournament-team-detail-page">
      <PageHeader
        variant="detail"
        tone="payments"
        icon={ReceiptText}
        eyebrow="Control financiero"
        title="Cargos de torneos"
        subtitle="Revisa la distribución y crea los cargos de inscripción autorizados por el área deportiva."
        onBack={() => navigate("/payments")}
      />

      {loading ? (
        <p>Cargando inscripciones de torneos...</p>
      ) : entries.length === 0 ? (
        <Card>
          <p>No hay equipos inscritos en torneos para gestionar.</p>
        </Card>
      ) : (
        <div className="tournament-teams-list">
          {entries.map((context) => {
            const entry = context.tournament_team;
            const isSelected = selectedId === entry.id;

            return (
              <Card key={entry.id} className="tournament-team-card">
                <div className="tournament-team-main">
                  <div className="tournament-team-info">
                    <strong>{entry.tournament?.name || "Torneo"}</strong>
                    <span>{entry.team?.name || "Equipo"}</span>
                  </div>

                  <div className="tournament-team-meta">
                    <span>
                      {context.registered_players_count} deportistas
                    </span>
                    <span>
                      {context.existing_charges_count} cargos creados
                    </span>
                    <strong>
                      {formatMoney(entry.registration_fee, entry.currency_code)}
                    </strong>
                  </div>
                </div>

                <Button
                  type="button"
                  variant={isSelected ? "secondary" : "primary"}
                  onClick={() => loadPreview(entry.id)}
                  disabled={loadingPreview && isSelected}
                >
                  {loadingPreview && isSelected
                    ? "Calculando..."
                    : "Revisar distribución"}
                </Button>
              </Card>
            );
          })}
        </div>
      )}

      {errorCode && (
        <Card className="tournament-inline-alert danger">
          <AlertCircle size={18} />
          <p>{errorMessages[errorCode] || errorMessages.NETWORK_ERROR}</p>
        </Card>
      )}

      {preview && (
        <section className="tournament-detail-section">
          <div className="tournament-section-title">
            <div>
              <h3>Distribución del costo</h3>
              <p>Confirma estos importes para crear los cargos en Pagos.</p>
            </div>
          </div>

          <Card className="tournament-charge-card">
            <div className="tournament-charge-summary">
              <div>
                <span>Monto total</span>
                <strong>
                  {formatMoney(
                    preview.registration_fee,
                    preview.currency_code,
                  )}
                </strong>
              </div>
              <div>
                <span>Deportistas</span>
                <strong>{preview.registered_players_count}</strong>
              </div>
              <div>
                <span>Cargos existentes</span>
                <strong>{preview.existing_charges_count}</strong>
              </div>
            </div>

            <div className="tournament-charge-list">
              {preview.players?.map((row) => (
                <div key={row.player_id} className="tournament-charge-row">
                  <div>
                    <strong>
                      {row.player?.first_name} {row.player?.last_name}
                    </strong>
                    <span>
                      #{row.player_number}
                      {row.existing_charge ? " · Cobro creado" : " · Por crear"}
                    </span>
                  </div>
                  <strong>
                    {formatMoney(row.amount, preview.currency_code)}
                  </strong>
                </div>
              ))}
            </div>

            {allChargesCreated ? (
              <div className="tournament-financial-actions">
                <div className="tournament-financial-success">
                  <CircleCheck size={20} />
                  <strong>Los cargos ya están creados.</strong>
                </div>
                <Button
                  type="button"
                  onClick={() =>
                    navigate(
                      `/payments?payment_type=tournament&tournament_team_id=${selectedId}`,
                    )
                  }
                >
                  Ver cobros en Pagos
                  <ArrowRight size={17} />
                </Button>
              </div>
            ) : (
              <div className="tournament-financial-actions">
                <Button
                  type="button"
                  onClick={handleGenerate}
                  disabled={generating || !preview.can_generate}
                >
                  {generating ? "Creando cobros..." : "Crear cargos"}
                </Button>
              </div>
            )}
          </Card>
        </section>
      )}
    </div>
  );
};
