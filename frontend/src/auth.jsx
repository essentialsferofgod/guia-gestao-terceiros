import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, pending } from "./api";
import { navigate } from "./router";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);
  const [offline, setOffline] = useState(null);

  useEffect(() => {
    api("/api/me")
      .then((d) => setUser(d.user))
      .catch((e) => setOffline(e.message))
      .finally(() => setReady(true));
  }, []);

  const login = useCallback(async (body) => {
    const data = await api("/api/auth/login", { method: "POST", body });
    setUser(data.user);
    return data.user;
  }, []);

  const register = useCallback(async (body) => {
    const data = await api("/api/auth/register", { method: "POST", body });
    setUser(data.user);
    return data.user;
  }, []);

  const refresh = useCallback(async () => {
    const data = await api("/api/me");
    setUser(data.user);
  }, []);

  const logout = useCallback(async () => {
    await api("/api/auth/logout", { method: "POST" });
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, ready, offline, setUser, login, register, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);

/** Depois do login: leva à escolha do perfil, se preciso, e só então salva a trilha pendente. */
export async function finishEntry({ account, next, saving }) {
  if (account.needs_profile) {
    navigate(`/perfis?next=${encodeURIComponent(next)}${saving ? "&salvar=1" : ""}`, { replace: true });
    return;
  }
  const draft = pending.read();
  if (saving && draft) {
    await api("/api/paths", { method: "POST", body: { situation: draft.situation, answers: draft.answers } });
    pending.clear();
    navigate("/minha-aprendizagem?trilha=salva", { replace: true });
  } else {
    navigate(next, { replace: true });
  }
}
