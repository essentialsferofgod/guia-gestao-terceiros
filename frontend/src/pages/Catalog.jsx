import { useEffect, useState } from "react";
import { api } from "../api";
import { useAuth } from "../auth";
import { navigate, useLocation } from "../router";
import { useAsync } from "../useAsync";
import { ErrorBox, Loading, VideoCard } from "../components/ui";

export default function Catalog() {
  const { user } = useAuth();
  const { query } = useLocation();
  const urlQ = query.get("q") || "";
  const category = query.get("categoria") || "";
  const [term, setTerm] = useState(urlQ);

  useEffect(() => setTerm(urlQ), [urlQ]);

  const setParams = (q, cat) => {
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (cat) params.set("categoria", cat);
    const search = params.toString();
    history.replaceState(null, "", `/catalogo${search ? `?${search}` : ""}`);
    window.dispatchEvent(new Event("locationchange"));
  };

  useEffect(() => {
    if (term === urlQ) return undefined;
    const timer = setTimeout(() => setParams(term.trim(), category), 250);
    return () => clearTimeout(timer);
  }, [term]);

  const cats = useAsync(() => api("/api/categories"), []);
  const list = useAsync(() => {
    const params = new URLSearchParams();
    if (urlQ) params.set("q", urlQ);
    if (category) params.set("category", category);
    return api(`/api/videos?${params}`);
  }, [urlQ, category, user?.id]);

  const videos = list.data?.videos || [];
  const filtered = urlQ || category;
  const categories = cats.data?.categories || [];
  const groups = categories
    .map((c) => ({ ...c, items: videos.filter((v) => v.category.slug === c.slug) }))
    .filter((g) => g.items.length);

  return (
    <div className="dark-page">
      <div className="wrap page">
        <div className="catalog-top">
          <h1>Catálogo</h1>
          <input
            type="search" className="search" placeholder="Busque por tema, como FGTS ou contrato"
            aria-label="Buscar vídeos" value={term} onChange={(e) => setTerm(e.target.value)}
          />
        </div>
        <div className="chips" role="group" aria-label="Filtrar por categoria">
          <button className="chip" aria-pressed={!category} onClick={() => setParams(urlQ, "")}>Todas</button>
          {categories.map((c) => (
            <button key={c.id} className="chip" aria-pressed={category === c.slug} onClick={() => setParams(urlQ, c.slug)}>{c.name}</button>
          ))}
        </div>

        {list.loading && <Loading label="Carregando vídeos" />}
        {list.error && <ErrorBox error={list.error} onRetry={list.reload} />}
        {!list.loading && !list.error && !videos.length && (
          <div className="state">
            <p>Nenhum vídeo encontrado para “{urlQ}”. Tente outro termo ou limpe os filtros.</p>
            <button className="btn btn-outline-light" onClick={() => navigate("/catalogo", { replace: true })}>Limpar filtros</button>
          </div>
        )}
        {!list.loading && videos.length > 0 && (filtered ? (
          <>
            <p className="result-count" role="status">{videos.length === 1 ? "1 vídeo encontrado" : `${videos.length} vídeos encontrados`}</p>
            <div className="video-grid">{videos.map((v) => <VideoCard key={v.id} video={v} />)}</div>
          </>
        ) : groups.map((g) => (
          <section className="shelf" key={g.id}>
            <div>
              <h2>{g.name}</h2>
              {g.description && <p>{g.description}</p>}
            </div>
            <div className="video-grid two">{g.items.map((v) => <VideoCard key={v.id} video={v} />)}</div>
          </section>
        )))}
      </div>
    </div>
  );
}
