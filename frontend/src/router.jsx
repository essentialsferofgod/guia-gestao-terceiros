import { useEffect, useState } from "react";

export function navigate(to, { replace = false } = {}) {
  history[replace ? "replaceState" : "pushState"](null, "", to);
  window.dispatchEvent(new Event("locationchange"));
  window.scrollTo(0, 0);
}

/** Aceita apenas destinos internos. */
export function safeNext(next, fallback = "/minha-aprendizagem") {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : fallback;
}

export function useLocation() {
  const read = () => ({ path: location.pathname, query: new URLSearchParams(location.search) });
  const [value, setValue] = useState(read);
  useEffect(() => {
    const update = () => setValue(read());
    window.addEventListener("popstate", update);
    window.addEventListener("locationchange", update);
    return () => {
      window.removeEventListener("popstate", update);
      window.removeEventListener("locationchange", update);
    };
  }, []);
  return value;
}

export function Link({ to, children, onClick, ...props }) {
  return (
    <a
      href={to}
      onClick={(e) => {
        onClick?.(e);
        if (e.defaultPrevented || e.metaKey || e.ctrlKey || e.shiftKey || e.button) return;
        e.preventDefault();
        navigate(to);
      }}
      {...props}
    >
      {children}
    </a>
  );
}
