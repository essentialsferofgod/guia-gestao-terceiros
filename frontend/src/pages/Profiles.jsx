import { useState } from "react";
import { api } from "../api";
import { finishEntry, useAuth } from "../auth";
import { safeNext, useLocation } from "../router";
import { Field } from "../components/ui";

function Avatar({ name }) {
  return <span className="profile-avatar" aria-hidden="true">{name.trim().charAt(0).toUpperCase()}</span>;
}

function ManageRow({ profile, canDelete }) {
  const { setUser } = useAuth();
  const [name, setName] = useState(profile.name);
  const [confirming, setConfirming] = useState(false);
  const [state, setState] = useState({});

  const rename = async (e) => {
    e.preventDefault();
    setState({ busy: true });
    try {
      const data = await api(`/api/profiles/${profile.id}`, { method: "PATCH", body: { name } });
      setUser(data.user);
      setState({ saved: true });
    } catch (error) {
      setState({ error });
    }
  };

  const remove = async () => {
    setState({ busy: true });
    try {
      const data = await api(`/api/profiles/${profile.id}`, { method: "DELETE" });
      setUser(data.user);
    } catch (error) {
      setState({ error });
      setConfirming(false);
    }
  };

  return (
    <li className="profile-manage-row" data-testid="profile-manage-row">
      <form onSubmit={rename}>
        <Field label={`Nome do perfil ${profile.name}`} error={state.error?.fields?.name}>
          <input value={name} onChange={(e) => { setName(e.target.value); setState({}); }} />
        </Field>
        <div className="profile-manage-actions">
          <button className="btn btn-primary btn-sm" disabled={state.busy || name === profile.name}>Salvar nome</button>
          {canDelete && !confirming && <button type="button" className="btn btn-outline-light btn-sm" onClick={() => setConfirming(true)}>Excluir</button>}
          {state.saved && <span role="status">Nome salvo</span>}
        </div>
      </form>
      {confirming && (
        <div className="profile-confirm">
          <p>O progresso, o histórico e as trilhas de {profile.name} serão apagados. Essa ação não pode ser desfeita.</p>
          <div className="profile-manage-actions">
            <button className="btn btn-primary btn-sm" disabled={state.busy} onClick={remove}>Confirmar exclusão</button>
            <button className="btn btn-outline-light btn-sm" onClick={() => setConfirming(false)}>Cancelar</button>
          </div>
        </div>
      )}
      {state.error && !Object.keys(state.error.fields).length && <p className="form-error" role="alert">{state.error.message}</p>}
    </li>
  );
}

function AddProfile() {
  const { setUser } = useAuth();
  const [name, setName] = useState("");
  const [state, setState] = useState({});

  const submit = async (e) => {
    e.preventDefault();
    setState({ busy: true });
    try {
      const data = await api("/api/profiles", { method: "POST", body: { name } });
      setUser(data.user);
      setName("");
      setState({});
    } catch (error) {
      setState({ error });
    }
  };

  return (
    <form className="profile-add" onSubmit={submit} noValidate>
      <Field label="Nome do novo perfil" error={state.error?.fields?.name}>
        <input value={name} onChange={(e) => { setName(e.target.value); setState({}); }} autoComplete="off" />
      </Field>
      <button className="btn btn-primary" disabled={state.busy}>Adicionar perfil</button>
      {state.error && !Object.keys(state.error.fields).length && <p className="form-error" role="alert">{state.error.message}</p>}
    </form>
  );
}

export default function Profiles() {
  const { user, setUser } = useAuth();
  const { query } = useLocation();
  const [managing, setManaging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState(null);
  const next = safeNext(query.get("next"));
  const saving = query.get("salvar") === "1";
  const { profiles, max_profiles: max } = user;

  const choose = async (profile) => {
    setBusy(true);
    setProblem(null);
    try {
      const data = await api(`/api/profiles/${profile.id}/select`, { method: "POST" });
      setUser(data.user);
      await finishEntry({ account: data.user, next, saving });
    } catch (error) {
      setProblem(error);
      setBusy(false);
    }
  };

  return (
    <div className="dark-page">
      <div className="wrap page profiles-page">
        <h1>Quem está assistindo?</h1>
        <p className="profiles-note">Cada perfil tem seu progresso, histórico e trilhas. O plano é o mesmo para toda a conta.</p>
        {problem && <p className="form-error" role="alert">{problem.message}</p>}
        <ul className="profile-grid">
          {profiles.map((p) => (
            <li key={p.id}>
              <button className="profile-card" data-testid="profile-card" disabled={busy} aria-current={p.id === user.active_profile_id ? "true" : undefined} onClick={() => choose(p)}>
                <Avatar name={p.name} />
                <span className="profile-name">{p.name}</span>
              </button>
            </li>
          ))}
        </ul>
        <p className="profiles-count">{profiles.length} de {max} perfis</p>
        <button className="btn btn-outline-light" aria-expanded={managing} onClick={() => setManaging(!managing)}>
          {managing ? "Concluir" : "Gerenciar perfis"}
        </button>
        {managing && (
          <div className="profile-manage">
            <ul>{profiles.map((p) => <ManageRow key={p.id} profile={p} canDelete={profiles.length > 1} />)}</ul>
            {profiles.length < max
              ? <AddProfile />
              : <p className="profiles-note">Esta conta já tem o limite de {max} perfis.</p>}
          </div>
        )}
      </div>
    </div>
  );
}
