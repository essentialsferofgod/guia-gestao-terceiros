import { useEffect } from "react";
import { createRoot } from "react-dom/client";
import { AuthProvider, useAuth } from "./auth";
import { Footer, Header } from "./components/Shell";
import { ErrorBox, Loading } from "./components/ui";
import Admin from "./pages/Admin";
import Catalog from "./pages/Catalog";
import Diagnostic from "./pages/Diagnostic";
import Home from "./pages/Home";
import Learning from "./pages/Learning";
import Login from "./pages/Login";
import WatchPage from "./pages/Player";
import Profiles from "./pages/Profiles";
import Result from "./pages/Result";
import { navigate, useLocation } from "./router";
import "./styles.css";

function Redirect({ to }) {
  useEffect(() => navigate(to, { replace: true }), [to]);
  return null;
}

function Private({ path, children, admin }) {
  const { user } = useAuth();
  if (!user) return <Redirect to={`/entrar?next=${encodeURIComponent(path)}`} />;
  if (admin && user.role !== "admin") {
    return <div className="wrap page narrow"><h1>Área restrita</h1><p className="muted">Esta área é exclusiva para administradores.</p></div>;
  }
  return children;
}

function Routes() {
  const { path } = useLocation();
  const { ready, offline, user } = useAuth();
  if (!ready) return <div className="wrap page"><Loading /></div>;
  if (offline) return <div className="wrap page"><ErrorBox error={{ message: offline }} onRetry={() => location.reload()} /></div>;

  // A tela de login conduz sozinha a escolha, para não perder a trilha pendente.
  if (user?.needs_profile && path !== "/perfis" && path !== "/entrar") {
    return <Redirect to={`/perfis?next=${encodeURIComponent(path + location.search)}`} />;
  }

  const watch = path.match(/^\/assistir\/(\d+)$/);
  if (path === "/") return <Home />;
  if (path === "/catalogo") return <Catalog />;
  if (path === "/entrar") return <Login />;
  if (path === "/diagnostico") return <Diagnostic />;
  if (path === "/diagnostico/resultado") return <Result />;
  if (watch) return <WatchPage key={watch[1]} id={watch[1]} />;
  if (path === "/perfis") return <Private path={path}><Profiles /></Private>;
  if (path === "/minha-aprendizagem") return <Private path={path}><Learning /></Private>;
  if (path === "/admin") return <Private path={path} admin><Admin /></Private>;
  return <div className="wrap page narrow"><h1>Página não encontrada</h1><p className="muted">O endereço não existe. Volte ao catálogo para continuar.</p></div>;
}

createRoot(document.getElementById("root")).render(
  <AuthProvider>
    <a className="skip" href="#conteudo">Ir para o conteúdo</a>
    <Header />
    <main id="conteudo"><Routes /></main>
    <Footer />
  </AuthProvider>,
);
