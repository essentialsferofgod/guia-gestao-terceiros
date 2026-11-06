import { useEffect, useRef, useState } from "react";
import { api, formatTime } from "../api";
import { useAuth } from "../auth";
import { Link, useLocation } from "../router";
import { useAsync } from "../useAsync";
import { CheckIcon, ErrorBox, Loading, LockIcon, OfferCard, VideoCard } from "../components/ui";

const SAVE_EVERY_SECONDS = 5;

function LockPanel({ video, onChange }) {
  const { path } = useLocation();
  const offer = video.lock_reason === "trial_expired";
  return (
    <div className={`lock-panel${offer ? " has-offer" : ""}`} data-testid="lock-panel">
      {video.thumb_url && <img src={video.thumb_url} alt="" />}
      <div className="lock-body">
        <LockIcon size={26} />
        <h2>{video.lock_message}</h2>
        {video.lock_reason === "login_required" && (
          <div className="lock-actions">
            <Link className="btn btn-primary" to={`/entrar?next=${encodeURIComponent(path)}`}>Entrar</Link>
            <Link className="btn btn-outline-light" to={`/entrar?modo=cadastro&next=${encodeURIComponent(path)}`}>Criar conta</Link>
          </div>
        )}
        {offer && <OfferCard onChange={onChange} />}
        {video.lock_reason === "plan_required" && <p>Este plano de demonstração libera apenas os vídeos introdutórios. A assinatura é ativada pelo administrador, sem pagamento.</p>}
      </div>
    </div>
  );
}

function Player({ video, canSave }) {
  const ref = useRef(null);
  const lastSaved = useRef(-1);
  const latest = useRef({ position: 0, duration: undefined });
  const resumed = useRef(false);
  const [notice, setNotice] = useState(null);
  const [failed, setFailed] = useState(false);
  const [saveFailed, setSaveFailed] = useState(false);

  const save = (keepalive = false) => {
    if (!canSave || !resumed.current) return;
    const position = Math.round(latest.current.position * 10) / 10;
    if (position === lastSaved.current || position <= 0) return;
    lastSaved.current = position;
    api(`/api/progress/${video.id}`, {
      method: "PUT", keepalive,
      body: { position_seconds: position, duration_seconds: latest.current.duration },
    }).then(() => setSaveFailed(false)).catch(() => setSaveFailed(true));
  };

  const track = (el) => {
    latest.current = { position: el.currentTime, duration: Number.isFinite(el.duration) ? el.duration : undefined };
  };

  useEffect(() => {
    const flush = () => save(true);
    window.addEventListener("pagehide", flush);
    return () => { window.removeEventListener("pagehide", flush); flush(); };
  }, [video.id]);

  return (
    <>
      <div className="player-frame">
        <video
          ref={ref}
          src={video.stream_url}
          controls
          playsInline
          preload="metadata"
          poster={video.thumb_url || undefined}
          data-testid="player"
          aria-label={video.title}
          onLoadedMetadata={(e) => {
            if (video.resume_seconds > 0 && video.resume_seconds < e.target.duration) {
              e.target.currentTime = video.resume_seconds;
              setNotice(`Continuando de ${formatTime(video.resume_seconds)}`);
            }
            resumed.current = true;
          }}
          onTimeUpdate={(e) => {
            track(e.target);
            if (Math.abs(e.target.currentTime - lastSaved.current) >= SAVE_EVERY_SECONDS) save();
          }}
          onSeeked={(e) => track(e.target)}
          onPause={(e) => { track(e.target); save(); }}
          onEnded={(e) => { track(e.target); save(); }}
          onError={() => setFailed(true)}
        />
      </div>
      {notice && <p className="player-note" role="status" data-testid="resume-note">{notice}</p>}
      {saveFailed && <p className="player-note warn" role="alert">O progresso não foi salvo. Verifique sua conexão.</p>}
      {failed && <ErrorBox error={{ message: "Não foi possível reproduzir este vídeo. Atualize a página ou tente mais tarde." }} />}
    </>
  );
}

export default function WatchPage({ id }) {
  const { user, ready } = useAuth();
  const video = useAsync(() => api(`/api/videos/${id}`), [id, user?.id]);
  const list = useAsync(() => api("/api/videos"), [user?.id]);
  const reloadAll = () => { video.reload(); list.reload(); };

  if (!ready || video.loading) return <div className="dark-page"><div className="wrap page"><Loading label="Carregando vídeo" /></div></div>;
  if (video.error) return <div className="dark-page"><div className="wrap page"><ErrorBox error={video.error} onRetry={video.reload} /></div></div>;

  const v = video.data.video;
  const others = (list.data?.videos || []).filter((x) => x.id !== v.id)
    .sort((a, b) => (b.category.slug === v.category.slug) - (a.category.slug === v.category.slug)).slice(0, 3);

  return (
    <div className="dark-page">
      <div className="wrap page watch">
        {v.locked ? <LockPanel video={v} onChange={reloadAll} />
          : v.stream_url ? <Player key={v.id} video={v} canSave={!!user} />
          : <div className="lock-panel"><div className="lock-body"><h2>Vídeo em produção</h2><p>O arquivo deste vídeo ainda não foi enviado.</p></div></div>}
        <div className="watch-info">
          <div>
            <p className="situation-context">{v.category.name}</p>
            <h1>{v.title}</h1>
            <p className="watch-description">{v.description}</p>
          </div>
          <div className="watch-side">
            <p>{formatTime(v.duration_seconds)} de duração</p>
            <p>{v.access_level === "intro" ? "Conteúdo introdutório" : "Conteúdo para assinantes"}</p>
            {v.completed && <p className="done-line"><CheckIcon size={14} />Você concluiu este vídeo</p>}
            {v.license_note && <p className="license">{v.license_note}</p>}
          </div>
        </div>
        {others.length > 0 && (
          <section className="rail">
            <h2>Continue aprendendo</h2>
            <div className="video-grid three">{others.map((o) => <VideoCard key={o.id} video={o} />)}</div>
          </section>
        )}
      </div>
    </div>
  );
}
