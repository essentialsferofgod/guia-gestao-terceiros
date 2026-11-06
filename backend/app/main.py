"""API e servidor da aplicação Guia para a Gestão de Terceiros."""
import hashlib
import json
import logging
import os
import re
import secrets
import sqlite3
import uuid

from pydantic import ValidationError
from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.routing import Route

from . import config, db, diagnostic, schemas, security, seed
from .errors import ApiError

log = logging.getLogger("guia")
SAFE_FILE = re.compile(r"^[a-z0-9-]+\.(mp4|webm|jpg|png)$")
COMPLETED_RATIO = 0.92
# Tipos explícitos: no Windows, o Registro pode informar um tipo errado e o nosniff bloquearia o arquivo.
STATIC_TYPES = {
    ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".woff": "font/woff", ".png": "image/png",
}

VIDEO_SELECT = (
    "SELECT v.*, c.name AS category_name, c.slug AS category_slug "
    "FROM videos v JOIN categories c ON c.id = v.category_id"
)


# ---------- apoio ----------

async def parse(request: Request, model):
    if "application/json" not in request.headers.get("content-type", ""):
        raise ApiError(415, "json_required", "Envie os dados em formato JSON.")
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ApiError(400, "invalid_json", "Não foi possível ler os dados enviados.")
    return model.model_validate(body)


def int_param(request: Request, name: str) -> int:
    return int(request.path_params[name])


def user_public(user: dict) -> dict:
    status = security.plan_status(user)
    return {
        "id": user["id"], "name": user["name"], "email": user["email"], "role": user["role"],
        "plan": user["plan"], "plan_status": status, "trial_ends_at": user["trial_ends_at"],
        "company": user["company"], "job_title": user["job_title"], "offer": security.offer_state(user),
    }


def account_public(user: dict) -> dict:
    """Dados da sessão: a conta, seus perfis e quem está assistindo."""
    return {
        **user_public(user), "profiles": user["profiles"], "active_profile_id": user["profile_id"],
        "needs_profile": user["profile_id"] is None, "max_profiles": config.MAX_PROFILES,
    }


def video_public(row, user, progress=None) -> dict:
    allowed, reason = security.video_access(user, row)
    position = progress["position_seconds"] if progress else 0
    completed = bool(progress["completed"]) if progress else False
    return {
        "id": row["id"], "slug": row["slug"], "title": row["title"], "description": row["description"],
        "category": {"id": row["category_id"], "name": row["category_name"], "slug": row["category_slug"]},
        "access_level": row["access_level"], "duration_seconds": row["duration_seconds"],
        "thumb_url": f"/api/thumbs/{row['thumb_name']}" if row["thumb_name"] else None,
        "has_file": bool(row["file_name"]), "is_synthetic": bool(row["is_synthetic"]),
        "license_note": row["license_note"],
        "locked": not allowed, "lock_reason": reason,
        "lock_message": security.lock_message(user, reason),
        "position_seconds": position, "completed": completed,
    }


def progress_map(conn, user) -> dict:
    if not user or user["profile_id"] is None:
        return {}
    rows = conn.execute("SELECT * FROM progress WHERE profile_id = ?", (user["profile_id"],)).fetchall()
    return {r["video_id"]: r for r in rows}


def get_video(conn, video_id: int, include_drafts=False):
    sql = VIDEO_SELECT + " WHERE v.id = ?" + ("" if include_drafts else " AND v.status = 'published'")
    row = conn.execute(sql, (video_id,)).fetchone()
    if not row:
        raise ApiError(404, "video_not_found", "Vídeo não encontrado.")
    return row


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", db.unaccent(text)).strip("-")[:70] or "item"


def unique_slug(conn, table: str, base: str) -> str:
    slug, n = base, 2
    while conn.execute(f"SELECT 1 FROM {table} WHERE slug = ?", (slug,)).fetchone():
        slug, n = f"{base}-{n}", n + 1
    return slug


# ---------- autenticação e perfil ----------

