import React, { useState, useContext, useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Context } from "../../store/appContext";
import { StatCounter } from "../../component/ui/statCounter";
import { PageHeader } from "../../component/ui/pageHeader";
import { Card } from "../../component/ui/card";
import { Input } from "../../component/ui/input";
import { Button } from "../../component/ui/button";

export const PlayerMatchStats = () => {
  const { actions } = useContext(Context);
  const { match_player_id } = useParams();
  const navigate = useNavigate();

  const [position, setPosition] = useState("");
  const [attacksTotal, setAttacksTotal] = useState(0);
  const [attacksPositive, setAttacksPositive] = useState(0);
  const [attacksErrors, setAttacksErrors] = useState(0);

  const [receptionsTotal, setReceptionsTotal] = useState(0);
  const [receptionsPositive, setReceptionsPositive] = useState(0);
  const [receptionsNegative, setReceptionsNegative] = useState(0);

  const [servesTotal, setServesTotal] = useState(0);
  const [servesAces, setServesAces] = useState(0);
  const [servesErrors, setServesErrors] = useState(0);

  const [blocksTotal, setBlocksTotal] = useState(0);
  const [blocksPoints, setBlocksPoints] = useState(0);
  const [loading, setLoading] = useState(false);

  const loadStats = async () => {
    const result = await actions.getPlayerMatchStats(match_player_id);

    if (!result.ok) return;

    const stats = result.data;

    setPosition(stats.position || "");

    setAttacksTotal(stats.attacks_total || 0);
    setAttacksPositive(stats.attacks_positive || 0);
    setAttacksErrors(stats.attacks_errors || 0);

    setReceptionsTotal(stats.receptions_total || 0);
    setReceptionsPositive(stats.receptions_positive || 0);
    setReceptionsNegative(stats.receptions_negative || 0);

    setServesTotal(stats.serves_total || 0);
    setServesAces(stats.serves_aces || 0);
    setServesErrors(stats.serves_errors || 0);

    setBlocksTotal(stats.blocks_total || 0);
    setBlocksPoints(stats.blocks_points || 0);
  };

  useEffect(() => {
    loadStats();
  }, [match_player_id]);

  const handleSave = async () => {
    setLoading(true);

    const result = await actions.savePlayerMatchStats(match_player_id, {
      position,

      attacks_total: attacksTotal,
      attacks_positive: attacksPositive,
      attacks_errors: attacksErrors,

      receptions_total: receptionsTotal,
      receptions_positive: receptionsPositive,
      receptions_negative: receptionsNegative,

      serves_total: servesTotal,
      serves_aces: servesAces,
      serves_errors: servesErrors,

      blocks_total: blocksTotal,
      blocks_points: blocksPoints,
    });

    setLoading(false);

    if (!result.ok) return;

    navigate(-1);
  };

  const attackEfficiency =
    attacksTotal > 0 ? Math.round((attacksPositive / attacksTotal) * 100) : 0;

  const attackErrorRate =
    attacksTotal > 0 ? Math.round((attacksErrors / attacksTotal) * 100) : 0;

  const receptionPositiveRate =
    receptionsTotal > 0
      ? Math.round((receptionsPositive / receptionsTotal) * 100)
      : 0;

  const receptionNegativeRate =
    receptionsTotal > 0
      ? Math.round((receptionsNegative / receptionsTotal) * 100)
      : 0;

  const serveAceRate =
    servesTotal > 0 ? Math.round((servesAces / servesTotal) * 100) : 0;

  const serveErrorRate =
    servesTotal > 0 ? Math.round((servesErrors / servesTotal) * 100) : 0;

  const blockPointRate =
    blocksTotal > 0 ? Math.round((blocksPoints / blocksTotal) * 100) : 0;

  return (
    <div className="page-container">
      <PageHeader
        title="Stats del partido"
        subtitle="Captura rápida en cancha"
      />

      <Card>
        <h3 className="mb-3">📍 Posición</h3>
        <Input
          label="Rol en cancha"
          value={position}
          onChange={(e) => setPosition(e.target.value)}
          placeholder="Ej: P4 / Central"
        />

        <div className="card card-surface-alt mt-4 p-3">
          <h3 className="mb-3">📊 Rendimiento en vivo</h3>

          <p>💥 Ataque positivo: {attackEfficiency}%</p>
          <p>💥 Error ataque: {attackErrorRate}%</p>

          <p>🛡️ Recepción positiva: {receptionPositiveRate}%</p>
          <p>🛡️ Recepción negativa: {receptionNegativeRate}%</p>

          <p>🎯 Aces: {serveAceRate}%</p>
          <p>🎯 Error saque: {serveErrorRate}%</p>

          <p>🧱 Bloqueo punto: {blockPointRate}%</p>
        </div>

        <div className="mt-4">
          <h3 className="mb-3">💥 Ataque</h3>

          <StatCounter
            label="Totales"
            value={attacksTotal}
            onChange={setAttacksTotal}
          />

          <StatCounter
            label="Positivos"
            value={attacksPositive}
            onChange={setAttacksPositive}
          />

          <StatCounter
            label="Errores"
            value={attacksErrors}
            onChange={setAttacksErrors}
          />
        </div>
        <div className="mt-4">
          <h3 className="mb-3">🛡️ Recepción</h3>

          <StatCounter
            label="Totales"
            value={receptionsTotal}
            onChange={setReceptionsTotal}
          />

          <StatCounter
            label="Positivas"
            value={receptionsPositive}
            onChange={setReceptionsPositive}
          />

          <StatCounter
            label="Negativas"
            value={receptionsNegative}
            onChange={setReceptionsNegative}
          />
        </div>

        <div className="mt-4">
          <h3 className="mb-3">🎯 Saque</h3>

          <StatCounter
            label="Totales"
            value={servesTotal}
            onChange={setServesTotal}
          />

          <StatCounter
            label="Aces"
            value={servesAces}
            onChange={setServesAces}
          />

          <StatCounter
            label="Errores"
            value={servesErrors}
            onChange={setServesErrors}
          />
        </div>
        <div className="mt-4">
          <h3 className="mb-3">🧱 Bloqueo</h3>

          <StatCounter
            label="Totales"
            value={blocksTotal}
            onChange={setBlocksTotal}
          />

          <StatCounter
            label="Puntos"
            value={blocksPoints}
            onChange={setBlocksPoints}
          />
        </div>
      </Card>

      <div className="mt-4">
        <Button variant="primary" onClick={handleSave} disabled={loading}>
          {loading ? "Guardando..." : "Guardar stats"}
        </Button>
      </div>
    </div>
  );
};
