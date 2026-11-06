import { useState } from "react";
import { api, formatTime, PLAN_LABEL, uploadVideo } from "../api";
import { useAsync } from "../useAsync";
import { ErrorBox, Field, Loading } from "../components/ui";

const EMPTY = { title: "", description: "", category_id: "", access_level: "premium", duration_seconds: 0, license_note: "" };

function VideoForm({ categories, initial, onDone, onCancel }) {
  const [form, setForm] = useState(initial || { ...EMPTY, category_id: categories[0]?.id || "" });
  const [state, setState] = useState({});
  const update = (key, numeric) => (e) => setForm({ ...form, [key]: numeric ? Number(e.target.value) : e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setState({ busy: true });
    const body = {
      title: form.title, description: form.description, category_id: Number(form.category_id),
      access_level: form.access_level, duration_seconds: Number(form.duration_seconds), license_note: form.license_note,
    };
    try {
      if (initial) await api(`/api/admin/videos/${initial.id}`, { method: "PATCH", body });
      else await api("/api/admin/videos", { method: "POST", body });
      onDone(initial ? "Vídeo atualizado." : "Vídeo criado como rascunho. Envie o arquivo para publicar.");
    } catch (error) {
      setState({ error });
    }
  };

  return (
    <form className="admin-form" onSubmit={submit} data-testid="video-form">
      <h3>{initial ? "Editar vídeo" : "Novo vídeo"}</h3>
      <Field label="Título" error={state.error?.fields?.title}><input value={form.title} onChange={update("title")} required /></Field>
      <Field label="Descrição" error={state.error?.fields?.description}><textarea rows="2" value={form.description} onChange={update("description")} /></Field>
      <div className="form-row">
        <Field label="Categoria">
          <select value={form.category_id} onChange={update("category_id")}>
            {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </Field>
        <Field label="Acesso">
          <select value={form.access_level} onChange={update("access_level")}>
            <option value="intro">Introdutório</option>
            <option value="premium">Assinantes</option>
          </select>
        </Field>
      </div>
      <Field label="Licença ou autoria" hint="Informe quem criou o vídeo ou qual licença autoriza o uso.">
        <input value={form.license_note} onChange={update("license_note")} />
      </Field>
      {state.error && !Object.keys(state.error.fields).length && <p className="form-error" role="alert">{state.error.message}</p>}
      <div className="form-actions">
        <button className="btn btn-primary" disabled={state.busy}>{initial ? "Salvar alterações" : "Criar vídeo"}</button>
        <button type="button" className="btn btn-text" onClick={onCancel}>Cancelar</button>
      </div>
    </form>
  );
}

function Videos({ categories }) {
  const { data, loading, error, reload } = useAsync(() => api("/api/admin/videos"), []);
  const [editing, setEditing] = useState(null); // null, "new" ou vídeo
  const [message, setMessage] = useState(null);
  const [problem, setProblem] = useState(null);
  const [upload, setUpload] = useState(null);
  const [confirming, setConfirming] = useState(null);

  const run = async (action, success) => {
    setProblem(null);
    try {
      await action();
      setMessage(success);
      reload();
    } catch (e) {
      setProblem(e);
    }
  };

  const send = async (video, file) => {
    if (!file) return;
    setProblem(null);
    setUpload({ id: video.id, percent: 0 });
    try {
      await uploadVideo(video.id, file, (percent) => setUpload({ id: video.id, percent }));
      setMessage("Arquivo enviado. O vídeo já pode ser publicado.");
      reload();
    } catch (e) {
      setProblem(e);
    }
    setUpload(null);
  };

  if (loading) return <Loading />;
  if (error) return <ErrorBox error={error} onRetry={reload} />;

  return (
    <section>
      <div className="admin-head">
        <h2>Vídeos</h2>
        <button className="btn btn-primary" onClick={() => { setEditing("new"); setMessage(null); }}>Novo vídeo</button>
      </div>
      {message && <p className="success-banner" role="status">{message}</p>}
      {problem && <p className="form-error" role="alert">{problem.message}</p>}
      {editing && (
        <VideoForm
          key={editing === "new" ? "new" : editing.id}
          categories={categories}
          initial={editing === "new" ? null : editing}
          onDone={(text) => { setEditing(null); setMessage(text); reload(); }}
          onCancel={() => setEditing(null)}
        />
      )}
      <div className="table-wrap">
        <table>
          <thead><tr><th>Título</th><th>Categoria</th><th>Acesso</th><th>Situação</th><th>Arquivo</th><th><span className="sr">Ações</span></th></tr></thead>
          <tbody>
            {data.videos.map((v) => (
              <tr key={v.id} data-testid="admin-video-row">
                <td><b>{v.title}</b>{v.is_synthetic && <small>Demonstrativo sintético</small>}</td>
                <td data-label="Categoria">{v.category_name}</td>
                <td data-label="Acesso">{v.access_level === "intro" ? "Introdutório" : "Assinantes"}</td>
                <td data-label="Situação"><span className={`status status-${v.status}`}>{v.status === "published" ? "Publicado" : "Rascunho"}</span></td>
                <td data-label="Arquivo">
                  {upload?.id === v.id ? `${upload.percent}%` : v.has_file ? formatTime(v.duration_seconds) : "Sem arquivo"}
                  <label className="file-link">
                    {v.has_file ? "Substituir" : "Enviar"}
                    <input type="file" accept="video/mp4,video/webm" aria-label={`Enviar arquivo de ${v.title}`} onChange={(e) => send(v, e.target.files[0])} disabled={!!upload} />
                  </label>
                </td>
                <td className="row-actions">
                  {confirming === v.id ? (
                    <>
                      <button className="link danger" onClick={() => { setConfirming(null); run(() => api(`/api/admin/videos/${v.id}`, { method: "DELETE" }), "Vídeo excluído."); }}>Confirmar exclusão</button>
                      <button className="link" onClick={() => setConfirming(null)}>Cancelar</button>
                    </>
                  ) : (
                    <>
                      <button className="link" onClick={() => setEditing(v)}>Editar</button>
                      <button className="link" onClick={() => run(
                        () => api(`/api/admin/videos/${v.id}`, { method: "PATCH", body: { status: v.status === "published" ? "draft" : "published" } }),
                        v.status === "published" ? "Vídeo movido para rascunho." : "Vídeo publicado.",
                      )}>{v.status === "published" ? "Despublicar" : "Publicar"}</button>
                      <button className="link danger" onClick={() => setConfirming(v.id)}>Excluir</button>
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Categories({ categories, reload }) {
  const [name, setName] = useState("");
  const [problem, setProblem] = useState(null);
  const [edits, setEdits] = useState({});

  const run = async (action) => {
    setProblem(null);
    try { await action(); reload(); } catch (e) { setProblem(e); }
  };

  return (
    <section>
      <div className="admin-head"><h2>Categorias</h2></div>
      {problem && <p className="form-error" role="alert">{problem.message}</p>}
      <form className="inline-form" onSubmit={(e) => { e.preventDefault(); run(async () => { await api("/api/admin/categories", { method: "POST", body: { name } }); setName(""); }); }}>
        <input aria-label="Nome da categoria" placeholder="Nome da nova categoria" value={name} onChange={(e) => setName(e.target.value)} />
        <button className="btn btn-primary">Criar categoria</button>
      </form>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Nome</th><th>Vídeos</th><th><span className="sr">Ações</span></th></tr></thead>
          <tbody>
            {categories.map((c) => (
              <tr key={c.id} data-testid="admin-category-row">
                <td><input aria-label={`Nome de ${c.name}`} value={edits[c.id] ?? c.name} onChange={(e) => setEdits({ ...edits, [c.id]: e.target.value })} /></td>
                <td data-label="Vídeos">{c.video_count}</td>
                <td className="row-actions">
                  <button className="link" disabled={!edits[c.id] || edits[c.id] === c.name} onClick={() => run(() => api(`/api/admin/categories/${c.id}`, { method: "PATCH", body: { name: edits[c.id], description: c.description } }))}>Salvar</button>
                  <button className="link danger" onClick={() => run(() => api(`/api/admin/categories/${c.id}`, { method: "DELETE" }))}>Excluir</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Users() {
  const { data, loading, error, reload } = useAsync(() => api("/api/admin/users"), []);
  const [problem, setProblem] = useState(null);
  if (loading) return <Loading />;
  if (error) return <ErrorBox error={error} onRetry={reload} />;

  const change = async (user, plan) => {
    setProblem(null);
    try {
      await api(`/api/admin/users/${user.id}`, { method: "PATCH", body: { plan } });
      reload();
    } catch (e) {
      setProblem(e);
    }
  };

  return (
    <section>
      <div className="admin-head"><h2>Assinaturas</h2></div>
      <p className="muted">A plataforma não tem pagamento. O administrador ativa ou encerra a assinatura de demonstração, e quem está no fim do teste pode ativar a oferta sozinho, sem cobrança.</p>
      {problem && <p className="form-error" role="alert">{problem.message}</p>}
      <div className="table-wrap">
        <table>
          <thead><tr><th>Pessoa</th><th>E-mail</th><th>Plano atual</th><th><span className="sr">Ações</span></th></tr></thead>
          <tbody>
            {data.users.map((u) => (
              <tr key={u.id} data-testid="admin-user-row">
                <td><b>{u.name}</b></td>
                <td data-label="E-mail">{u.email}</td>
                <td data-label="Plano">{PLAN_LABEL[u.plan_status]}</td>
                <td className="row-actions">
                  {u.role !== "admin" && (u.plan === "premium"
                    ? <button className="link" onClick={() => change(u, "trial")}>Encerrar assinatura</button>
                    : <button className="link" onClick={() => change(u, "premium")}>Ativar assinatura</button>)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default function Admin() {
  const [tab, setTab] = useState("videos");
  const cats = useAsync(() => api("/api/categories"), []);
  const tabs = [["videos", "Vídeos"], ["categorias", "Categorias"], ["usuarios", "Assinaturas"]];
  return (
    <div className="wrap page admin">
      <h1>Administração</h1>
      <div className="admin-tabs" role="tablist">
        {tabs.map(([id, label]) => <button key={id} role="tab" aria-selected={tab === id} onClick={() => { setTab(id); cats.reload(); }}>{label}</button>)}
      </div>
      {cats.loading && <Loading />}
      {cats.error && <ErrorBox error={cats.error} onRetry={cats.reload} />}
      {cats.data && tab === "videos" && <Videos categories={cats.data.categories} />}
      {cats.data && tab === "categorias" && <Categories categories={cats.data.categories} reload={cats.reload} />}
      {tab === "usuarios" && <Users />}
    </div>
  );
}