async def register(request: Request):
    data = await parse(request, schemas.Register)
    password_hash = security.hash_password(data.password)
    with db.transaction() as conn:
        if conn.execute("SELECT 1 FROM users WHERE email = ?", (data.email,)).fetchone():
            raise ApiError(409, "email_in_use", "Já existe uma conta com este e-mail. Entre para continuar.")
        cur = conn.execute(
            "INSERT INTO users (name,email,password_hash,role,plan,trial_ends_at,created_at) "
            "VALUES (?,?,?,'subscriber','trial',?,?)",
            (data.name, data.email, password_hash, db.days_from_now(config.TRIAL_DAYS), db.now_iso()),
        )
        profile_id = db.add_profile(conn, cur.lastrowid, data.name)
        token = security.create_session(conn, cur.lastrowid, profile_id)
        user = dict(conn.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone())
        user = security.with_profiles(conn, user, profile_id)
    response = JSONResponse({"user": account_public(user)}, status_code=201)
    security.set_session_cookie(response, token)
    return response


async def login(request: Request):
    data = await parse(request, schemas.Login)
    key = f"{request.client.host if request.client else 'local'}:{data.email}"
    security.limiter.check(key)
    with db.transaction() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (data.email,)).fetchone()
    valid = security.verify_password(data.password, row["password_hash"] if row else security.DUMMY_HASH)
    if not row or not valid:
        security.limiter.fail(key)
        raise ApiError(401, "invalid_credentials", "E-mail ou senha incorretos.")
    security.limiter.reset(key)
    with db.transaction() as conn:
        user = security.with_profiles(conn, dict(row))
        token = security.create_session(conn, row["id"], user["profile_id"])
    response = JSONResponse({"user": account_public(user)})
    security.set_session_cookie(response, token)
    return response


async def logout(request: Request):
    token = request.cookies.get(config.COOKIE_NAME)
    if token:
        with db.transaction() as conn:
            security.destroy_session(conn, token)
    response = JSONResponse({"ok": True})
    security.clear_session_cookie(response)
    return response


async def me(request: Request):
    user = security.current_user(request)
    return JSONResponse({"user": account_public(user) if user else None})


async def update_me(request: Request):
    user = security.require_user(request)
    data = await parse(request, schemas.ProfileUpdate)
    fields = data.model_dump(exclude_none=True)
    if fields:
        assignments = ", ".join(f"{k} = ?" for k in fields)
        with db.transaction() as conn:
            conn.execute(f"UPDATE users SET {assignments} WHERE id = ?", (*fields.values(), user["id"]))
    user.update(fields)
    return JSONResponse({"user": account_public(user)})


# ---------- perfis ----------

def owned_profile(conn, user: dict, profile_id: int):
    row = conn.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
    if not row:
        raise ApiError(404, "profile_not_found", "Perfil não encontrado.")
    if row["user_id"] != user["id"]:
        raise ApiError(403, "profile_forbidden", "Este perfil não pertence à sua conta.")
    return row


def name_in_use() -> ApiError:
    return ApiError(409, "profile_name_in_use", "Já existe um perfil com este nome nesta conta.")


async def list_profiles(request: Request):
    user = security.require_user(request)
    return JSONResponse({"profiles": user["profiles"], "active_profile_id": user["profile_id"],
                         "max_profiles": config.MAX_PROFILES})


async def create_profile(request: Request):
    user = security.require_user(request)
    data = await parse(request, schemas.ProfileIn)
    try:
        with db.transaction() as conn:
            profile_id = db.add_profile(conn, user["id"], data.name)
    except sqlite3.IntegrityError:
        raise name_in_use()
    if profile_id is None:
        raise ApiError(409, "profile_limit", f"Cada conta pode ter até {config.MAX_PROFILES} perfis.")
    return JSONResponse({"profile": {"id": profile_id, "name": data.name},
                         "user": account_public(security.current_user(request))}, status_code=201)


async def rename_profile(request: Request):
    user = security.require_user(request)
    profile_id = int_param(request, "id")
    with db.transaction() as conn:
        owned_profile(conn, user, profile_id)
    data = await parse(request, schemas.ProfileIn)
    try:
        with db.transaction() as conn:
            conn.execute("UPDATE profiles SET name = ? WHERE id = ?", (data.name, profile_id))
    except sqlite3.IntegrityError:
        raise name_in_use()
    return JSONResponse({"user": account_public(security.current_user(request))})


