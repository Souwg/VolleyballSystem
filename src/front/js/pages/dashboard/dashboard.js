import React, { useEffect, useContext } from "react";
import { Context } from "../../store/appContext";
import { PageHeader } from "../../component/ui/pageHeader";
import { Container } from "../../component/ui/container";
import { Card } from "../../component/ui/card";

export const Dashboard = () => {
  const { store, actions } = useContext(Context);

  useEffect(() => {
    if (!store.token) return;
    actions.getDashboard();
  }, [store.token]);

  if (!store.dashboardStats) {
    return <p>Loading dashboard...</p>;
  }

  return (
    <Container>
      <PageHeader title={`${store.club?.name} Dashboard`} />

      <div className="dashboard-grid">
        <Card>
          <h5>Total Teams</h5>
          <h2>{store.dashboardStats.total_teams}</h2>
        </Card>

        <Card>
          <h5>Total Players</h5>
          <h2>{store.dashboardStats.total_players}</h2>
        </Card>

        <Card>
          <h5>Active Players</h5>
          <h2>{store.dashboardStats.active_players}</h2>
        </Card>

        <Card>
          <h5>Injured Players</h5>
          <h2>{store.dashboardStats.injured_players}</h2>
        </Card>
      </div>
    </Container>
  );
};
