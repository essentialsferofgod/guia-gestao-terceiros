import { useEffect, useState } from "react";
import { api, formatTime, pending } from "../api";
import { useAuth } from "../auth";
import { Link, navigate } from "../router";
import { CheckIcon, ErrorBox, LockIcon } from "../components/ui";

export default function Result() {
  const { user } = useAuth();
  const [draft, setDraft] = useState(() => pending.read());
  const [state, setState] = useState({ busy: false, error: null, saved: false });

  // Atualiza os bloqueios quando o usuário entra na conta.
  useEffect(() => {
    if (!draft) return;
    api("/api/diagnostic/evaluate", { method: "POST", body: { situation: draft.situation, answers: draft.answers } })
      .then(({ result }) => setDraft((d) => ({ ...d, result })))
      .catch(() => {});
  }, [user?.id]);

  if (!draft) {
    return (
      <div className="wrap page narrow">
        <h1>Nenhum diagnóstico em andamento</h1>
        <p className="muted">Responda às perguntas para receber sua trilha.</p>
        <Link className="btn btn-primary" to="/diagnostico">Fazer o diagnóstico</Link>
      </div>
    );
  }

  const { result } = draft;
  const save = async () => {
    setState({ busy: true, error: null, saved: false });
    try {
      await api("/api/paths", { method: "POST", body: { situation: draft.situation, answers: draft.answers } });
      setState({ busy: false, error: null, saved: true });
    } catch (error) {
      setState({ busy: false, error, saved: false });
    }
  };

  return (
    <div className="wrap page result">
      <header className="result-head">
        <p className="situation-context">{result.situation_title}</p>
        <h1>{result.summary}</h1>
      </header>
      <div className="result-grid">
        <section aria-labelledby="trilha">
          <h2 id="trilha">Sua trilha recomendada</h2>
          <ol className="path-list">
            {result.path.map((item, index) => (
              <li key={item.slug} data-testid="path-item">
                <span className="path-number">{index + 1}</span>
                <div>
                  <Link to={`/assistir/${item.video.id}`} className="path-title">{item.video.title}</Link>
                  <p className="reason">{item.reason}</p>
                  <p className="card-meta dark">
                    <span>{item.video.category.name}</span>
                    <span>{formatTime(item.video.duration_seconds)}</span>
                    {item.video.locked && <span className="meta-lock"><LockIcon size={13} />{item.video.lock_reason === "plan_required" ? "Exclusivo para assinantes" : "Entre para assistir"}</span>}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        </section>
        <aside className="result-side">
          <section className="checklist" aria-labelledby="checklist">
            <h2 id="checklist">Comece por aqui</h2>
            <ul>
              {result.checklist.map((text) => <li key={text}><CheckIcon size={15} />{text}</li>)}
            </ul>
          </section>
          <div className="save-box">
            {state.saved ? (
              <>
                <p role="status"><b>Trilha salva.</b> Acompanhe seu progresso em Minha aprendizagem.</p>
                <Link className="btn btn-primary btn-block" to="/minha-aprendizagem">Abrir Minha aprendizagem</Link>
              </>
            ) : user ? (
              <>
                <p>Guarde esta trilha para acompanhar seu progresso.</p>
                <button className="btn btn-primary btn-block" onClick={save} disabled={state.busy}>{state.busy ? "Salvando" : "Salvar trilha"}</button>
              </>
            ) : (
              <>
                <p>Crie uma conta para salvar esta trilha e acompanhar seu progresso.</p>
                <Link className="btn btn-primary btn-block" to="/entrar?modo=cadastro&salvar=1">Criar conta e salvar trilha</Link>
                <Link className="btn btn-ghost btn-block" to="/entrar?salvar=1">Já tenho conta</Link>
              </>
            )}
            {state.error && <ErrorBox error={state.error} />}
          </div>
          <details className="answers-recap">
            <summary>Ver minhas respostas</summary>
            <dl>
              {result.answers.map((a) => (<div key={a.question}><dt>{a.question}</dt><dd>{a.answer}</dd></div>))}
            </dl>
          </details>
          <button className="btn btn-text" onClick={() => { pending.clear(); navigate("/diagnostico"); }}>Refazer o diagnóstico</button>
          <p className="muted small">{result.note}</p>
        </aside>
      </div>
    </div>
  );
}