async def delete_profile(request: Request):
    """Apaga o perfil com seu progresso e suas trilhas. A conta sempre mantém ao menos um."""
    user = security.require_user(request)
    profile_id = int_param(request, "id")
    with db.transaction() as conn:
        owned_profile(conn, user, profile_id)
        cur = conn.execute(
            "DELETE FROM profiles WHERE id = ? AND (SELECT COUNT(*) FROM profiles WHERE user_id = ?) > 1",
            (profile_id, user["id"]),
        )
    if not cur.rowcount:
        raise ApiError(409, "last_profile", "A conta precisa manter ao menos um perfil.")
    return JSONResponse({"user": account_public(security.current_user(request))})


async def choose_profile(request: Request):
    user = security.require_user(request)
    profile_id = int_param(request, "id")
    with db.transaction() as conn:
        owned_profile(conn, user, profile_id)
        security.select_profile(conn, request.cookies[config.COOKIE_NAME], profile_id)
    return JSONResponse({"user": account_public(security.current_user(request))})


# ---------- oferta de fim de teste ----------

async def activate_offer(request: Request):
    """Ativação simulada pelo próprio usuário: muda o plano da conta, sem nenhuma cobrança."""
    user = security.require_user(request)
    offer = security.offer_state(user)
    if offer and offer["status"] == "activated":  # Repetir o pedido não muda nada.
        return JSONResponse({"user": account_public(user)})
    if not offer or offer["status"] != "available":
        raise ApiError(409, "offer_unavailable", "Esta oferta não está disponível para a sua conta.")
    with db.transaction() as conn:
        conn.execute(
            "UPDATE users SET plan = 'premium', offer_activated_at = ? "
            "WHERE id = ? AND plan = 'trial' AND offer_activated_at IS NULL",
            (db.now_iso(), user["id"]),
        )
    return JSONResponse({"user": account_public(security.current_user(request))})


# ---------- catálogo ----------

async def categories(request: Request):
    with db.transaction() as conn:
        rows = conn.execute(
            "SELECT c.*, (SELECT COUNT(*) FROM videos v WHERE v.category_id = c.id) AS video_count "
            "FROM categories c ORDER BY position, name"
        ).fetchall()
    return JSONResponse({"categories": [dict(r) for r in rows]})


async def list_videos(request: Request):
    user = security.current_user(request)
    q = db.unaccent(request.query_params.get("q", "").strip())[:80]
    category = request.query_params.get("category", "").strip()[:60]
    sql = VIDEO_SELECT + " WHERE v.status = 'published'"
    args: list = []
    if q:
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        like = f"%{escaped}%"
        sql += (" AND (unaccent(v.title) LIKE ? ESCAPE '\\' OR unaccent(v.description) LIKE ? ESCAPE '\\'"
                " OR unaccent(c.name) LIKE ? ESCAPE '\\')")
        args += [like, like, like]
    if category:
        sql += " AND c.slug = ?"
        args.append(category)
    sql += " ORDER BY c.position, v.id"
    with db.transaction() as conn:
        rows = conn.execute(sql, args).fetchall()
        prog = progress_map(conn, user)
    return JSONResponse({"videos": [video_public(r, user, prog.get(r["id"])) for r in rows]})


async def video_detail(request: Request):
    user = security.current_user(request)
    with db.transaction() as conn:
        admin = bool(user and user["role"] == "admin")
        row = get_video(conn, int_param(request, "id"), include_drafts=admin)
        prog = progress_map(conn, user).get(row["id"])
    payload = video_public(row, user, prog)
    if payload["locked"]:
        payload["position_seconds"] = 0
        payload["stream_url"] = None
    else:
        payload["stream_url"] = f"/api/videos/{row['id']}/stream" if row["file_name"] else None
    resume = payload["position_seconds"]
    if payload["completed"] and (not row["duration_seconds"] or resume >= row["duration_seconds"] * COMPLETED_RATIO):
        resume = 0
    payload["resume_seconds"] = resume
    return JSONResponse({"video": payload})


async def stream_video(request: Request):
    """Entrega o arquivo apenas depois de validar sessão e plano. Aceita Range para avançar no vídeo."""
    user = security.current_user(request)
    with db.transaction() as conn:
        admin = bool(user and user["role"] == "admin")
        row = get_video(conn, int_param(request, "id"), include_drafts=admin)
    allowed, reason = security.video_access(user, row)
    if not allowed:
        status = 401 if reason == "login_required" else 403
        raise ApiError(status, reason, security.lock_message(user, reason))
    if not row["file_name"] or not SAFE_FILE.match(row["file_name"]):
        raise ApiError(404, "file_unavailable", "O arquivo deste vídeo ainda não foi enviado.")
    path = config.VIDEO_DIR / row["file_name"]
    if not path.exists():
        raise ApiError(404, "file_unavailable", "O arquivo deste vídeo não foi encontrado.")
    media_type = "video/webm" if path.suffix == ".webm" else "video/mp4"
    return FileResponse(path, media_type=media_type, headers={"Cache-Control": "private, no-store"})


