import { useCallback, useEffect, useState } from "react";

/** Carrega dados e expõe os estados de carregamento, erro e recarga. */
export function useAsync(loader, deps) {
  const [state, setState] = useState({ loading: true, data: null, error: null });
  const load = useCallback(loader, deps);

  const reload = useCallback(() => {
    let active = true;
    load()
      .then((data) => active && setState({ loading: false, data, error: null }))
      .catch((error) => active && setState({ loading: false, data: null, error }));
    return () => { active = false; };
  }, [load]);

  useEffect(() => {
    setState((s) => ({ ...s, loading: true, error: null }));
    return reload();
  }, [reload]);

  return { ...state, reload };
}
