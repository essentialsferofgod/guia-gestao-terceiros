import { useEffect, useRef, useState } from "react";
import { Link } from "../router";
import { api, formatTime } from "../api";
import { useAuth } from "../auth";

export function Logo() {
  return <img src="/streamy-logo.png" alt="Streamy" width="199" height="24" />;
}

export function LockIcon({ size = 16 }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="5" y="11" width="14" height="10" rx="2" />
      <path d="M8 11V7a4 4 0 0 1 8 0v4" />
    </svg>
  );
}

export function CheckIcon({ size = 16 }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 13l4 4L19 7" />
    </svg>
  );
}

export function Loading({ label = "Carregando" }) {
  return <div className="state" role="status"><span className="spinner" />{label}</div>;
}

export function ErrorBox({ error, onRetry }) {
  return (
    <div className="state state-error" role="alert">
      <p>{error?.message || "Não foi possível carregar."}</p>
      {onRetry && <button className="btn btn-ghost" onClick={onRetry}>Tentar novamente</button>}
    </div>
  );
}

export function Field({ label, error, hint, children }) {
  return (
    <label className={`field${error ? " field-error" : ""}`}>
      <span>{label}</span>
      {children}
      {hint && !error && <small>{hint}</small>}
      {error && <small className="error-text">{error}</small>}
    </label>
  );
}

export function ProgressBar({ value, label }) {
  const percent = Math.min(100, Math.round(value * 100));
  return (
    <div className="progress" role="progressbar" aria-valuenow={percent} aria-valuemin={0} aria-valuemax={100} aria-label={label || "Progresso"}>
      <span style={{ width: `${percent}%` }} />
    </div>
  );
}

function useCountdown(secondsLeft, onEnd) {
  const [left, setLeft] = useState(secondsLeft);
  const ended = useRef(onEnd);
  ended.current = onEnd;
  useEffect(() => {
    // Conta a partir do valor do servidor, sem depender do relógio do computador.
    const start = performance.now();
    setLeft(secondsLeft);
    const timer = setInterval(() => {
      const rest = secondsLeft - Math.floor((performance.now() - start) / 1000);
      setLeft(Math.max(0, rest));
      if (rest <= 0) {
        clearInterval(timer);
        ended.current?.();
      }
    }, 1000);
    return () => clearInterval(timer);
  }, [secondsLeft]);
  return left;
}

function formatCountdown(total) {
  const pad = (n) => String(n).padStart(2, "0");
  return `${pad(Math.floor(total / 3600))}h ${pad(Math.floor((total % 3600) / 60))}min ${pad(total % 60)}s`;
}

export function PriceList({ offer }) {
  return (
    <ul className="offer-prices" data-testid="offer-prices">
      {offer.prices.map((p) => <li key={p.period}><span>{p.period}</span><b>{p.price}</b></li>)}
    </ul>
  );
}

/** Oferta de fim de teste. Os preços e o prazo vêm do servidor. */
export function OfferCard({ onChange }) {
  const { user, setUser, refresh } = useAuth();
  const [state, setState] = useState({});
  const offer = user?.offer;
  const left = useCountdown(offer?.seconds_left ?? 0, async () => {
    if (offer?.status !== "available") return;
    await refresh();
    onChange?.();
  });

  if (!offer) return null;

  const activate = async () => {
    setState({ busy: true });
    try {
      const data = await api("/api/offer/activate", { method: "POST" });
      setUser(data.user);
      setState({});
      onChange?.();
    } catch (error) {
      setState({ error });
      await refresh().catch(() => {});
    }
  };

  if (offer.status === "activated") {
    return (
      <section className="offer" data-testid="offer" aria-labelledby="oferta">
        <h2 id="oferta">Assinatura ativa</h2>
        <p className="offer-note">{offer.notice}. Valores da oferta:</p>
        <PriceList offer={offer} />
      </section>
    );
  }

  if (offer.status !== "available") {
    return (
      <section className="offer" data-testid="offer" aria-labelledby="oferta">
        <h2 id="oferta">{offer.status === "used" ? "Oferta já utilizada" : "Oferta encerrada"}</h2>
        <p className="offer-note">A assinatura agora é ativada pela administração da plataforma.</p>
      </section>
    );
  }

  return (
    <section className="offer" data-testid="offer" aria-labelledby="oferta">
      <h2 id="oferta">Continue assistindo com a oferta de fim de teste</h2>
      <p className="offer-timer">Termina em <time role="timer" data-testid="offer-timer" dateTime={offer.expires_at}>{formatCountdown(left)}</time></p>
      <PriceList offer={offer} />
      <button className="btn btn-primary btn-block" disabled={state.busy || left <= 0} onClick={activate}>
        {state.busy ? "Ativando" : "Ativar oferta"}
      </button>
      <p className="offer-note"><b>{offer.notice}.</b> Nenhum dado de pagamento é pedido.</p>
      {state.error && <p className="form-error" role="alert">{state.error.message}</p>}
    </section>
  );
}

export function VideoCard({ video, wide }) {
  const fraction = video.duration_seconds ? video.position_seconds / video.duration_seconds : 0;
  return (
    <Link to={`/assistir/${video.id}`} className={`video-card${video.locked ? " is-locked" : ""}${wide ? " is-wide" : ""}`} data-testid="video-card">
      <div className="cover">
        {video.thumb_url
          ? <img src={video.thumb_url} alt="" loading="lazy" />
          : <div className="cover-fallback"><b>{video.category.name}</b><span>{video.title}</span></div>}
        {video.locked && video.access_level === "premium" && <span className="badge-lock"><LockIcon size={14} />Assinantes</span>}
        {video.locked && video.access_level === "intro" && <span className="badge-intro">Introdutório</span>}
        {!video.locked && video.completed && <span className="badge-done"><CheckIcon size={13} />Concluído</span>}
        {!video.locked && fraction > 0 && !video.completed && <ProgressBar value={fraction} label={`Progresso de ${video.title}`} />}
      </div>
      <h3>{video.title}</h3>
      <p className="card-meta">
        <span>{video.category.name}</span>
        <span>{formatTime(video.duration_seconds)}</span>
      </p>
    </Link>
  );
}