async def thumb(request: Request):
    name = request.path_params["name"]
    path = config.THUMB_DIR / name
    if not SAFE_FILE.match(name) or not path.exists():
        raise ApiError(404, "thumb_not_found", "Imagem não encontrada.")
    media_type = "image/png" if path.suffix == ".png" else "image/jpeg"
    return FileResponse(path, media_type=media_type, headers={"Cache-Control": "public, max-age=3600"})


# ---------- progresso e aprendizagem ----------

async def save_progress(request: Request):
    user = security.require_profile(request)
    data = await parse(request, schemas.ProgressUpdate)
    with db.transaction() as conn:
        row = get_video(conn, int_param(request, "id"), include_drafts=user["role"] == "admin")
        allowed, reason = security.video_access(user, row)
        if not allowed:
            raise ApiError(403, reason, security.lock_message(user, reason))
        duration = row["duration_seconds"]
        if not duration and data.duration_seconds:
            duration = round(data.duration_seconds)
            conn.execute("UPDATE videos SET duration_seconds = ? WHERE id = ?", (duration, row["id"]))
        position = min(data.position_seconds, duration) if duration else data.position_seconds
        done = 1 if duration and position >= duration * COMPLETED_RATIO else 0
        stamp = db.now_iso()
        conn.execute(
            "INSERT INTO progress (profile_id,video_id,position_seconds,completed,first_watched_at,last_watched_at) "
            "VALUES (?,?,?,?,?,?) ON CONFLICT (profile_id,video_id) DO UPDATE SET "
            "position_seconds = excluded.position_seconds, "
            "completed = MAX(progress.completed, excluded.completed), "
            "last_watched_at = excluded.last_watched_at",
            (user["profile_id"], row["id"], position, done, stamp, stamp),
        )
        saved = conn.execute(
            "SELECT * FROM progress WHERE profile_id = ? AND video_id = ?", (user["profile_id"], row["id"])
        ).fetchone()
    return JSONResponse({"position_seconds": saved["position_seconds"], "completed": bool(saved["completed"])})


def path_view(conn, row, user) -> dict:
    result = json.loads(row["result_json"])
    prog = progress_map(conn, user)
    items = []
    done = 0
    for item in result["path"]:
        video = conn.execute(VIDEO_SELECT + " WHERE v.slug = ? AND v.status = 'published'", (item["slug"],)).fetchone()
        if not video:
            continue
        public = video_public(video, user, prog.get(video["id"]))
        done += 1 if public["completed"] else 0
        items.append({**item, "video": public})
    result["path"] = items
    return {
        "id": row["id"], "created_at": row["created_at"], "result": result,
        "done": done, "total": len(items),
    }


async def learning(request: Request):
    user = security.require_profile(request)
    with db.transaction() as conn:
        rows = conn.execute(
            VIDEO_SELECT.replace("SELECT v.*,", "SELECT v.*, p.position_seconds, p.completed, p.last_watched_at,")
            + " JOIN progress p ON p.video_id = v.id WHERE p.profile_id = ? AND v.status = 'published' "
              "ORDER BY p.last_watched_at DESC, v.id",
            (user["profile_id"],),
        ).fetchall()
        paths = conn.execute(
            "SELECT * FROM saved_paths WHERE profile_id = ? ORDER BY created_at DESC, id DESC", (user["profile_id"],)
        ).fetchall()
        path_views = [path_view(conn, p, user) for p in paths]
        total = conn.execute("SELECT COUNT(*) AS n FROM videos WHERE status = 'published'").fetchone()["n"]

    history, keep_watching = [], []
    for row in rows:
        item = video_public(row, user, row)
        item["last_watched_at"] = row["last_watched_at"]
        history.append(item)
        if not item["completed"] and not item["locked"] and item["position_seconds"] > 0:
            keep_watching.append(item)
    completed = sum(1 for h in history if h["completed"])
    return JSONResponse({
        "continue_watching": keep_watching,
        "history": history,
        "paths": path_views,
        "stats": {"started": len(history), "completed": completed, "catalog_total": total},
    })


