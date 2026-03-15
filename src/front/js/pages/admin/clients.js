import React, { useEffect, useContext, useState } from "react";
import { Context } from "../../store/appContext";
import { Input } from "../../component/ui/input";
import { Button } from "../../component/ui/button";
import { PageHeader } from "../../component/ui/pageHeader";
import { Container } from "../../component/ui/container";

export const Clients = () => {
  const { store, actions } = useContext(Context);

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [clubName, setClubName] = useState("");
  const [flashMessage, setFlashMessage] = useState(null);

  useEffect(() => {
    actions.getAdminClients();
  }, []);

  const createClient = async (e) => {
    e.preventDefault();

    const result = await actions.createClient({
      full_name: fullName,
      email: email,
      club_name: clubName,
    });

    if (!result?.ok) {
      alert(result.message);
      return;
    }

    const credentials = result.data.credentials;

    setFullName("");
    setEmail("");
    setClubName("");

    setFlashMessage({
      email: credentials.email,
      password: credentials.temporary_password,
    });

    setTimeout(() => {
      setFlashMessage(null);
    }, 9000);
  };

  return (
    <Container>
      {flashMessage && (
        <div>
          <strong>Client created successfully</strong>

          <div>
            <div>Email: {flashMessage.email}</div>
            <div>
              Temporary password:
              <code>{flashMessage.password}</code>
            </div>
          </div>
        </div>
      )}

      <PageHeader title="Clients" />

      <form onSubmit={createClient}>
        <div>
          <div>
            <Input
              placeholder="Full name"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
            />
          </div>

          <div>
            <Input
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          <div>
            <Input
              placeholder="Club name"
              value={clubName}
              onChange={(e) => setClubName(e.target.value)}
            />
          </div>
        </div>

        <Button>Create Client</Button>
      </form>

      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Email</th>
            <th>Status</th>
            <th>Action</th>
          </tr>
        </thead>

        <tbody>
          {store.adminClients.map((client) => {
            return (
              <tr key={client.id}>
                <td>{client.full_name}</td>

                <td>{client.email}</td>

                <td>{client.is_active ? "Active" : "Inactive"}</td>

                <td>
                  {client.is_active ? (
                    <Button
                      onClick={() =>
                        actions.toggleClientStatus(client.id, "deactivate")
                      }
                    >
                      Deactivate
                    </Button>
                  ) : (
                    <Button
                      onClick={() =>
                        actions.toggleClientStatus(client.id, "activate")
                      }
                    >
                      Activate
                    </Button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Container>
  );
};
