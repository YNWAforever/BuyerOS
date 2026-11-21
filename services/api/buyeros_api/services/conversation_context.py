"""Bounded readable conversation history for saved-turn model context.

The model may see only a small, deterministic window of the *same* saved
discussion: at most twelve user/assistant messages and at most eight KiB of
UTF-8 text. The window is constructed server-side from persisted messages; no
client-supplied transcript can enter the prompt. Older history is simply
omitted. The current question is always passed separately by the caller.
"""
from __future__ import annotations

from sqlalchemy import select

from ..db.conversation_threads import ConversationThreadMessage

MAX_HISTORY_MESSAGES = 12
MAX_HISTORY_BYTES = 8 * 1024
# Assistant citation-bearing rows are omitted by filtering; scan up to the same
# stored discussion ceiling so twelve readable user messages still win even when
# paired assistant rows are dropped.
MAX_HISTORY_SCAN = 100
HISTORY_ROLES = ('user', 'assistant')


def bounded_history(items, *, max_messages=MAX_HISTORY_MESSAGES,
                    max_bytes=MAX_HISTORY_BYTES) -> list[dict]:
    """Bound newest-first ``(role, text)`` messages to a contiguous newest suffix.

    Items that would cross either cap are omitted by stopping at that point: the
    window is always the newest contiguous readable suffix, never an older
    message selected from behind an oversized newer one. A model may not receive a
    half sentence attributed to a prior participant.
    """
    selected = []
    used = 0
    for item in items:
        if len(selected) >= max_messages:
            break
        if not isinstance(item, (tuple, list)) or len(item) != 2:
            raise ValueError('readable history item must be a role/text pair')
        role, text = item
        if role not in HISTORY_ROLES:
            raise ValueError('readable history role is not user or assistant')
        if not isinstance(text, str) or not text.strip():
            continue
        size = len(text.encode('utf-8'))
        if size > max_bytes - used:
            break
        selected.append({'role': role, 'text': text})
        used += size
    selected.reverse()
    return selected


def _assistant_body_is_safe(parts) -> bool:
    """Whether a prior assistant body may be replayed into a new model prompt.

    Persisted assistant messages carry citation IDs and labels, not the reviewed
    source content or its revision. A source ID can stay constant while policy,
    excerpt or content changes, so the saved citation is not authority to replay
    the assistant prose. Omit every assistant body with a citations part. A body
    without citations is notice/advisory text, never model output; user messages
    are always included and remain the recall anchor.
    """
    for part in parts or ():
        if not isinstance(part, dict):
            return False
        if part.get('kind') == 'citations':
            return False
    return True


def readable_items(rows, *, limit=MAX_HISTORY_MESSAGES):
    """Filter newest-first persisted rows, then bound the readable window."""
    items = []
    for role, text, parts in rows:
        if role == 'assistant' and not _assistant_body_is_safe(parts):
            continue
        items.append((role, text))
    return bounded_history(items, max_messages=max(1, min(int(limit), MAX_HISTORY_MESSAGES)))


async def readable_history(session, workspace_id, project_id, thread_id, *,
                           limit=MAX_HISTORY_MESSAGES):
    """Read the newest same-thread user/assistant messages, bounded and chronological.

    Deleting or editing a message is not possible in this contract, so persisted
    text is the readable transcript. No other thread, project or turn can leak
    into this window. Assistant bodies are included only when they carry no saved
    source citations; user messages always remain available for recall. The scan
    is bounded by the stored thread ceiling, not by the final 12-message window,
    so filtered assistant rows cannot hide older user facts.
    """
    rows = (await session.execute(select(
        ConversationThreadMessage.role, ConversationThreadMessage.text,
        ConversationThreadMessage.parts).where(
        ConversationThreadMessage.workspace_id == workspace_id,
        ConversationThreadMessage.project_id == project_id,
        ConversationThreadMessage.thread_id == thread_id,
        ConversationThreadMessage.role.in_(HISTORY_ROLES)).order_by(
        ConversationThreadMessage.seq.desc()).limit(MAX_HISTORY_SCAN))).all()
    return readable_items(rows, limit=limit)
