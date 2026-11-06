import { useState } from "react";
import { api, formatDate, formatTime, PLAN_LABEL } from "../api";
import { useAuth } from "../auth";
import { Link, useLocation } from "../router";
import { useAsync } from "../useAsync";
import { CheckIcon, ErrorBox, Field, Loading, LockIcon, OfferCard, ProgressBar, VideoCard } from "../components/ui";

function Profile() {
  const { user, setUser } = useAuth();
  const [form, setForm] = useState({ name: user.name, company: user.company, job_title: user.job_title });
  const [state, setState] = useState({});
  const submit = async (e) => {
    e.preventDefault();
    setState({ busy: true });
    try {
      const data = await api("/api/me", { method: "PATCH", body: form });
      setUser(data.user);
      setState({ saved: true });
    } catch (error) {
      setState({ error });
    }
  };
  const update = (key) => (e) => { setForm({ ...form, [key]: e.target.value }); setState({}); };
  return (
    <section className="panel" aria-labelledby="conta">
      <h2 id="conta">Conta</h2>
      <p className="plan-line"><b>{PLAN_LABEL[user.plan_status]}</b>{user.plan_status === "trial" && ` até ${formatDate(user.trial_ends_at)}`}</p>
      <form onSubmit={submit} className="profile-form">
        <Field label="Nome" error={state.error?.fields?.name}><input value={form.name} onChange={update("name")} /></Field>
        <Field label="Empresa"><input value={form.company} onChange={update("company")} /></Field>
        <Field label="Cargo"><input value={form.job_title} onChange={update("job_title")} /></Field>
        <button className="btn btn-primary" disabled={state.busy}>Salvar dados</button>
        {state.saved && <span className="saved-note" role="status">Dados salvos</span>}
      </form>
    </section>
  );
}

export default function Learning() {
  const { query } = useLocation();
  const { user } = useAuth();
  const profile = user.profiles.find((p) => p.id === user.active_profile_id);
  const { data, loading, error, reload } = useAsync(() => api("/api/me/learning"), []);
  const [removing, setRemoving] = useState(null);

  const removePath = async (id) => {
    setRemoving(id);
    await api(`/api/paths/${id}`, { method: "DELETE" }).catch(() => {});
    setRemoving(null);
    reload();
  };

  return (
    <div className="wrap page">
      <h1>Minha aprendizagem</h1>
      {profile && <p className="muted profile-line">Assistindo como <b>{profile.name}</b>. <Link to="/perfis">Trocar de perfil</Link></p>}
      {query.get("trilha") === "salva" && <p className="success-banner" role="status">Trilha salva. Seu progresso aparece aqui.</p>}
      {user.offer && <div className="offer-slot"><OfferCard onChange={reload} /></div>}
      {loading && <Loading />}
      {error && <ErrorBox error={error} onRetry={reload} />}
      {data && (
        <div className="learning-grid">
          <div className="learning-main">
            <p className="learning-stats">
              {data.stats.completed} de {data.stats.catalog_total} vídeos concluídos
            </p>
            <ProgressBar value={data.stats.catalog_total ? data.stats.completed / data.stats.catalog_total : 0} label="Vídeos concluídos" />

            <section aria-labelledby="continuar">
              <h2 id="continuar">Continuar assistindo</h2>
              {data.continue_watching.length ? (
                <div className="video-grid two">
                  {data.continue_watching.slice(0, 4).map((v) => <VideoCard key={v.id} video={v} />)}
                </div>
              ) : <p className="empty">Os vídeos que você começar aparecem aqui. <Link to="/catalogo">Abrir o catálogo</Link></p>}
            </section>

            <section aria-labelledby="trilhas">
              <h2 id="trilhas">Trilhas salvas</h2>
              {data.paths.length ? data.paths.map((p) => (
                <article className="saved-path" key={p.id} data-testid="saved-path">
                  <header>
                    <div>
                      <h3>{p.result.situation_title}</h3>
                      <p className="muted small">{p.done} de {p.total} vídeos concluídos. Salva em {formatDate(p.created_at)}.</p>
                    </div>
                    <button className="btn btn-text" disabled={removing === p.id} onClick={() => removePath(p.id)}>Remover</button>
                  </header>
                  <ProgressBar value={p.total ? p.done / p.total : 0} label={`Progresso da trilha ${p.result.situation_title}`} />
                  <ol>
                    {p.result.path.map((item) => (
                      <li key={item.slug}>
                        <Link to={`/assistir/${item.video.id}`}>{item.video.title}</Link>
                        {item.video.completed && <span className="done-mark"><CheckIcon size={13} />Concluído</span>}
                        {item.video.locked && <span className="meta-lock"><LockIcon size={13} />Exclusivo</span>}
                        <p className="reason">{item.reason}</p>
                      </li>
                    ))}
                  </ol>
                </article>
              )) : <p className="empty">Faça o diagnóstico para montar sua primeira trilha. <Link to="/diagnostico">Fazer o diagnóstico</Link></p>}
            </section>

            <section aria-labelledby="historico">
              <h2 id="historico">Histórico</h2>
              {data.history.length ? (
                <ul className="history">
                  {data.history.map((v) => (
                    <li key={v.id} data-testid="history-item">
                      <Link to={`/assistir/${v.id}`}>{v.title}</Link>
                      <span>{v.completed ? "Concluído" : `Parou em ${formatTime(v.position_seconds)}`}</span>
                      <span>{formatDate(v.last_watched_at)}</span>
                    </li>
                  ))}
                </ul>
              ) : <p className="empty">Você ainda não assistiu a nenhum vídeo.</p>}
            </section>
          </div>
          <Profile />
        </div>
      )}
    </div>
  );
}