# ---------- diagnóstico e trilhas ----------

def published_slugs(conn) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT slug FROM videos WHERE status = 'published'").fetchall()]


def expand_result(conn, result: dict, user) -> dict:
    prog = progress_map(conn, user)
    expanded = []
    for item in result["path"]:
        video = conn.execute(VIDEO_SELECT + " WHERE v.slug = ?", (item["slug"],)).fetchone()
        expanded.append({**item, "video": video_public(video, user, prog.get(video["id"]))})
    return {**result, "path": expanded}


async def diagnostic_flow(request: Request):
    return JSONResponse(diagnostic.public_flow())


async def diagnostic_evaluate(request: Request):
    data = await parse(request, schemas.Evaluate)
    user = security.current_user(request)
    with db.transaction() as conn:
        result = diagnostic.evaluate(data.situation, data.answers, published_slugs(conn))
        return JSONResponse({"result": expand_result(conn, result, user)})


async def list_paths(request: Request):
    user = security.require_profile(request)
    with db.transaction() as conn:
        rows = conn.execute(
            "SELECT * FROM saved_paths WHERE profile_id = ? ORDER BY created_at DESC, id DESC", (user["profile_id"],)
        ).fetchall()
        return JSONResponse({"paths": [path_view(conn, r, user) for r in rows]})


async def save_path(request: Request):
    """Recalcula o resultado no servidor. O cliente só envia as respostas."""
    user = security.require_profile(request)
    data = await parse(request, schemas.Evaluate)
    canonical = json.dumps({"s": data.situation, "a": data.answers}, sort_keys=True)
    fingerprint = hashlib.sha256(canonical.encode()).hexdigest()
    with db.transaction() as conn:
        result = diagnostic.evaluate(data.situation, data.answers, published_slugs(conn))
        conn.execute(
            "INSERT INTO saved_paths (profile_id,situation,answers_json,result_json,fingerprint,created_at) "
            "VALUES (?,?,?,?,?,?) ON CONFLICT (profile_id,fingerprint) DO NOTHING",
            (user["profile_id"], data.situation, json.dumps(data.answers, ensure_ascii=False),
             json.dumps(result, ensure_ascii=False), fingerprint, db.now_iso()),
        )
        row = conn.execute(
            "SELECT * FROM saved_paths WHERE profile_id = ? AND fingerprint = ?", (user["profile_id"], fingerprint)
        ).fetchone()
        return JSONResponse({"path": path_view(conn, row, user)}, status_code=201)


async def delete_path(request: Request):
    user = security.require_profile(request)
    with db.transaction() as conn:
        cur = conn.execute(
            "DELETE FROM saved_paths WHERE id = ? AND profile_id = ?", (int_param(request, "id"), user["profile_id"])
        )
    if not cur.rowcount:
        raise ApiError(404, "path_not_found", "Trilha não encontrada.")
    return JSONResponse({"ok": True})


# ---------- administração ----------

def admin_video(row) -> dict:
    return {
        "id": row["id"], "slug": row["slug"], "title": row["title"], "description": row["description"],
        "category_id": row["category_id"], "category_name": row["category_name"],
        "access_level": row["access_level"], "status": row["status"],
        "duration_seconds": row["duration_seconds"], "has_file": bool(row["file_name"]),
        "license_note": row["license_note"], "is_synthetic": bool(row["is_synthetic"]),
        "updated_at": row["updated_at"],
    }


def ensure_category(conn, category_id: int) -> None:
    if not conn.execute("SELECT 1 FROM categories WHERE id = ?", (category_id,)).fetchone():
        raise ApiError(422, "invalid_category", "Escolha uma categoria existente.")


async def admin_list_videos(request: Request):
    security.require_admin(request)
    with db.transaction() as conn:
        rows = conn.execute(VIDEO_SELECT + " ORDER BY v.id DESC").fetchall()
    return JSONResponse({"videos": [admin_video(r) for r in rows]})


