#!/usr/bin/env python3
"""Keil-friendly web file server (FastAPI + separated WebUI)."""

from __future__ import annotations

import argparse
import hashlib
import mimetypes
import os
import platform
import re
import socket
import sys
import tempfile
import threading
import urllib.parse
import uuid
import webbrowser
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from collections import deque

try:
    import uvicorn
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel
except ModuleNotFoundError as exc:
    missing = exc.name or "dependency"
    print(f"[ERROR] Missing dependency: {missing}")
    print("[HINT] Run:")
    print(
        "       uv pip install --python .venv/Scripts/python.exe -r requirements-build.txt"
    )
    raise SystemExit(1) from exc


TEXT_PREVIEW_LIMIT = 200_000
BINARY_PREVIEW_LIMIT = 65_536


def app_base_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


BASE_DIR = app_base_dir()
WEBUI_VUE_DIST_DIR = BASE_DIR / "webui-vue" / "dist"
WEBUI_VUE_ASSETS_DIR = WEBUI_VUE_DIST_DIR / "assets"


class RootState:
    def __init__(self, root: Path) -> None:
        self._lock = threading.Lock()
        self._root = root

    def get(self) -> Path:
        with self._lock:
            return self._root

    def set(self, root: Path) -> None:
        with self._lock:
            self._root = root


def clean_relpath(value: str) -> str:
    return value.replace("\\", "/").strip("/")


def safe_target(root: Path, rel: str) -> Path:
    rel = clean_relpath(rel)
    target = (root / rel).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="path escapes root") from exc
    return target


def readable_size(size: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{int(value)}{unit}" if unit == "B" else f"{value:.1f}{unit}"
        value /= 1024
    return f"{size}B"


def content_disposition(filename: str) -> str:
    ascii_fallback = re.sub(r"[^A-Za-z0-9._-]", "_", filename) or "download"
    encoded = urllib.parse.quote(filename, safe="")
    return f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{encoded}"


def build_hex_preview(data: bytes, width: int = 16) -> str:
    lines = []
    for offset in range(0, len(data), width):
        chunk = data[offset : offset + width]
        hex_part = " ".join(f"{b:02x}" for b in chunk)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{offset:08x}  {hex_part:<47}  {ascii_part}")
    return "\n".join(lines)


def read_bytes_limit(path: Path, limit: int) -> bytes:
    with path.open("rb") as f:
        return f.read(limit)


def bytes_to_hex(data: bytes, max_len: int = 512) -> str:
    view = data[:max_len]
    out = " ".join(f"{b:02x}" for b in view)
    if len(data) > max_len:
        out += " ..."
    return out


def bytes_to_ascii(data: bytes, max_len: int = 512) -> str:
    view = data[:max_len]
    out = "".join(chr(b) if 32 <= b < 127 else "." for b in view)
    if len(data) > max_len:
        out += "..."
    return out


def read_text_preview(
    path: Path, byte_limit: int = TEXT_PREVIEW_LIMIT
) -> tuple[str, str, bool]:
    raw = read_bytes_limit(path, byte_limit + 1)
    truncated = len(raw) > byte_limit
    sample = raw[:byte_limit]
    for enc in ("utf-8", "gbk", "gb18030"):
        try:
            return sample.decode(enc), enc, truncated
        except UnicodeDecodeError:
            continue
    return sample.decode("utf-8", errors="replace"), "utf-8-replace", truncated


def guess_lan_ip() -> str | None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return None
    finally:
        sock.close()


def get_process_tree() -> dict:
    pid = os.getpid()
    result = {
        "current_pid": pid,
        "chain": [{"pid": pid, "name": Path(sys.executable).name}],
    }
    if os.name != "nt":
        result["note"] = "process tree detail currently implemented for Windows only"
        return result

    try:
        import ctypes
        from ctypes import wintypes

        TH32CS_SNAPPROCESS = 0x00000002
        INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value

        class PROCESSENTRY32W(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD),
                ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t),
                ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", ctypes.c_long),
                ("dwFlags", wintypes.DWORD),
                ("szExeFile", wintypes.WCHAR * 260),
            ]

        kernel32 = ctypes.windll.kernel32
        snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if snapshot == INVALID_HANDLE_VALUE:
            result["note"] = "CreateToolhelp32Snapshot failed"
            return result

        try:
            pe = PROCESSENTRY32W()
            pe.dwSize = ctypes.sizeof(PROCESSENTRY32W)
            proc_map: dict[int, tuple[int, str]] = {}

            if kernel32.Process32FirstW(snapshot, ctypes.byref(pe)):
                while True:
                    proc_map[int(pe.th32ProcessID)] = (
                        int(pe.th32ParentProcessID),
                        pe.szExeFile,
                    )
                    if not kernel32.Process32NextW(snapshot, ctypes.byref(pe)):
                        break

            chain = []
            cur = pid
            visited = set()
            while cur and cur not in visited and cur in proc_map and len(chain) < 16:
                visited.add(cur)
                ppid, name = proc_map[cur]
                chain.append({"pid": cur, "name": name, "parent_pid": ppid})
                cur = ppid

            if chain:
                result["chain"] = chain
                if len(chain) > 1:
                    result["parent"] = chain[1]
        finally:
            kernel32.CloseHandle(snapshot)
    except Exception as exc:  # noqa: BLE001
        result["note"] = f"process tree inspect failed: {exc}"

    return result


