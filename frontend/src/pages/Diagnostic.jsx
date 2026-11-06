import { useEffect, useState } from "react";
import { api, pending } from "../api";
import { navigate, useLocation } from "../router";
import { useAsync } from "../useAsync";
import { ErrorBox, Loading } from "../components/ui";

export default function Diagnostic() {
  const { query } = useLocation();
  const flow = useAsync(() => api("/api/diagnostic/flow"), []);
  const [situation, setSituation] = useState(query.get("situacao"));
  const [steps, setSteps] = useState([]); // [{questionId, optionId}]
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => setSituation(query.get("situacao")), [query.get("situacao")]);
  useEffect(() => setSteps([]), [situation]);

  if (flow.loading) return <div className="wrap page narrow"><Loading label="Carregando diagnóstico" /></div>;
  if (flow.error) return <div className="wrap page narrow"><ErrorBox error={flow.error} onRetry={flow.reload} /></div>;

  const { situations, questions } = flow.data;
  const selected = situations.find((s) => s.id === situation);

  const finish = async (finalSteps) => {
    setBusy(true);
    setError(null);
    const answers = Object.fromEntries(finalSteps.map((s) => [s.questionId, s.optionId]));
    try {
      const { result } = await api("/api/diagnostic/evaluate", { method: "POST", body: { situation, answers } });
      pending.write({ situation, answers, result });
      navigate("/diagnostico/resultado");
    } catch (err) {
      setError(err);
      setBusy(false);
    }
  };

  if (!selected) {
    return (
      <div className="wrap page narrow diagnostic">
        <h1>Qual é a sua situação?</h1>
        <p className="muted">Escolha a opção mais próxima. Você recebe a trilha ao final, sem cadastro.</p>
        <div className="answer-list">
          {situations.map((s) => (
            <button key={s.id} className="answer" onClick={() => setSituation(s.id)}>
              <b>{s.title}</b><span>{s.description}</span>
            </button>
          ))}
        </div>
      </div>
    );
  }

  const last = steps[steps.length - 1];
  const lastOption = last && questions[last.questionId].options.find((o) => o.id === last.optionId);
  const questionId = last ? lastOption.next : selected.start;
  const question = questionId ? questions[questionId] : null;

  const choose = (option) => {
    const nextSteps = [...steps, { questionId, optionId: option.id }];
    if (option.next) setSteps(nextSteps);
    else finish(nextSteps);
  };

  const back = () => {
    if (steps.length) setSteps(steps.slice(0, -1));
    else { setSituation(null); navigate("/diagnostico", { replace: true }); }
  };

  return (
    <div className="wrap page narrow diagnostic">
      <p className="situation-context">{selected.title}</p>
      <p className="step-count">Pergunta {steps.length + 1}</p>
      <h1 key={questionId}>{question?.text}</h1>
      <div className="answer-list" key={`list-${questionId}`}>
        {question?.options.map((o) => (
          <button key={o.id} className="answer" disabled={busy} onClick={() => choose(o)}><b>{o.label}</b></button>
        ))}
      </div>
      {busy && <Loading label="Montando sua trilha" />}
      {error && <ErrorBox error={error} />}
      <button className="btn btn-text" onClick={back} disabled={busy}>Voltar</button>
    </div>
  );
}
