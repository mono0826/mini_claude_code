"""Memory system — 4-type file-based memory with MEMORY.md index.
Mirrors Claude Code's memory architecture: semantic recall via sideQuery."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .frontmatter import parse_frontmatter, format_frontmatter

# A callable that sends a prompt and returns model text response.
# Signature: async (system: str, user_message: str) -> str
from typing import Callable
SideQueryFn = Callable[[str, str], Any]  # actually Awaitable[str]

# ─── Types ──────────────────────────────────────────────────

VALID_TYPES = {"user", "feedback", "project", "reference"}
MAX_INDEX_LINES = 200
MAX_INDEX_BYTES = 25000


class MemoryEntry:
    __slots__ = ("name", "description", "type", "filename", "content")

    def __init__(self, name: str, description: str, type: str, filename: str, content: str):
        self.name = name
        self.description = description
        self.type = type
        self.filename = filename
        self.content = content


# ─── Paths ──────────────────────────────────────────────────


def _project_hash() -> str:
    return hashlib.sha256(str(Path.cwd()).encode()).hexdigest()[:16]


def get_memory_dir() -> Path:
    d = Path.home() / ".mini-claude" / "projects" / _project_hash() / "memory"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _get_index_path() -> Path:
    return get_memory_dir() / "MEMORY.md"


# ─── Slugify ────────────────────────────────────────────────


def _slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", text.lower())
    s = s.strip("_")
    return s[:40]


# ─── CRUD ───────────────────────────────────────────────────


def list_memories() -> list[MemoryEntry]:
    d = get_memory_dir()
    entries: list[MemoryEntry] = []
    for f in sorted(d.glob("*.md")):
        if f.name == "MEMORY.md":
            continue
        try:
            result = parse_frontmatter(f.read_text())
            meta = result.meta
            if not meta.get("name") or not meta.get("type"):
                continue
            t = meta["type"] if meta["type"] in VALID_TYPES else "project"
            entries.append(MemoryEntry(
                name=meta["name"],
                description=meta.get("description", ""),
                type=t,
                filename=f.name,
                content=result.body,
            ))
        except Exception:
            pass
    # Sort by mtime desc
    entries.sort(key=lambda e: (d / e.filename).stat().st_mtime, reverse=True)
    return entries


def save_memory(name: str, description: str, type: str, content: str) -> str:
    d = get_memory_dir()
    filename = f"{type}_{_slugify(name)}.md"
    text = format_frontmatter({"name": name, "description": description, "type": type}, content)
    (d / filename).write_text(text)
    _update_memory_index()
    return filename


def delete_memory(filename: str) -> bool:
    filepath = get_memory_dir() / filename
    if not filepath.exists():
        return False
    filepath.unlink()
    _update_memory_index()
    return True


# ─── Index ──────────────────────────────────────────────────


def _update_memory_index() -> None:
    memories = list_memories()
    lines = ["# Memory Index", ""]
    for m in memories:
        lines.append(f"- **[{m.name}]({m.filename})** ({m.type}) — {m.description}")
    _get_index_path().write_text("\n".join(lines))


def load_memory_index() -> str:
    index_path = _get_index_path()
    if not index_path.exists():
        return ""
    content = index_path.read_text()
    lines = content.split("\n")
    if len(lines) > MAX_INDEX_LINES:
        content = "\n".join(lines[:MAX_INDEX_LINES]) + "\n\n[... truncated, too many memory entries ...]"
    if len(content.encode()) > MAX_INDEX_BYTES:
        content = content[:MAX_INDEX_BYTES] + "\n\n[... truncated, index too large ...]"
    return content


# ─── Memory Header (lightweight scan) ──────────────────────

class MemoryHeader:
    __slots__ = ("filename", "file_path", "mtime_ms", "description", "type")

    def __init__(self, filename: str, file_path: str, mtime_ms: float,
                 description: str | None, type: str | None):
        self.filename = filename
        self.file_path = file_path
        self.mtime_ms = mtime_ms
        self.description = description
        self.type = type


MAX_MEMORY_FILES = 200
MAX_MEMORY_BYTES_PER_FILE = 4096
MAX_SESSION_MEMORY_BYTES = 60 * 1024  # 60KB cumulative per session


def scan_memory_headers() -> list[MemoryHeader]:
    """Scan memory directory — read only frontmatter (first 30 lines) for speed."""
    d = get_memory_dir()
    headers: list[MemoryHeader] = []
    for f in d.glob("*.md"):
        if f.name == "MEMORY.md":
            continue
        try:
            stat = f.stat()
            raw = f.read_text()
            first30 = "\n".join(raw.split("\n")[:30]) # 读取前30行
            result = parse_frontmatter(first30) # 解析前言，获得meta和body
            meta = result.meta
            t = meta.get("type") # 获取记忆类型
            headers.append(MemoryHeader(
                filename=f.name, # 文件名
                file_path=str(f), # 文件路径
                mtime_ms=stat.st_mtime * 1000, # 修改时间
                description=meta.get("description"), # 描述
                type=t if t in VALID_TYPES else None, # 记忆类型, 如果类型不在VALID_TYPES中, 则设置为None
            ))
        except Exception:
            pass
    headers.sort(key=lambda h: h.mtime_ms, reverse=True) # 按修改时间排序, 时间越近的越靠前
    return headers[:MAX_MEMORY_FILES] # 返回前MAX_MEMORY_FILES个记忆头


# 将记忆头文件名格式化成字符串, 用于记忆召回
# example: 目录下有user_xxx.md, project_xxx.md, reference_xxx.md, feedback_xxx.md, text_xxx.md
# 则返回:
# - [user] user_xxx.md (2026-05-12T00:00:00+00:00): 用户记忆
# - [project] project_xxx.md (2026-05-12T00:00:00+00:00): 项目记忆
# - [reference] reference_xxx.md (2026-05-12T00:00:00+00:00): 参考记忆
# - [feedback] feedback_xxx.md (2026-05-12T00:00:00+00:00): 反馈记忆
# - [] text_xxx.md (2026-05-12T00:00:00+00:00): 文本记忆 # 未定义类型, 则不显示类型标签

def format_memory_manifest(headers: list[MemoryHeader]) -> str:
    """Format manifest for semantic selector: one line per memory."""
    lines = []
    for h in headers:
        tag = f"[{h.type}] " if h.type and h.type in VALID_TYPES else "" # 记忆类型标签, 如果类型不在VALID_TYPES中, 则不显示类型标签
        ts = datetime.fromtimestamp(h.mtime_ms / 1000, tz=timezone.utc).isoformat()
        if h.description:
            lines.append(f"- {tag}{h.filename} ({ts}): {h.description}")
        else:
            lines.append(f"- {tag}{h.filename} ({ts})")
    return "\n".join(lines)


# ─── Memory Age / Freshness ────────────────────────────────

def memory_age(mtime_ms: float) -> str:
    # 计算记忆时间，单位为天
    days = max(0, int((time.time() * 1000 - mtime_ms) / 86_400_000))
    if days == 0:
        return "today"
    if days == 1:
        return "yesterday"
    return f"{days} days ago"

# 记忆新鲜度警告
# 如果记忆时间超过1天，则返回警告
def memory_freshness_warning(mtime_ms: float) -> str:
    days = max(0, int((time.time() * 1000 - mtime_ms) / 86_400_000))
    if days <= 1:
        return ""
    return (f"This memory is {days} days old. Memories are point-in-time observations, "
            "not live state — claims about code behavior may be outdated. "
            "Verify against current code before asserting as fact.")


# ─── Semantic Recall (sideQuery) ────────────────────────────

SELECT_MEMORIES_PROMPT = """You are selecting memories that will be useful to an AI coding assistant as it processes a user's query. You will be given the user's query and a list of available memory files with their filenames and descriptions.

