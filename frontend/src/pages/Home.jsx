import { api } from "../api";
import { useAuth } from "../auth";
import { Link } from "../router";
import { useAsync } from "../useAsync";
import { VideoCard } from "../components/ui";

const SITUATIONS = [
  ["contratar", "Preciso contratar uma empresa terceirizada"],
  ["documentacao", "Tenho problemas com documentação"],
  ["acompanhar", "Preciso acompanhar contratos e prevenir riscos"],
];

export default function Home() {
  const { user } = useAuth();
  const { data } = useAsync(() => api("/api/videos"), [user?.id]);
  const videos = data?.videos || [];
  const inProgress = videos.find((v) => !v.locked && !v.completed && v.position_seconds > 0);
  const featured = inProgress || videos.find((v) => v.slug === "rotina-mensal-do-contrato") || videos[0];
  const others = videos.filter((v) => v !== featured).slice(0, 2);

  return (
    <>
      <section className="hero">
        <div className="wrap hero-grid">
          <div className="hero-diagnostic">
            <h1>O terceiro é de outra empresa. O risco também é seu.</h1>
            <p className="lead">
              Vídeos curtos para gestores que contratam serviços terceirizados. Conte o que está acontecendo
              e receba uma trilha feita para a sua situação.
            </p>
            <div className="situation-panel">
              <h2>O que você precisa resolver agora?</h2>
              <div className="situation-list">
                {SITUATIONS.map(([id, label]) => (
                  <Link key={id} to={`/diagnostico?situacao=${id}`} className="situation-option">{label}</Link>
                ))}
              </div>
              <p className="panel-note">Leva menos de um minuto e funciona sem cadastro.</p>
            </div>
          </div>
          <aside className="hero-stream" aria-label="Prévia do catálogo">
            <div className="stream-head">
              <h2>{inProgress ? "Continue de onde parou" : "No catálogo"}</h2>
              <Link to="/catalogo">Ver todos os vídeos</Link>
            </div>
            {featured && <VideoCard video={featured} wide />}
            <div className="stream-pair">
              {others.map((v) => <VideoCard key={v.id} video={v} />)}
            </div>
          </aside>
        </div>
      </section>

      <section className="section">
        <div className="wrap stages">
          <h2>Do contrato assinado ao contrato em dia</h2>
          <ol className="stage-line">
            <li><b>Contratar</b><span>Escolha a prestadora com critérios claros e um contrato completo.</span></li>
            <li><b>Documentar</b><span>Saiba o que exigir, quando conferir e como tratar pendências.</span></li>
            <li><b>Acompanhar</b><span>Crie uma rotina mensal e reconheça sinais de risco cedo.</span></li>
          </ol>
        </div>
      </section>
    </>
  );
}