def get_loaded_modules(limit: int = 400, keyword: str = "") -> dict:
    pid = os.getpid()
    result = {"pid": pid, "modules": []}
    if os.name != "nt":
        result["note"] = "module listing currently implemented for Windows only"
        return result

    try:
        import ctypes
        from ctypes import wintypes

        TH32CS_SNAPMODULE = 0x00000008
        TH32CS_SNAPMODULE32 = 0x00000010
        INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value

        class MODULEENTRY32W(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD),
                ("th32ModuleID", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),
                ("GlblcntUsage", wintypes.DWORD),
                ("ProccntUsage", wintypes.DWORD),
                ("modBaseAddr", ctypes.POINTER(ctypes.c_ubyte)),
                ("modBaseSize", wintypes.DWORD),
                ("hModule", wintypes.HMODULE),
                ("szModule", wintypes.WCHAR * 256),
                ("szExePath", wintypes.WCHAR * 260),
            ]

        kernel32 = ctypes.windll.kernel32
        flags = TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32
        snapshot = kernel32.CreateToolhelp32Snapshot(flags, pid)
        if snapshot == INVALID_HANDLE_VALUE:
            result["note"] = "CreateToolhelp32Snapshot failed"
            return result

        try:
            me = MODULEENTRY32W()
            me.dwSize = ctypes.sizeof(MODULEENTRY32W)
            kw = keyword.lower().strip()
            modules = []
            if kernel32.Module32FirstW(snapshot, ctypes.byref(me)):
                while True:
                    entry = {
                        "name": me.szModule,
                        "path": me.szExePath,
                        "base_size": int(me.modBaseSize),
                    }
                    blob = f"{entry['name']} {entry['path']}".lower()
                    if not kw or kw in blob:
                        modules.append(entry)
                        if len(modules) >= limit:
                            break
                    if not kernel32.Module32NextW(snapshot, ctypes.byref(me)):
                        break
            result["modules"] = modules
            result["count"] = len(modules)
        finally:
            kernel32.CloseHandle(snapshot)
    except Exception as exc:  # noqa: BLE001
        result["note"] = f"module inspect failed: {exc}"

    return result


def file_probe(
    path: Path, head: int = 128, tail: int = 128, hash_mode: str = "sample"
) -> dict:
    size = path.stat().st_size
    with path.open("rb") as f:
        head_data = f.read(max(0, head))
        tail_data = b""
        if tail > 0 and size > 0:
            back = min(tail, size)
            f.seek(size - back)
            tail_data = f.read(back)

    sha256 = hashlib.sha256()
    if hash_mode == "full":
        with path.open("rb") as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                sha256.update(chunk)
        mode = "full"
    else:
        sample_size = min(size, 4 * 1024 * 1024)
        with path.open("rb") as f:
            sha256.update(f.read(sample_size))
        mode = f"sample:{sample_size}"

    return {
        "size_bytes": size,
        "sha256": sha256.hexdigest(),
        "hash_mode": mode,
        "head_hex": bytes_to_hex(head_data, max_len=head),
        "head_ascii": bytes_to_ascii(head_data, max_len=head),
        "tail_hex": bytes_to_hex(tail_data, max_len=tail),
        "tail_ascii": bytes_to_ascii(tail_data, max_len=tail),
    }


