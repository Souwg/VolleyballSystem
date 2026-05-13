import React, { useState, useContext, useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Context } from "../../store/appContext";
import { StatCounter } from "../../component/ui/statCounter";
import { PageHeader } from "../../component/ui/pageHeader";
import { Card } from "../../component/ui/card";
import { Button } from "../../component/ui/button";

const genderLabelMap = {
  female: "Femenino",
  male: "Masculino",
  mixed: "Mixto",
};

const attendanceLabelMap = {
  present: "Presente",
  late: "Llegó tarde",
  absent: "Ausente",
  injured: "Lesionada",
};

const positionLabelMap = {
  setter: "Armadora",
  outside: "Punta",
  middle: "Central",
  opposite: "Opuesto",
  libero: "Líbero",
};

export const PlayerMatchStats = () => {
  const { actions } = useContext(Context);
  const { match_player_id } = useParams();
  const navigate = useNavigate();
  const [context, setContext] = useState(null);
  const [showLiveSummary, setShowLiveSummary] = useState(true);

  const [attacksTotal, setAttacksTotal] = useState(0);
  const [attacksPositive, setAttacksPositive] = useState(0);
  const [attacksNeutral, setAttacksNeutral] = useState(0);
  const [attacksErrors, setAttacksErrors] = useState(0);

  const [receptionsTotal, setReceptionsTotal] = useState(0);
  const [receptionsPositive, setReceptionsPositive] = useState(0);
  const [receptionsNeutral, setReceptionsNeutral] = useState(0);
  const [receptionsNegative, setReceptionsNegative] = useState(0);

  const [defensesTotal, setDefensesTotal] = useState(0);
  const [defensesPositive, setDefensesPositive] = useState(0);
  const [defensesNeutral, setDefensesNeutral] = useState(0);
  const [defensesNegative, setDefensesNegative] = useState(0);

  const [setsTotal, setSetsTotal] = useState(0);
  const [setsPositive, setSetsPositive] = useState(0);
  const [setsNeutral, setSetsNeutral] = useState(0);
  const [setsErrors, setSetsErrors] = useState(0);

  const [servesTotal, setServesTotal] = useState(0);
  const [servesIn, setServesIn] = useState(0);
  const [servesAces, setServesAces] = useState(0);
  const [servesErrors, setServesErrors] = useState(0);

  const [blocksTotal, setBlocksTotal] = useState(0);
  const [blocksPoints, setBlocksPoints] = useState(0);
  const [blocksNeutral, setBlocksNeutral] = useState(0);
  const [blocksErrors, setBlocksErrors] = useState(0);

  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const sum = attacksPositive + attacksNeutral + attacksErrors;

    if (sum > attacksTotal) {
      const overflow = sum - attacksTotal;

      if (attacksErrors >= overflow) {
        setAttacksErrors((prev) => prev - overflow);
      } else if (attacksNeutral >= overflow) {
        setAttacksNeutral((prev) => prev - overflow);
      } else {
        setAttacksPositive((prev) => Math.max(0, prev - overflow));
      }
    }
  }, [attacksPositive, attacksNeutral, attacksErrors, attacksTotal]);

  useEffect(() => {
    const sum = receptionsPositive + receptionsNeutral + receptionsNegative;

    if (sum > receptionsTotal) {
      const overflow = sum - receptionsTotal;

      if (receptionsNegative >= overflow) {
        setReceptionsNegative((prev) => prev - overflow);
      } else if (receptionsNeutral >= overflow) {
        setReceptionsNeutral((prev) => prev - overflow);
      } else {
        setReceptionsPositive((prev) => Math.max(0, prev - overflow));
      }
    }
  }, [
    receptionsPositive,
    receptionsNeutral,
    receptionsNegative,
    receptionsTotal,
  ]);

  useEffect(() => {
    const sum = defensesPositive + defensesNeutral + defensesNegative;

    if (sum > defensesTotal) {
      const overflow = sum - defensesTotal;

      if (defensesNegative >= overflow) {
        setDefensesNegative((prev) => prev - overflow);
      } else if (defensesNeutral >= overflow) {
        setDefensesNeutral((prev) => prev - overflow);
      } else {
        setDefensesPositive((prev) => Math.max(0, prev - overflow));
      }
    }
  }, [defensesPositive, defensesNeutral, defensesNegative, defensesTotal]);

  useEffect(() => {
    const sum = setsPositive + setsNeutral + setsErrors;

    if (sum > setsTotal) {
      const overflow = sum - setsTotal;

      if (setsErrors >= overflow) {
        setSetsErrors((prev) => prev - overflow);
      } else if (setsNeutral >= overflow) {
        setSetsNeutral((prev) => prev - overflow);
      } else {
        setSetsPositive((prev) => Math.max(0, prev - overflow));
      }
    }
  }, [setsPositive, setsNeutral, setsErrors, setsTotal]);

  useEffect(() => {
    const sum = servesIn + servesAces + servesErrors;

    if (sum > servesTotal) {
      const overflow = sum - servesTotal;

      if (servesErrors >= overflow) {
        setServesErrors((prev) => prev - overflow);
      } else if (servesAces >= overflow) {
        setServesAces((prev) => prev - overflow);
      } else {
        setServesIn((prev) => Math.max(0, prev - overflow));
      }
    }
  }, [servesIn, servesAces, servesErrors, servesTotal]);

  useEffect(() => {
    const sum = blocksPoints + blocksNeutral + blocksErrors;

    if (sum > blocksTotal) {
      const overflow = sum - blocksTotal;

      if (blocksErrors >= overflow) {
        setBlocksErrors((prev) => prev - overflow);
      } else if (blocksNeutral >= overflow) {
        setBlocksNeutral((prev) => prev - overflow);
      } else {
        setBlocksPoints((prev) => Math.max(0, prev - overflow));
      }
    }
  }, [blocksPoints, blocksNeutral, blocksErrors, blocksTotal]);

  const loadStats = async () => {
    const result = await actions.getPlayerMatchStats(match_player_id);

    if (!result.ok) return;

    const contextData = result.data.context || null;
    const stats = result.data.stats || null;

    setContext(contextData);

    if (!stats) {
      setAttacksTotal(0);
      setAttacksPositive(0);
      setAttacksNeutral(0);
      setAttacksErrors(0);

      setReceptionsTotal(0);
      setReceptionsPositive(0);
      setReceptionsNeutral(0);
      setReceptionsNegative(0);

      setDefensesTotal(0);
      setDefensesPositive(0);
      setDefensesNeutral(0);
      setDefensesNegative(0);

      setSetsTotal(0);
      setSetsPositive(0);
      setSetsNeutral(0);
      setSetsErrors(0);

      setServesTotal(0);
      setServesIn(0);
      setServesAces(0);
      setServesErrors(0);

      setBlocksTotal(0);
      setBlocksPoints(0);
      setBlocksNeutral(0);
      setBlocksErrors(0);
      return;
    }

    setAttacksTotal(stats.attacks_total || 0);
    setAttacksPositive(stats.attacks_positive || 0);
    setAttacksNeutral(stats.attacks_neutral || 0);
    setAttacksErrors(stats.attacks_errors || 0);

    setReceptionsTotal(stats.receptions_total || 0);
    setReceptionsPositive(stats.receptions_positive || 0);
    setReceptionsNeutral(stats.receptions_neutral || 0);
    setReceptionsNegative(stats.receptions_negative || 0);

    setDefensesTotal(stats.defenses_total || 0);
    setDefensesPositive(stats.defenses_positive || 0);
    setDefensesNeutral(stats.defenses_neutral || 0);
    setDefensesNegative(stats.defenses_negative || 0);

    setSetsTotal(stats.sets_total || 0);
    setSetsPositive(stats.sets_positive || 0);
    setSetsNeutral(stats.sets_neutral || 0);
    setSetsErrors(stats.sets_errors || 0);

    setServesTotal(stats.serves_total || 0);
    setServesIn(stats.serves_in || 0);
    setServesAces(stats.serves_aces || 0);
    setServesErrors(stats.serves_errors || 0);

    setBlocksTotal(stats.blocks_total || 0);
    setBlocksPoints(stats.blocks_points || 0);
    setBlocksNeutral(stats.blocks_neutral || 0);
    setBlocksErrors(stats.blocks_errors || 0);
  };

  useEffect(() => {
    loadStats();
  }, [match_player_id]);

  const handleSave = async () => {
    setLoading(true);

    const result = await actions.savePlayerMatchStats(match_player_id, {
      attacks_total: attacksTotal,
      attacks_positive: attacksPositive,
      attacks_neutral: attacksNeutral,
      attacks_errors: attacksErrors,

      receptions_total: receptionsTotal,
      receptions_positive: receptionsPositive,
      receptions_neutral: receptionsNeutral,
      receptions_negative: receptionsNegative,

      defenses_total: defensesTotal,
      defenses_positive: defensesPositive,
      defenses_neutral: defensesNeutral,
      defenses_negative: defensesNegative,

      sets_total: setsTotal,
      sets_positive: setsPositive,
      sets_neutral: setsNeutral,
      sets_errors: setsErrors,

      serves_total: servesTotal,
      serves_in: servesIn,
      serves_aces: servesAces,
      serves_errors: servesErrors,

      blocks_total: blocksTotal,
      blocks_points: blocksPoints,
      blocks_neutral: blocksNeutral,
      blocks_errors: blocksErrors,
    });

    setLoading(false);

    if (!result.ok) return;

    navigate(-1);
  };

  const attackEfficiency =
    attacksTotal > 0
      ? Math.round(((attacksPositive - attacksErrors) / attacksTotal) * 100)
      : 0;

  const attackPositiveRate =
    attacksTotal > 0 ? Math.round((attacksPositive / attacksTotal) * 100) : 0;

  const receptionPositiveRate =
    receptionsTotal > 0
      ? Math.round((receptionsPositive / receptionsTotal) * 100)
      : 0;

  const defensePositiveRate =
    defensesTotal > 0
      ? Math.round((defensesPositive / defensesTotal) * 100)
      : 0;

  const setsPositiveRate =
    setsTotal > 0 ? Math.round((setsPositive / setsTotal) * 100) : 0;

  const playerFullName = context
    ? `${context.player.first_name} ${context.player.last_name}`
    : "";

  const teamLabel = context
    ? `${context.team.name} · ${genderLabelMap[context.team.gender] || ""}`
    : "";

  const attendanceLabel = context?.match_player?.attendance_status
    ? attendanceLabelMap[context.match_player.attendance_status]
    : null;

  const playerPosition = context?.match_player?.position || "";

  const headerPosition = positionLabelMap[playerPosition] || "";

  const isLibero = playerPosition === "libero";

  const showAttack = !isLibero;
  const showBlock = !isLibero;

  return (
    <div className="page-container">
      <PageHeader
        title="Ajustar estadísticas"
        subtitle={
          context
            ? `vs ${context.match.opponent_name}`
            : "Revisión manual por jugadora"
        }
      />

      {context && (
        <Card className="mb-3">
          <p className="mb-1">
            <strong>
              #{context.player.player_number} {playerFullName}
            </strong>
          </p>

          <p className="mb-1">
            {teamLabel} · vs {context.match.opponent_name}
          </p>

          {headerPosition && (
            <p className="mb-1">
              Posición: <strong>{headerPosition}</strong>
            </p>
          )}
        </Card>
      )}

      <Card>
        <div className="mt-4">
          <Button
            variant="secondary"
            onClick={() => setShowLiveSummary((prev) => !prev)}
          >
            {showLiveSummary ? "Ocultar resumen" : "Mostrar resumen"}
          </Button>
        </div>

        {showLiveSummary && (
          <div className="card card-surface-alt mt-3 p-3">
            <h3 className="mb-3">📊 Resumen en vivo</h3>

            <h4 className="mb-2">Rendimiento</h4>

            {showAttack && (
              <>
                <p className="mb-1">
                  💥 Eficiencia de ataque: {attackEfficiency}%
                </p>
                <p className="mb-1">
                  ✅ Ataques positivos: {attackPositiveRate}%
                </p>
              </>
            )}

            <p className="mb-1">
              🛡️ Recepciones buenas: {receptionPositiveRate}%
            </p>
            <p className="mb-1">
              🛡️ Defensas positivas: {defensePositiveRate}%
            </p>
            <p className="mb-3">✋ Armados buenos: {setsPositiveRate}%</p>

            <h4 className="mb-2">Totales</h4>

            <p className="mb-1">🎯 Saques totales: {servesTotal}</p>
            <p className="mb-1">✅ Saques adentro: {servesIn}</p>
            <p className="mb-1">⭐ Aces: {servesAces}</p>
            <p className="mb-1">❌ Errores de saque: {servesErrors}</p>

            {showBlock && (
              <>
                <p className="mb-1">🧱 Bloqueos totales: {blocksTotal}</p>
                <p className="mb-1">✅ Bloqueos punto: {blocksPoints}</p>
                <p className="mb-1">↔️ Bloqueos sigue: {blocksNeutral}</p>
                <p className="mb-0">❌ Errores de bloqueo: {blocksErrors}</p>
              </>
            )}
          </div>
        )}

        <div className="mt-4">
          <h3 className="mb-3">Corregir estadísticas</h3>

          {showAttack && (
            <div className="mt-4">
              <h4 className="mb-3">💥 Ataque</h4>
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
                label="Neutrales"
                value={attacksNeutral}
                onChange={setAttacksNeutral}
              />
              <StatCounter
                label="Errores"
                value={attacksErrors}
                onChange={setAttacksErrors}
              />
            </div>
          )}

          <div className="mt-4">
            <h4 className="mb-3">🛡️ Recepción</h4>
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
              label="Neutrales"
              value={receptionsNeutral}
              onChange={setReceptionsNeutral}
            />
            <StatCounter
              label="Negativas"
              value={receptionsNegative}
              onChange={setReceptionsNegative}
            />
          </div>

          <div className="mt-4">
            <h4 className="mb-3">🛡️ Defensa</h4>
            <StatCounter
              label="Totales"
              value={defensesTotal}
              onChange={setDefensesTotal}
            />
            <StatCounter
              label="Positivas"
              value={defensesPositive}
              onChange={setDefensesPositive}
            />
            <StatCounter
              label="Neutrales"
              value={defensesNeutral}
              onChange={setDefensesNeutral}
            />
            <StatCounter
              label="Negativas"
              value={defensesNegative}
              onChange={setDefensesNegative}
            />
          </div>

          <div className="mt-4">
            <h4 className="mb-3">✋ Armado</h4>
            <StatCounter
              label="Totales"
              value={setsTotal}
              onChange={setSetsTotal}
            />
            <StatCounter
              label="Positivos"
              value={setsPositive}
              onChange={setSetsPositive}
            />
            <StatCounter
              label="Neutrales"
              value={setsNeutral}
              onChange={setSetsNeutral}
            />
            <StatCounter
              label="Errores"
              value={setsErrors}
              onChange={setSetsErrors}
            />
          </div>

          <div className="mt-4">
            <h4 className="mb-3">🎯 Saque</h4>
            <StatCounter
              label="Totales"
              value={servesTotal}
              onChange={setServesTotal}
            />
            <StatCounter
              label="Adentro"
              value={servesIn}
              onChange={setServesIn}
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

          {showBlock && (
            <div className="mt-4">
              <h4 className="mb-3">🧱 Bloqueo</h4>

              <StatCounter
                label="Total"
                value={blocksTotal}
                onChange={setBlocksTotal}
              />

              <StatCounter
                label="Puntos"
                value={blocksPoints}
                onChange={setBlocksPoints}
              />

              <StatCounter
                label="Sigue"
                value={blocksNeutral}
                onChange={setBlocksNeutral}
              />

              <StatCounter
                label="Errores"
                value={blocksErrors}
                onChange={setBlocksErrors}
              />
            </div>
          )}
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