async def admin_create_video(request: Request):
    security.require_admin(request)
    data = await parse(request, schemas.VideoCreate)
    if data.status == "published":
        raise ApiError(422, "file_required", "Envie o arquivo do vídeo antes de publicar.")
    with db.transaction() as conn:
        ensure_category(conn, data.category_id)
        stamp = db.now_iso()
        cur = conn.execute(
            "INSERT INTO videos (slug,title,description,category_id,access_level,status,duration_seconds,"
            "license_note,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (unique_slug(conn, "videos", slugify(data.title)), data.title, data.description, data.category_id,
             data.access_level, data.status, data.duration_seconds, data.license_note, stamp, stamp),
        )
        row = get_video(conn, cur.lastrowid, include_drafts=True)
    return JSONResponse({"video": admin_video(row)}, status_code=201)


async def admin_update_video(request: Request):
    security.require_admin(request)
    data = await parse(request, schemas.VideoUpdate)
    fields = data.model_dump(exclude_none=True)
    video_id = int_param(request, "id")
    with db.transaction() as conn:
        current = get_video(conn, video_id, include_drafts=True)
        if "category_id" in fields:
            ensure_category(conn, fields["category_id"])
        if fields.get("status") == "published" and not current["file_name"]:
            raise ApiError(422, "file_required", "Envie o arquivo do vídeo antes de publicar.")
        if fields:
            fields["updated_at"] = db.now_iso()
            assignments = ", ".join(f"{k} = ?" for k in fields)
            conn.execute(f"UPDATE videos SET {assignments} WHERE id = ?", (*fields.values(), video_id))
        row = get_video(conn, video_id, include_drafts=True)
    return JSONResponse({"video": admin_video(row)})


def _remove_media(row) -> None:
    # Os arquivos demonstrativos fazem parte do repositório e não são apagados.
    if row["is_synthetic"]:
        return
    for folder, name in ((config.VIDEO_DIR, row["file_name"]), (config.THUMB_DIR, row["thumb_name"])):
        if name and SAFE_FILE.match(name):
            (folder / name).unlink(missing_ok=True)


async def admin_delete_video(request: Request):
    security.require_admin(request)
    with db.transaction() as conn:
        row = get_video(conn, int_param(request, "id"), include_drafts=True)
        conn.execute("DELETE FROM videos WHERE id = ?", (row["id"],))
    _remove_media(row)
    return JSONResponse({"ok": True})


async def admin_upload_video(request: Request):
    """Recebe o arquivo como corpo da requisição, em blocos, sem carregá-lo na memória."""
    security.require_admin(request)
    video_id = int_param(request, "id")
    with db.transaction() as conn:
        row = get_video(conn, video_id, include_drafts=True)
    content_type = request.headers.get("content-type", "").split(";")[0].strip()
    extension = {"video/mp4": "mp4", "video/webm": "webm"}.get(content_type)
    if not extension:
        raise ApiError(415, "invalid_video_type", "Envie um arquivo MP4 ou WebM.")
    limit = config.MAX_UPLOAD_MB * 1024 * 1024
    config.VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{row['slug']}-{secrets.token_hex(4)}.{extension}"
    temp = config.VIDEO_DIR / f"{uuid.uuid4().hex}.part"
    size = 0
    head = b""
    try:
        with open(temp, "wb") as handle:
            async for chunk in request.stream():
                size += len(chunk)
                if size > limit:
                    raise ApiError(413, "file_too_large", f"O arquivo ultrapassa {config.MAX_UPLOAD_MB} MB.")
                if len(head) < 16:
                    head += chunk[:16]
                handle.write(chunk)
        valid = (extension == "mp4" and head[4:8] == b"ftyp") or (extension == "webm" and head[:4] == b"\x1a\x45\xdf\xa3")
        if not valid:
            raise ApiError(422, "invalid_video_file", "O conteúdo do arquivo não é um vídeo válido.")
        final = config.VIDEO_DIR / name
        os.replace(temp, final)
    finally:
        temp.unlink(missing_ok=True)

    duration = seed.probe_duration(final)
    with db.transaction() as conn:
        conn.execute(
            "UPDATE videos SET file_name = ?, duration_seconds = CASE WHEN ? > 0 THEN ? ELSE duration_seconds END, "
            "updated_at = ? WHERE id = ?",
            (name, duration, duration, db.now_iso(), video_id),
        )
        updated = get_video(conn, video_id, include_drafts=True)
    if row["file_name"] and not row["is_synthetic"] and SAFE_FILE.match(row["file_name"]):
        (config.VIDEO_DIR / row["file_name"]).unlink(missing_ok=True)
    return JSONResponse({"video": admin_video(updated)})