Return a JSON object with a "selected_memories" array of filenames for the memories that will clearly be useful (up to 5). Only include memories that you are certain will be helpful based on their name and description.
- If you are unsure if a memory will be useful, do not include it.
- If no memories would clearly be useful, return an empty array."""


class RelevantMemory:
    __slots__ = ("path", "content", "mtime_ms", "header")

    def __init__(self, path: str, content: str, mtime_ms: float, header: str):
        self.path = path
        self.content = content
        self.mtime_ms = mtime_ms
        self.header = header

# 流程：
# 查询目录下的文件->格式化记忆清单-> (用户输入+记忆清单)->side_query()->获得相关记忆文件->读取相关文件内容(需要做截断)->拼接记忆头文本->返回相关记忆列表
async def select_relevant_memories(
    query: str, # 用户输入
    side_query: SideQueryFn, # 侧边查询
    already_surfaced: set[str],
) -> list[RelevantMemory]:  # 返回相关记忆列表
    """Call the model to semantically select relevant memories."""
    headers = scan_memory_headers() # 获得时间最近的MAX_MEMORY_FILES个记忆头
    if not headers:
        return [] # 如果没有记忆头，则返回空列表

    candidates = [h for h in headers if h.file_path not in already_surfaced] # 过滤掉已经召回的记忆
    if not candidates:
        return [] # 如果没有候选记忆，则返回空列表

    manifest = format_memory_manifest(candidates) # 返回为字符串的记忆清单，用于知识文件类型以及时间信息展示
    # example:
    # - [user] user_xxx.md (2026-05-12T00:00:00+00:00): 用户记忆
    # - [project] project_xxx.md (2026-05-12T00:00:00+00:00): 项目记忆
    # - [reference] reference_xxx.md (2026-05-12T00:00:00+00:00): 参考记忆
    # - [feedback] feedback_xxx.md (2026-05-12T00:00:00+00:00): 反馈记忆
    # - [] text_xxx.md (2026-05-12T00:00:00+00:00): 文本记忆 # 未定义类型, 则不显示类型标签

    try:
        text = await side_query( # 调用侧边查询
            SELECT_MEMORIES_PROMPT, # 系统提示词
            f"Query: {query}\n\nAvailable memories:\n{manifest}", # 用户输入, 将用户输入和记忆清单拼接成字符串
        )

        # Extract JSON from response
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            return []

        parsed = json.loads(match.group(0)) # 将JSON字符串转换为Python对象
        selected_filenames = set(parsed.get("selected_memories", [])) # 获取选中的记忆文件名集合

        selected = [h for h in candidates if h.filename in selected_filenames][:5] # 获取选中的记忆对象列表，最多5条

        result: list[RelevantMemory] = []
        for h in selected:
            content = Path(h.file_path).read_text() # 读取记忆内容
            if len(content.encode()) > MAX_MEMORY_BYTES_PER_FILE: # 如果记忆内容超过最大值，则截断
                content = content[:MAX_MEMORY_BYTES_PER_FILE] + "\n\n[... truncated, memory file too large ...]"
            freshness = memory_freshness_warning(h.mtime_ms) # 判断文件更改时间是否超过1天，超过则返回警告
            header_text = (
                f"{freshness}\n\nMemory: {h.file_path}:" if freshness
                else f"Memory (saved {memory_age(h.mtime_ms)}): {h.file_path}:"
            ) # 拼接记忆头文本，包括记忆时间、记忆路径、记忆新鲜度警告
            result.append(RelevantMemory(
                path=h.file_path, content=content,
                mtime_ms=h.mtime_ms, header=header_text,
            ))
        return result
    except Exception as e:
        if "cancel" in str(e).lower():
            return []
        print(f"[memory] semantic recall failed: {e}")
        return []


# ─── Prefetch Handle ────────────────────────────────────────

class MemoryPrefetch:
    def __init__(self, task: asyncio.Task):
        self.task = task
        self.consumed = False

    @property
    def settled(self) -> bool:
        return self.task.done()

# 预先提取相关记忆
def start_memory_prefetch(
    query: str, # 用户输入
    side_query: SideQueryFn,
    already_surfaced: set[str],
    session_memory_bytes: int,
) -> MemoryPrefetch | None:
    """Start async memory prefetch. Returns handle to poll for results."""
    # Gate: multi-word input only
    # 输入长度检查
    if not re.search(r"\s", query.strip()):
        return None

    # Gate: session budget
    # 会话内存预算检查
    # 如果会话内存超过最大值，则不进行记忆预取
    if session_memory_bytes >= MAX_SESSION_MEMORY_BYTES:
        return None

    # Gate: memories must exist
    d = get_memory_dir() # 获取记忆目录
    has_memories = any(f.suffix == ".md" and f.name != "MEMORY.md" for f in d.iterdir())
    if not has_memories:
        return None # 如果没有记忆，则不进行记忆预取

    task = asyncio.create_task(
        select_relevant_memories(query, side_query, already_surfaced) # 创建异步任务，调用模型用于记忆召回
    )
    return MemoryPrefetch(task) # 返回记忆预取对象


def format_memories_for_injection(memories: list[RelevantMemory]) -> str:
    """Format recalled memories for injection as user message content."""
    parts = []
    for m in memories:
        parts.append(f"<system-reminder>\n{m.header}\n\n{m.content}\n</system-reminder>")
    return "\n\n".join(parts)


# ─── System prompt section ──────────────────────────────────


def build_memory_prompt_section() -> str:
    index = load_memory_index()
    memory_dir = str(get_memory_dir())

    return f"""# Memory System

You have a persistent, file-based memory system at `{memory_dir}`.

## Memory Types
- **user**: User's role, preferences, knowledge level
- **feedback**: Corrections and guidance from the user (include Why + How to apply)
- **project**: Ongoing work, goals, deadlines, decisions
- **reference**: Pointers to external resources (URLs, tools, dashboards)

## How to Save Memories
Use the write_file tool to create a memory file with YAML frontmatter:

```markdown
---
name: memory name
description: one-line description
type: user|feedback|project|reference
---
Memory content here.
```

Save to: `{memory_dir}/`
Filename format: `{{type}}_{{slugified_name}}.md`

The MEMORY.md index is auto-updated when you write to the memory directory — do NOT update it manually.

## What NOT to Save
- Code patterns or architecture (read the code instead)
- Git history (use git log)
- Anything already in CLAUDE.md
- Ephemeral task details

## When to Recall
When the user asks you to remember or recall, or when prior context seems relevant.
{chr(10) + "## Current Memory Index" + chr(10) + index if index else chr(10) + "(No memories saved yet.)"}"""