def sanitize_env(data: dict[str, str]) -> dict[str, str]:
    out = {}
    for k, v in data.items():
        key_u = k.upper()
        if any(x in key_u for x in ("SECRET", "TOKEN", "PASS", "PWD", "KEY")):
            out[k] = "***"
        else:
            out[k] = v
    return out


def build_debug_context(
    root: Path,
    include_all_env: bool = False,
    env_limit: int = 200,
    recent_access: list[dict] | None = None,
) -> dict:
    env_all = dict(os.environ)
    keil_env = {
        k: v
        for k, v in env_all.items()
        if any(token in k.upper() for token in ("KEIL", "UV4", "ARM", "MDK"))
    }
    common_env_keys = (
        "PATH",
        "PYTHONPATH",
        "COMSPEC",
        "PATHEXT",
        "SYSTEMROOT",
        "TEMP",
        "TMP",
        "USERNAME",
    )
    common_env = {k: env_all.get(k, "") for k in common_env_keys if k in env_all}

    payload = {
        "ok": True,
        "process": {
            "pid": os.getpid(),
            "platform": platform.platform(),
            "python": sys.version,
            "executable": sys.executable,
            "argv": sys.argv,
            "cwd": str(Path.cwd()),
            "base_dir": str(BASE_DIR),
            "frozen": bool(getattr(sys, "frozen", False)),
        },
        "process_tree": get_process_tree(),
        "root": str(root),
        "env": {
            "keil_related": sanitize_env(dict(sorted(keil_env.items()))),
            "common": sanitize_env(common_env),
        },
        "recent_access": recent_access if recent_access is not None else [],
    }

    if include_all_env:
        sorted_env = dict(sorted(env_all.items()))
        limited = dict(list(sorted_env.items())[:env_limit])
        payload["env"]["all_limited"] = sanitize_env(limited)

    return payload


class SetRootRequest(BaseModel):
    root: str


class CreateZipTaskRequest(BaseModel):
    path: str


class AccessLog:
    def __init__(self, max_items: int = 200) -> None:
        self._lock = threading.Lock()
        self._records: deque[dict] = deque(maxlen=max_items)

    def add(self, action: str, rel_path: str, target: Path, ok: bool = True) -> None:
        record = {
            "time": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "rel_path": rel_path,
            "abs_path": str(target),
            "ok": ok,
        }
        with self._lock:
            self._records.appendleft(record)

    def list(self, limit: int = 80) -> list[dict]:
        with self._lock:
            return list(self._records)[:limit]


class ZipTaskManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tasks: dict[str, dict] = {}
        self._task_dir = Path(tempfile.gettempdir()) / "keil_web_file_server_tasks"
        self._task_dir.mkdir(parents=True, exist_ok=True)

    def create_task(self, target_dir: Path) -> dict:
        task_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc).isoformat()
        zip_path = self._task_dir / f"{task_id}.zip"
        task = {
            "id": task_id,
            "path": str(target_dir),
            "name": target_dir.name,
            "status": "pending",
            "created_at": now,
            "updated_at": now,
            "error": "",
            "zip_path": str(zip_path),
            "download_name": f"{target_dir.name or 'folder'}.zip",
            "file_count": 0,
            "size_bytes": 0,
        }
        with self._lock:
            self._tasks[task_id] = task
            self._cleanup_locked(max_tasks=120)
        return dict(task)

    def get_task(self, task_id: str) -> dict | None:
        with self._lock:
            task = self._tasks.get(task_id)
            return dict(task) if task else None

    def list_tasks(self, limit: int = 30) -> list[dict]:
        with self._lock:
            values = list(self._tasks.values())
        values.sort(key=lambda t: t["created_at"], reverse=True)
        return [dict(v) for v in values[:limit]]

    def update_task(self, task_id: str, **changes: object) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return
            task.update(changes)
            task["updated_at"] = datetime.now(timezone.utc).isoformat()

    def _cleanup_locked(self, max_tasks: int) -> None:
        if len(self._tasks) <= max_tasks:
            return
        ordered = sorted(self._tasks.values(), key=lambda t: t["created_at"])
        remove_count = len(self._tasks) - max_tasks
        for task in ordered[:remove_count]:
            zip_path = Path(task["zip_path"])
            if zip_path.exists():
                try:
                    zip_path.unlink()
                except OSError:
                    pass
            self._tasks.pop(task["id"], None)

    def delete_task(self, task_id: str) -> tuple[bool, str]:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False, "task not found"
            if task["status"] in ("pending", "running"):
                return False, "task is running"
            zip_path = Path(task["zip_path"])
            if zip_path.exists():
                try:
                    zip_path.unlink()
                except OSError:
                    pass
            self._tasks.pop(task_id, None)
        return True, ""

    def run_zip_task(self, task_id: str, target_dir: Path) -> None:
        task = self.get_task(task_id)
        if not task:
            return
        zip_path = Path(task["zip_path"])
        self.update_task(task_id, status="running")
        try:
            file_count = 0
            with zipfile.ZipFile(
                zip_path, mode="w", compression=zipfile.ZIP_DEFLATED
            ) as zf:
                for file_path in target_dir.rglob("*"):
                    if file_path.is_file():
                        arcname = file_path.relative_to(target_dir).as_posix()
                        zf.write(file_path, arcname=arcname)
                        file_count += 1
            size_bytes = zip_path.stat().st_size if zip_path.exists() else 0
            self.update_task(
                task_id, status="done", file_count=file_count, size_bytes=size_bytes
            )
        except Exception as exc:  # noqa: BLE001
            self.update_task(task_id, status="failed", error=str(exc))


