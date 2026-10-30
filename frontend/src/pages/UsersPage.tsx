import { FormEvent, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import ErrorBox from "../components/ErrorBox";

type Person = {
  id: number;
  username: string;
  role: string;
};

const ROLES = [
  { value: "clinician", label: "Clinician" },
  { value: "mlops", label: "MLOps" },
];

function roleLabel(role: string): string {
  return ROLES.find((r) => r.value === role)?.label ?? role;
}

export default function UsersPage() {
  const { user } = useAuth();
  const [people, setPeople] = useState<Person[]>([]);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("clinician");
  const [drafts, setDrafts] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [notice, setNotice] = useState("");

  const load = () =>
    api<{ users: Person[] }>("/api/v1/users")
      .then((r) => {
        setPeople(r.users);
        setDrafts(Object.fromEntries(r.users.map((p) => [p.id, p.role])));
      })
      .catch(setError);

  useEffect(() => {
    if (user?.role === "mlops") load();
  }, [user?.role]);

  if (user?.role !== "mlops") return <Navigate to="/" replace />;

  const onCreate = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setNotice("");
    try {
      const created = await api<Person>("/api/v1/users", {
        method: "POST",
        body: JSON.stringify({ username, password, role }),
      });
      setNotice(`Added ${created.username} as ${roleLabel(created.role)}.`);
      setUsername("");
      setPassword("");
      setRole("clinician");
      await load();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  const assign = async (person: Person) => {
    const next = drafts[person.id];
    if (!next || next === person.role) return;
    setError(null);
    setNotice("");
    try {
      const updated = await api<Person>(`/api/v1/users/${person.id}`, {
        method: "PATCH",
        body: JSON.stringify({ role: next }),
      });
      setNotice(`${updated.username} is now ${roleLabel(updated.role)}.`);
      await load();
    } catch (err) {
      setError(err);
    }
  };

  return (
    <article className="people">
      <h1>People</h1>
      <p className="people-lede">
        Add someone who can sign in, and choose whether they screen patients or manage the service.
      </p>
      {notice ? <p className="people-notice">{notice}</p> : null}
      {error ? <ErrorBox error={error} /> : null}

      <form className="card people-form" onSubmit={onCreate}>
        <label>
          Username
          <input
            value={username}
            autoComplete="off"
            onChange={(e) => setUsername(e.target.value)}
            required
          />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            autoComplete="new-password"
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>
        <label>
          Role
          <select value={role} onChange={(e) => setRole(e.target.value)}>
            {ROLES.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" disabled={busy}>
          {busy ? "Adding…" : "Add person"}
        </button>
      </form>

      <section className="card">
        <table className="dash-table">
          <thead>
            <tr>
              <th>Username</th>
              <th>Role</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {people.map((person) => {
              const changed = drafts[person.id] !== person.role;
              const self = person.username === user.username;
              return (
                <tr key={person.id}>
                  <td>{person.username}</td>
                  <td>
                    {self ? (
                      roleLabel(person.role)
                    ) : (
                      <select
                        aria-label={`Role for ${person.username}`}
                        value={drafts[person.id] ?? person.role}
                        onChange={(e) =>
                          setDrafts((prev) => ({ ...prev, [person.id]: e.target.value }))
                        }
                      >
                        {ROLES.map((r) => (
                          <option key={r.value} value={r.value}>
                            {r.label}
                          </option>
                        ))}
                      </select>
                    )}
                  </td>
                  <td>
                    {self ? null : (
                      <button type="button" disabled={!changed} onClick={() => assign(person)}>
                        Assign role
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>
    </article>
  );
}
