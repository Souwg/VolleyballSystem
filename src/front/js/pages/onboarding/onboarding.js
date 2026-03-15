import React, { useEffect, useContext, useState } from "react";
import { Context } from "../../store/appContext";
import { StepIndicator } from "../../component/ui/stepIndicator";
import "../../../styles/onboarding.css";

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

  return (
    <div className="onboarding-container">
      <div className="onboarding-card">
        <StepIndicator step={step} />

        <h2>Initial setup</h2>

        {step === 1 && (
          <form className="onboarding-form" onSubmit={handleSaveClub}>
            <h3>Step 1: Configure your club</h3>

            <input
              type="text"
              placeholder="Club location"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
            />

            <button>Save location</button>
          </form>
        )}

        {step === 2 && (
          <form className="onboarding-form" onSubmit={handleCreateTeam}>
            <h3>Step 2: Create your first team</h3>

            <input
              type="text"
              placeholder="Team name"
              value={teamName}
              onChange={(e) => setTeamName(e.target.value)}
            />

            <button>Create team</button>
          </form>
        )}

        {step === 3 && (
          <form className="onboarding-form" onSubmit={handleCreatePlayer}>
            <h3>Step 3: Register your first player</h3>

            <input
              type="text"
              placeholder="First name"
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
            />

            <input
              type="text"
              placeholder="Last name"
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
            />

            <input
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

            <button>Create player</button>
          </form>
        )}

        {step === 4 && (
          <>
            <h3>System ready</h3>
            <p>Your club system is ready.</p>
          </>
        )}
      </div>
    </div>
  );
};