def create_app(initial_root: Path) -> FastAPI:
    app = FastAPI(title="Keil Web File Server", docs_url=None, redoc_url=None)
    root_state = RootState(initial_root)
    task_manager = ZipTaskManager()
    access_log = AccessLog()

    if WEBUI_VUE_DIST_DIR.exists() and WEBUI_VUE_ASSETS_DIR.exists():
        index_file = WEBUI_VUE_DIST_DIR / "index.html"
        app.mount("/assets", StaticFiles(directory=WEBUI_VUE_ASSETS_DIR), name="assets")
        print(f"[INFO] Using Vue WebUI: {WEBUI_VUE_DIST_DIR}")
    else:
        raise RuntimeError("Vue WebUI assets not found. Build webui-vue first.")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(index_file)

    @app.get("/api/list")
    def api_list(
        path: str = Query(default=""),
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=200, ge=1, le=1000),
        sort: str = Query(default="name_asc"),
    ) -> JSONResponse:
        root_dir = root_state.get()
        target = safe_target(root_dir, path)
        if not target.exists() or not target.is_dir():
            access_log.add("list", path, target, ok=False)
            return JSONResponse(
                {"ok": False, "error": "directory not found"}, status_code=400
            )
        access_log.add("list", path, target, ok=True)

        sortable: list[tuple[Path, int]] = []
        for entry in target.iterdir():
            size = 0 if entry.is_dir() else entry.stat().st_size
            sortable.append((entry, size))

        if sort == "name_desc":
            sortable.sort(key=lambda x: x[0].name.lower(), reverse=True)
            sortable.sort(key=lambda x: not x[0].is_dir())
        elif sort == "size_asc":
            sortable.sort(key=lambda x: (not x[0].is_dir(), x[1], x[0].name.lower()))
        elif sort == "size_desc":
            sortable.sort(key=lambda x: (not x[0].is_dir(), -x[1], x[0].name.lower()))
        else:
            sortable.sort(key=lambda x: (not x[0].is_dir(), x[0].name.lower()))

        total = len(sortable)
        total_pages = (total + page_size - 1) // page_size if total else 1
        if page > total_pages:
            page = total_pages

        start = (page - 1) * page_size
        end = start + page_size
        page_slice = sortable[start:end]

        items = []
        for entry, size in page_slice:
            rel_entry = clean_relpath(str(entry.relative_to(root_dir)))
            items.append(
                {
                    "name": entry.name,
                    "rel": rel_entry,
                    "is_dir": entry.is_dir(),
                    "size": "-" if entry.is_dir() else readable_size(size),
                }
            )

        current = clean_relpath(str(target.relative_to(root_dir)))
        return JSONResponse(
            {
                "ok": True,
                "root": str(root_dir),
                "current": current,
                "items": items,
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": total_pages,
                "sort": sort,
            }
        )

    @app.get("/api/file")
    def api_file(path: str = Query(default="")) -> JSONResponse:
        root_dir = root_state.get()
        target = safe_target(root_dir, path)
        if not target.exists() or not target.is_file():
            access_log.add("preview", path, target, ok=False)
            return JSONResponse(
                {"ok": False, "error": "file not found"}, status_code=400
            )
        access_log.add("preview", path, target, ok=True)

        size_bytes = target.stat().st_size
        mime = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        file_url = f"/api/file-content?path={urllib.parse.quote(path, safe='')}"

        if mime.startswith("image/"):
            return JSONResponse(
                {
                    "ok": True,
                    "path": clean_relpath(str(target.relative_to(root_dir))),
                    "kind": "image",
                    "mime": mime,
                    "size_bytes": size_bytes,
                    "url": file_url,
                }
            )

        if mime == "application/pdf":
            return JSONResponse(
                {
                    "ok": True,
                    "path": clean_relpath(str(target.relative_to(root_dir))),
                    "kind": "pdf",
                    "mime": mime,
                    "size_bytes": size_bytes,
                    "url": file_url,
                }
            )

        sample = read_bytes_limit(target, 4096)
        is_binary = b"\x00" in sample
        if is_binary:
            raw = read_bytes_limit(target, BINARY_PREVIEW_LIMIT)
            hex_text = build_hex_preview(raw)
            if size_bytes > BINARY_PREVIEW_LIMIT:
                hex_text += "\n\n... (binary preview truncated)"
            return JSONResponse(
                {
                    "ok": True,
                    "path": clean_relpath(str(target.relative_to(root_dir))),
                    "kind": "hex",
                    "mime": mime,
                    "size_bytes": size_bytes,
                    "encoding": "",
                    "truncated": size_bytes > BINARY_PREVIEW_LIMIT,
                    "content": hex_text,
                }
            )

        text, encoding, truncated = read_text_preview(target)
        if truncated:
            text += "\n\n... (content truncated)"

        return JSONResponse(
            {
                "ok": True,
                "path": clean_relpath(str(target.relative_to(root_dir))),
                "kind": "text",
                "mime": mime,
                "size_bytes": size_bytes,
                "encoding": encoding,
                "truncated": truncated,
                "content": text,
            }
        )

    @app.get("/api/file-content")
    def api_file_content(path: str = Query(default="")) -> StreamingResponse:
        root_dir = root_state.get()
        target = safe_target(root_dir, path)
        if not target.exists() or not target.is_file():
            access_log.add("file-content", path, target, ok=False)
            raise HTTPException(status_code=404, detail="file not found")
        access_log.add("file-content", path, target, ok=True)

        media_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"

        def iter_file() -> bytes:
            with target.open("rb") as f:
                while True:
                    chunk = f.read(1024 * 1024)
                    if not chunk:
                        break
                    yield chunk

        return StreamingResponse(iter_file(), media_type=media_type)

    @app.get("/api/download")
    def api_download(path: str = Query(default="")) -> StreamingResponse:
        root_dir = root_state.get()
        target = safe_target(root_dir, path)
        if not target.exists() or not target.is_file():
            access_log.add("download", path, target, ok=False)
            raise HTTPException(status_code=404, detail="file not found")
        access_log.add("download", path, target, ok=True)

        media_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        headers = {"Content-Disposition": content_disposition(target.name)}

        def iter_file() -> bytes:
            with target.open("rb") as f:
                while True:
                    chunk = f.read(1024 * 1024)
                    if not chunk:
                        break
                    yield chunk

        return StreamingResponse(iter_file(), media_type=media_type, headers=headers)

    @app.get("/api/download-folder")
    def api_download_folder(path: str = Query(default="")) -> StreamingResponse:
        root_dir = root_state.get()
        target = safe_target(root_dir, path)
        if not target.exists() or not target.is_dir():
            access_log.add("download-folder", path, target, ok=False)
            raise HTTPException(status_code=404, detail="directory not found")
        access_log.add("download-folder", path, target, ok=True)

        mem = BytesIO()
        with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for file_path in target.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(target).as_posix()
                    zf.write(file_path, arcname=arcname)

        payload = mem.getvalue()
        zip_name = f"{target.name or 'folder'}.zip"
        headers = {"Content-Disposition": content_disposition(zip_name)}
        return StreamingResponse(
            BytesIO(payload), media_type="application/zip", headers=headers
        )

    @app.post("/api/tasks/zip")
    def api_create_zip_task(body: CreateZipTaskRequest) -> JSONResponse:
        root_dir = root_state.get()
        target = safe_target(root_dir, body.path)
        if not target.exists() or not target.is_dir():
            access_log.add("create-zip-task", body.path, target, ok=False)
            return JSONResponse(
                {"ok": False, "error": "directory not found"}, status_code=400
            )
        access_log.add("create-zip-task", body.path, target, ok=True)

        task = task_manager.create_task(target)
        worker = threading.Thread(
            target=task_manager.run_zip_task, args=(task["id"], target), daemon=True
        )
        worker.start()
        return JSONResponse({"ok": True, "task": task})

    @app.get("/api/tasks")
    def api_list_tasks(limit: int = Query(default=30, ge=1, le=100)) -> JSONResponse:
        return JSONResponse({"ok": True, "tasks": task_manager.list_tasks(limit=limit)})

    @app.get("/api/tasks/{task_id}")
    def api_get_task(task_id: str) -> JSONResponse:
        task = task_manager.get_task(task_id)
        if not task:
            return JSONResponse(
                {"ok": False, "error": "task not found"}, status_code=404
            )
        return JSONResponse({"ok": True, "task": task})

    @app.get("/api/tasks/{task_id}/download")
    def api_download_task_zip(task_id: str) -> StreamingResponse:
        task = task_manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="task not found")
        if task["status"] != "done":
            raise HTTPException(status_code=409, detail="task not completed")

        zip_path = Path(task["zip_path"])
        if not zip_path.exists() or not zip_path.is_file():
            raise HTTPException(status_code=404, detail="archive not found")

        headers = {
            "Content-Disposition": content_disposition(str(task["download_name"]))
        }

        def iter_file() -> bytes:
            with zip_path.open("rb") as f:
                while True:
                    chunk = f.read(1024 * 1024)
                    if not chunk:
                        break
                    yield chunk

        return StreamingResponse(
            iter_file(), media_type="application/zip", headers=headers
        )

    @app.delete("/api/tasks/{task_id}")
    def api_delete_task(task_id: str) -> JSONResponse:
        ok, error = task_manager.delete_task(task_id)
        if not ok:
            status = 404 if error == "task not found" else 409
            return JSONResponse({"ok": False, "error": error}, status_code=status)
        return JSONResponse({"ok": True})

    @app.post("/api/root")
    def api_set_root(body: SetRootRequest) -> JSONResponse:
        raw = body.root.strip()
        if not raw:
            return JSONResponse(
                {"ok": False, "error": "root path is required"}, status_code=400
            )

        new_root = Path(raw).expanduser().resolve()
        if not new_root.exists() or not new_root.is_dir():
            return JSONResponse(
                {"ok": False, "error": "directory not found"}, status_code=400
            )

        root_state.set(new_root)
        return JSONResponse({"ok": True, "root": str(new_root)})

    @app.get("/api/debug/context")
    def api_debug_context(
        include_all_env: bool = Query(default=False),
        env_limit: int = Query(default=200, ge=1, le=1000),
    ) -> JSONResponse:
        payload = build_debug_context(
            root=root_state.get(),
            include_all_env=include_all_env,
            env_limit=env_limit,
            recent_access=access_log.list(limit=80),
        )
        return JSONResponse(payload)

    @app.get("/api/debug/process-tree")
    def api_debug_process_tree() -> JSONResponse:
        return JSONResponse({"ok": True, "process_tree": get_process_tree()})

    @app.get("/api/debug/modules")
    def api_debug_modules(
        limit: int = Query(default=400, ge=1, le=2000), keyword: str = Query(default="")
    ) -> JSONResponse:
        return JSONResponse(
            {"ok": True, "data": get_loaded_modules(limit=limit, keyword=keyword)}
        )

    @app.get("/api/debug/file-probe")
    def api_debug_file_probe(
        path: str = Query(default=""),
        head: int = Query(default=128, ge=0, le=4096),
        tail: int = Query(default=128, ge=0, le=4096),
        hash_mode: str = Query(default="sample"),
    ) -> JSONResponse:
        root_dir = root_state.get()
        target = safe_target(root_dir, path)
        if not target.exists() or not target.is_file():
            return JSONResponse(
                {"ok": False, "error": "file not found"}, status_code=404
            )
        if hash_mode not in ("sample", "full"):
            return JSONResponse(
                {"ok": False, "error": "invalid hash_mode"}, status_code=400
            )
        data = file_probe(target, head=head, tail=tail, hash_mode=hash_mode)
        return JSONResponse(
            {
                "ok": True,
                "root": str(root_dir),
                "path": clean_relpath(str(target.relative_to(root_dir))),
                "abs_path": str(target),
                "probe": data,
            }
        )

    @app.get("/api/debug/report")
    def api_debug_report(
        include_all_env: bool = Query(default=False),
        env_limit: int = Query(default=200, ge=1, le=1000),
        modules_limit: int = Query(default=400, ge=1, le=2000),
        modules_keyword: str = Query(default=""),
        probe_path: str = Query(default=""),
        probe_head: int = Query(default=128, ge=0, le=4096),
        probe_tail: int = Query(default=128, ge=0, le=4096),
        probe_hash_mode: str = Query(default="sample"),
    ) -> JSONResponse:
        if probe_hash_mode not in ("sample", "full"):
            return JSONResponse(
                {"ok": False, "error": "invalid probe_hash_mode"}, status_code=400
            )

        root_dir = root_state.get()
        context = build_debug_context(
            root=root_dir,
            include_all_env=include_all_env,
            env_limit=env_limit,
            recent_access=access_log.list(limit=80),
        )
        modules = get_loaded_modules(limit=modules_limit, keyword=modules_keyword)

        payload = {
            "ok": True,
            "context": context,
            "process_tree": get_process_tree(),
            "modules": modules,
            "file_probe": None,
        }

        if probe_path.strip():
            try:
                target = safe_target(root_dir, probe_path)
                if not target.exists() or not target.is_file():
                    payload["file_probe"] = {
                        "ok": False,
                        "error": "file not found",
                        "path": probe_path,
                    }
                else:
                    probe = file_probe(
                        target,
                        head=probe_head,
                        tail=probe_tail,
                        hash_mode=probe_hash_mode,
                    )
                    payload["file_probe"] = {
                        "ok": True,
                        "root": str(root_dir),
                        "path": clean_relpath(str(target.relative_to(root_dir))),
                        "abs_path": str(target),
                        "probe": probe,
                    }
            except HTTPException as exc:
                payload["file_probe"] = {
                    "ok": False,
                    "error": exc.detail,
                    "path": probe_path,
                }

        return JSONResponse(payload)

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str) -> FileResponse:
        # Support Vue Router history mode refresh (e.g. /browser, /tasks).
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")

        candidate = WEBUI_VUE_DIST_DIR / full_path
        if candidate.is_file():
            return FileResponse(candidate)

        return FileResponse(index_file)

    return app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Keil web file explorer")
    parser.add_argument(
        "root",
        nargs="?",
        default=None,
        help="Initial root path (default: current directory)",
    )
    parser.add_argument(
        "--host", default="127.0.0.1", help="Bind host, use 0.0.0.0 for LAN access"
    )
    parser.add_argument("--port", type=int, default=8765, help="Bind port")
    parser.add_argument(
        "--public", action="store_true", help="Shortcut for --host 0.0.0.0"
    )
    parser.add_argument(
        "--open", action="store_true", help="Open browser automatically"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    root = Path(args.root) if args.root else Path.cwd()
    root = root.resolve()
    if not root.exists() or not root.is_dir():
        print(f"[ERROR] Invalid root directory: {root}")
        return 2

    host = "0.0.0.0" if args.public else args.host
    local_url = f"http://127.0.0.1:{args.port}/"

    print(f"[INFO] Root directory: {root}")
    print(f"[INFO] Serving on: {host}:{args.port}")
    print(f"[INFO] Local UI: {local_url}")

    if host == "0.0.0.0":
        lan = guess_lan_ip()
        if lan:
            print(f"[INFO] LAN UI: http://{lan}:{args.port}/")

    if args.open:
        webbrowser.open(local_url)

    app = create_app(root)
    uvicorn.run(app, host=host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