async def admin_create_category(request: Request):
    security.require_admin(request)
    data = await parse(request, schemas.CategoryIn)
    with db.transaction() as conn:
        if conn.execute("SELECT 1 FROM categories WHERE name = ?", (data.name,)).fetchone():
            raise ApiError(409, "category_exists", "Já existe uma categoria com este nome.")
        position = conn.execute("SELECT COALESCE(MAX(position), 0) + 1 AS p FROM categories").fetchone()["p"]
        cur = conn.execute(
            "INSERT INTO categories (name,slug,description,position) VALUES (?,?,?,?)",
            (data.name, unique_slug(conn, "categories", slugify(data.name)), data.description, position),
        )
        row = conn.execute("SELECT * FROM categories WHERE id = ?", (cur.lastrowid,)).fetchone()
    return JSONResponse({"category": dict(row)}, status_code=201)


async def admin_update_category(request: Request):
    security.require_admin(request)
    data = await parse(request, schemas.CategoryIn)
    category_id = int_param(request, "id")
    with db.transaction() as conn:
        if conn.execute("SELECT 1 FROM categories WHERE name = ? AND id != ?", (data.name, category_id)).fetchone():
            raise ApiError(409, "category_exists", "Já existe uma categoria com este nome.")
        cur = conn.execute(
            "UPDATE categories SET name = ?, description = ? WHERE id = ?", (data.name, data.description, category_id)
        )
        if not cur.rowcount:
            raise ApiError(404, "category_not_found", "Categoria não encontrada.")
        row = conn.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()
    return JSONResponse({"category": dict(row)})


async def admin_delete_category(request: Request):
    security.require_admin(request)
    category_id = int_param(request, "id")
    with db.transaction() as conn:
        if conn.execute("SELECT 1 FROM videos WHERE category_id = ? LIMIT 1", (category_id,)).fetchone():
            raise ApiError(409, "category_in_use", "Mova ou exclua os vídeos desta categoria antes de excluí-la.")
        cur = conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))
    if not cur.rowcount:
        raise ApiError(404, "category_not_found", "Categoria não encontrada.")
    return JSONResponse({"ok": True})


async def admin_list_users(request: Request):
    security.require_admin(request)
    with db.transaction() as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY created_at DESC, id DESC").fetchall()
    return JSONResponse({"users": [user_public(dict(r)) for r in rows]})


async def admin_update_user(request: Request):
    security.require_admin(request)
    data = await parse(request, schemas.UserAdminUpdate)
    user_id = int_param(request, "id")
    with db.transaction() as conn:
        target = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not target:
            raise ApiError(404, "user_not_found", "Usuário não encontrado.")
        if target["role"] == "admin":
            raise ApiError(422, "admin_plan_fixed", "O plano de administradores não pode ser alterado.")
        trial_ends = target["trial_ends_at"]
        if data.plan == "trial" and not trial_ends:
            trial_ends = db.days_from_now(config.TRIAL_DAYS)
        conn.execute("UPDATE users SET plan = ?, trial_ends_at = ? WHERE id = ?", (data.plan, trial_ends, user_id))
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return JSONResponse({"user": user_public(dict(row))})


# ---------- infraestrutura ----------

async def health(request: Request):
    with db.transaction() as conn:
        conn.execute("SELECT 1").fetchone()
    return JSONResponse({"status": "ok"})


async def api_not_found(request: Request):
    raise ApiError(404, "not_found", "Recurso não encontrado.")


async def spa(request: Request):
    """Serve a aplicação React para qualquer rota fora da API."""
    relative = request.path_params.get("path", "")
    candidate = (config.DIST_DIR / relative).resolve()
    if relative and candidate.is_file() and candidate.is_relative_to(config.DIST_DIR.resolve()):
        return FileResponse(candidate, media_type=STATIC_TYPES.get(candidate.suffix))
    index = config.DIST_DIR / "index.html"
    if not index.exists():
        return Response("Frontend não compilado. Veja o README.", status_code=503)
    return FileResponse(index, media_type=STATIC_TYPES[".html"], headers={"Cache-Control": "no-cache"})


class SecurityHeaders(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; media-src 'self' blob:; "
            "style-src 'self' 'unsafe-inline'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
        )
        return response


