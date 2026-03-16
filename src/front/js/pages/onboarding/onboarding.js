import React, { useEffect, useContext, useState } from "react";
import { Context } from "../../store/appContext";
import { StepIndicator } from "../../component/ui/stepIndicator";
import { Container } from "../../component/ui/container";
import { Card } from "../../component/ui/card";
import { Input } from "../../component/ui/input";
import { Button } from "../../component/ui/button";
import { PageHeader } from "../../component/ui/pageHeader";

export const Onboarding = () => {
  const { store, actions } = useContext(Context);

  const [location, setLocation] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [number, setNumber] = useState("");
  const [sex, setSex] = useState("");
  const [teamName, setTeamName] = useState("");
  const [selectedTeam, setSelectedTeam] = useState("");

  useEffect(() => {
    actions.getOnboardingStatus();
    actions.getTeams();
  }, []);

  const step = store.onboardingStep;

  const handleSaveClub = async (e) => {
    e.preventDefault();

    const result = await actions.updateClub(location);

    if (!result.ok) {
      alert(result.message);
    }
  };

  const handleCreateTeam = async (e) => {
    e.preventDefault();

    const result = await actions.createTeam(teamName);

    if (!result.ok) {
      alert(result.message);
    }
  };

  const handleCreatePlayer = async (e) => {
    e.preventDefault();

    if (!selectedTeam) {
      alert("Debes seleccionar un equipo");
      return;
    }

    const result = await actions.createPlayer({
      first_name: firstName,
      last_name: lastName,
      player_number: number,
      sex: sex,
      team_id: selectedTeam,
    });

    if (!result.ok) {
      alert(result.message);
    }
  };

  useEffect(() => {
    if (step === 4) {
      setTimeout(() => {
        navigate("/dashboard");
      }, 1500);
    }
  }, [step]);

  return (
    <Container>
      <Card>
        <StepIndicator step={step} total={4} />

        {step === 1 && (
          <>
            <PageHeader
              title="Initial setup"
              subtitle="Let's configure your volleyball club"
            />

            <form className="form" onSubmit={handleSaveClub}>
              <Input
                type="text"
                placeholder="Club location"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
              />

              <Button type="submit">Save location</Button>
            </form>
          </>
        )}

        {step === 2 && (
          <>
            <PageHeader
              title="Create your first team"
              subtitle="You can create more teams later"
            />
            <form className="form" onSubmit={handleCreateTeam}>
              <Input
                type="text"
                placeholder="Team name"
                value={teamName}
                onChange={(e) => setTeamName(e.target.value)}
              />

              <Button type="submit">Create team</Button>
            </form>
          </>
        )}

        {step === 3 && (
          <>
            <PageHeader
              title="Register your first player"
              subtitle="Add your first player to start managing your club"
            />
            <form className="form" onSubmit={handleCreatePlayer}>
              <Input
                type="text"
                placeholder="First name"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
              />

              <Input
                type="text"
                placeholder="Last name"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
              />

              <Input
                type="number"
                placeholder="Player number"
                value={number}
                onChange={(e) => setNumber(e.target.value)}
              />

              <select value={sex} onChange={(e) => setSex(e.target.value)}>
                <option value="">Sex</option>
                <option value="male">Male</option>
                <option value="female">Female</option>
              </select>

              <select
                value={selectedTeam}
                onChange={(e) => setSelectedTeam(e.target.value)}
              >
                <option value="">Select team</option>

                {store.teams?.map((team) => (
                  <option key={team.id} value={team.id}>
                    {team.name}
                  </option>
                ))}
              </select>

              <Button type="submit">Create player</Button>
            </form>
          </>
        )}

        {step === 4 && (
          <>
            <PageHeader
              title="System ready"
              subtitle="Your volleyball club system is ready"
            />
            <p>You will be redirected to the dashboard.</p>
          </>
        )}
      </Card>
    </Container>
  );
};
