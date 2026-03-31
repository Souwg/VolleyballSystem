import React, { useEffect, useContext, useState } from "react";
import { useParams } from "react-router-dom";
import { Context } from "../../store/appContext";

import { Container } from "../../component/ui/container";
import { PageHeader } from "../../component/ui/pageHeader";
import { Card } from "../../component/ui/card";

export const PlayerDetail = () => {
  const { actions } = useContext(Context);
  const { player_id } = useParams();

  const [player, setPlayer] = useState(null);
  const [summary, setSummary] = useState(null);
  const [history, setHistory] = useState([]);

  useEffect(() => {
    const loadData = async () => {
      const data = await actions.getPlayerAttendance(player_id);

      if (!data) return;

      setPlayer(data.player);
      setSummary(data.summary);
      setHistory(data.history);
    };

    loadData();
  }, [player_id]);

  if (!player) return null;

  return (
    <Container>
      <PageHeader
        title={`${player.first_name} ${player.last_name}`}
        subtitle={`#${player.player_number}`}
      />

      <Card>
        <h3>Attendance Summary</h3>

        {summary && (
          <div>
            <p>Present: {summary.present}</p>
            <p>Late: {summary.late}</p>
            <p>Absent: {summary.absent}</p>
            <p>Attendance Rate: {summary.attendance_rate}%</p>
          </div>
        )}
      </Card>

      <Card>
        <h3>Attendance History</h3>

        {history.map((h) => (
          <div key={h.training_id}>
            {h.date} — {h.status}
          </div>
        ))}
      </Card>
    </Container>
  );
};