async def on_api_error(request, exc: ApiError):
    return JSONResponse({"error": {"code": exc.code, "message": exc.message, **exc.extra}}, status_code=exc.status)


async def on_validation_error(request, exc: ValidationError):
    fields = {}
    for item in exc.errors():
        field = ".".join(str(p) for p in item["loc"]) or "geral"
        message = item["msg"].removeprefix("Value error, ")
        if item["type"] != "value_error":
            message = "Verifique este campo."
        fields.setdefault(field, message)
    return JSONResponse(
        {"error": {"code": "validation_error", "message": "Revise os campos informados.", "fields": fields}},
        status_code=422,
    )


async def on_http_error(request, exc: HTTPException):
    return JSONResponse({"error": {"code": "http_error", "message": "Requisição inválida."}}, status_code=exc.status_code)


async def on_unexpected(request, exc: Exception):
    log.exception("Erro inesperado em %s", request.url.path)
    return JSONResponse({"error": {"code": "internal_error", "message": "Erro interno. Tente novamente."}}, status_code=500)


NUM = "{id:int}"
routes = [
    Route("/api/health", health),
    Route("/api/auth/register", register, methods=["POST"]),
    Route("/api/auth/login", login, methods=["POST"]),
    Route("/api/auth/logout", logout, methods=["POST"]),
    Route("/api/me", me, methods=["GET"]),
    Route("/api/me", update_me, methods=["PATCH"]),
    Route("/api/me/learning", learning),
    Route("/api/profiles", list_profiles, methods=["GET"]),
    Route("/api/profiles", create_profile, methods=["POST"]),
    Route(f"/api/profiles/{NUM}", rename_profile, methods=["PATCH"]),
    Route(f"/api/profiles/{NUM}", delete_profile, methods=["DELETE"]),
    Route(f"/api/profiles/{NUM}/select", choose_profile, methods=["POST"]),
    Route("/api/offer/activate", activate_offer, methods=["POST"]),
    Route("/api/categories", categories),
    Route("/api/videos", list_videos),
    Route(f"/api/videos/{NUM}", video_detail),
    Route(f"/api/videos/{NUM}/stream", stream_video),
    Route("/api/thumbs/{name}", thumb),
    Route(f"/api/progress/{NUM}", save_progress, methods=["PUT"]),
    Route("/api/diagnostic/flow", diagnostic_flow),
    Route("/api/diagnostic/evaluate", diagnostic_evaluate, methods=["POST"]),
    Route("/api/paths", list_paths, methods=["GET"]),
    Route("/api/paths", save_path, methods=["POST"]),
    Route(f"/api/paths/{NUM}", delete_path, methods=["DELETE"]),
    Route("/api/admin/videos", admin_list_videos, methods=["GET"]),
    Route("/api/admin/videos", admin_create_video, methods=["POST"]),
    Route(f"/api/admin/videos/{NUM}", admin_update_video, methods=["PATCH"]),
    Route(f"/api/admin/videos/{NUM}", admin_delete_video, methods=["DELETE"]),
    Route(f"/api/admin/videos/{NUM}/file", admin_upload_video, methods=["PUT"]),
    Route("/api/admin/categories", admin_create_category, methods=["POST"]),
    Route(f"/api/admin/categories/{NUM}", admin_update_category, methods=["PATCH"]),
    Route(f"/api/admin/categories/{NUM}", admin_delete_category, methods=["DELETE"]),
    Route("/api/admin/users", admin_list_users, methods=["GET"]),
    Route(f"/api/admin/users/{NUM}", admin_update_user, methods=["PATCH"]),
    Route("/api/{rest:path}", api_not_found, methods=["GET", "POST", "PUT", "PATCH", "DELETE"]),
    Route("/{path:path}", spa, methods=["GET", "HEAD"]),
]


def startup():
    db.init_db()
    if config.SEED_ON_START:
        seed.run()


from contextlib import asynccontextmanager  # noqa: E402


@asynccontextmanager
async def lifespan(app):
    startup()
    yield


app = Starlette(
    routes=routes,
    middleware=[Middleware(SecurityHeaders)],
    exception_handlers={
        ApiError: on_api_error,
        ValidationError: on_validation_error,
        HTTPException: on_http_error,
        Exception: on_unexpected,
    },
    lifespan=lifespan,
)
