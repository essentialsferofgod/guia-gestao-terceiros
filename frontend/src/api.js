export class ApiError extends Error {
  constructor(status, body) {
    super(body?.error?.message || "Não foi possível concluir a ação.");
    this.status = status;
    this.code = body?.error?.code;
    this.fields = body?.error?.fields || {};
  }
}

export async function api(path, { method = "GET", body, keepalive } = {}) {
  let response;
  try {
    response = await fetch(path, {
      method,
      keepalive,
      credentials: "same-origin",
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, { error: { message: "Sem conexão com o servidor. Verifique se a aplicação está em execução." } });
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(response.status, data);
  return data;
}

export function uploadVideo(id, file, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", `/api/admin/videos/${id}/file`);
    xhr.setRequestHeader("Content-Type", file.type);
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(Math.round((e.loaded / e.total) * 100));
    xhr.onload = () => {
      let data = null;
      try { data = JSON.parse(xhr.responseText); } catch { /* resposta vazia */ }
      xhr.status < 300 ? resolve(data) : reject(new ApiError(xhr.status, data));
    };
    xhr.onerror = () => reject(new ApiError(0, { error: { message: "O envio foi interrompido. Tente novamente." } }));
    xhr.send(file);
  });
}

const PENDING_KEY = "guia.diagnostico";

export const pending = {
  read() {
    try { return JSON.parse(sessionStorage.getItem(PENDING_KEY)); } catch { return null; }
  },
  write(value) {
    try { sessionStorage.setItem(PENDING_KEY, JSON.stringify(value)); } catch { /* navegação privada */ }
  },
  clear() {
    try { sessionStorage.removeItem(PENDING_KEY); } catch { /* navegação privada */ }
  },
};

export function formatTime(seconds = 0) {
  const total = Math.max(0, Math.round(seconds));
  const m = Math.floor(total / 60);
  return `${m}:${String(total % 60).padStart(2, "0")}`;
}

export function formatDate(iso) {
  return iso ? new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "short", year: "numeric" }) : "";
}

export const PLAN_LABEL = {
  admin: "Administrador",
  premium: "Assinante",
  trial: "Básico, teste de 14 dias",
  trial_expired: "Teste encerrado",
  anonymous: "Visitante",
};
