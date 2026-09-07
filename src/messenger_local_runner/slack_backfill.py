from __future__ import annotations

import datetime as dt
import hashlib
import json
import pathlib
import urllib.parse
import urllib.request
from typing import Any


SLACK_API = "https://slack.com/api"
DEFAULT_TYPES = "public_channel,im,mpim"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def runtime_dir_for(data_dir: pathlib.Path) -> pathlib.Path:
    return data_dir / "runtime"


def load_json(path: pathlib.Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def write_json(path: pathlib.Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_slack_token_record(runtime_dir: pathlib.Path) -> dict[str, Any]:
    token_path = runtime_dir / "oauth" / "slack-user-token.json"
    if not token_path.exists():
        raise RuntimeError("missing_slack_user_token")
    return load_json(token_path)


def load_slack_access_token(runtime_dir: pathlib.Path) -> str:
    record = load_slack_token_record(runtime_dir)
    token = record.get("access_token")
    if not isinstance(token, str) or not token:
        raise RuntimeError("missing_slack_user_token")
    return token


def load_team_id(runtime_dir: pathlib.Path) -> str | None:
    record = load_slack_token_record(runtime_dir)
    team = record.get("team")
    if isinstance(team, dict):
        team_id = team.get("id")
        return team_id if isinstance(team_id, str) and team_id else None
    return None


def slack_get(token: str, method: str, params: dict[str, str]) -> dict[str, Any]:
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(
        f"{SLACK_API}/{method}?{query}",
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        value = json.loads(response.read().decode("utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("slack_non_object_response")
    return value


def channel_type_for(channel: dict[str, Any]) -> str:
    if channel.get("is_im"):
        return "im"
    if channel.get("is_mpim"):
        return "mpim"
    if channel.get("is_group") or channel.get("is_private"):
        return "group"
    return "channel"


def event_type_for_channel(channel: dict[str, Any]) -> str:
    return f"message.{channel_type_for(channel)}"


def list_channels(token: str, channel_limit: int, types: str) -> list[dict[str, Any]]:
    channels: list[dict[str, Any]] = []
    cursor = ""
    while len(channels) < channel_limit:
        params = {
            "exclude_archived": "true",
            "limit": str(min(200, max(1, channel_limit - len(channels)))),
            "types": types,
        }
        if cursor:
            params["cursor"] = cursor
        payload = slack_get(token, "conversations.list", params)
        if not payload.get("ok"):
            raise RuntimeError(str(payload.get("error") or "slack_conversations_list_failed"))
        items = payload.get("channels")
        if isinstance(items, list):
            channels.extend(item for item in items if isinstance(item, dict))
        metadata = payload.get("response_metadata")
        cursor = str(metadata.get("next_cursor") or "") if isinstance(metadata, dict) else ""
        if not cursor:
            break
    return channels[:channel_limit]


def history_for_channel(token: str, channel_id: str, per_channel: int) -> list[dict[str, Any]]:
    payload = slack_get(
        token,
        "conversations.history",
        {"channel": channel_id, "limit": str(max(1, per_channel))},
    )
    if not payload.get("ok"):
        error = str(payload.get("error") or "slack_conversations_history_failed")
        if error in {"not_in_channel", "missing_scope", "channel_not_found", "is_archived"}:
            return []
        raise RuntimeError(error)
    messages = payload.get("messages")
    return [item for item in messages if isinstance(item, dict)] if isinstance(messages, list) else []


def payload_for_message(message: dict[str, Any], channel: dict[str, Any], team_id: str | None) -> dict[str, Any]:
    channel_id = str(channel.get("id") or "")
    channel_type = channel_type_for(channel)
    event = dict(message)
    event["type"] = "message"
    event["channel"] = channel_id
    event["channel_type"] = channel_type
    if "event_ts" not in event and isinstance(event.get("ts"), str):
        event["event_ts"] = event["ts"]
    return {
        "type": "event_callback",
        "team_id": team_id,
        "event_id": f"backfill-{channel_id}-{event.get('ts')}",
        "event_time": int(dt.datetime.now(dt.timezone.utc).timestamp()),
        "event": event,
    }


def idempotency_key(provider: str, payload: dict[str, Any], event_type: str) -> str:
    parts: list[str] = [provider, event_type]
    event = payload.get("event")
    if isinstance(event, dict):
        parts.extend(
            [
                str(payload.get("event_id") or ""),
                str(event.get("channel") or ""),
                str(event.get("ts") or event.get("event_ts") or ""),
                str(event.get("thread_ts") or ""),
                str(event.get("user") or ""),
            ]
        )
    joined = "\0".join(parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def already_queued(runtime_dir: pathlib.Path, key: str) -> bool:
    queue_dir = runtime_dir / "queue"
    if not queue_dir.exists():
        return False
    for queue_path in queue_dir.glob("*.json"):
        try:
            record = load_json(queue_path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if record.get("idempotency_key") == key:
            return True
    return False


def save_event(runtime_dir: pathlib.Path, event_type: str, payload: dict[str, Any], key: str) -> pathlib.Path:
    received_at = utc_now()
    prefix = received_at.replace(":", "").replace("-", "").replace(".", "")
    event_id = f"{prefix}-slack-{event_type}-{key[:12]}".replace("/", "_")
    raw_path = runtime_dir / "raw-events" / f"{event_id}.json"
    queue_path = runtime_dir / "queue" / f"{event_id}.json"
    raw_record = {
        "schema_version": 1,
        "idempotency_key": key,
        "provider": "slack",
        "event_type": event_type,
        "received_at": received_at,
        "headers": {"x-reply-drafter-source": "slack_backfill"},
        "body": json.dumps(payload, ensure_ascii=False),
        "payload": payload,
    }
    queue_record = {
        "schema_version": 1,
        "job_type": "triage_inbox",
        "provider": "slack",
        "event_type": event_type,
        "idempotency_key": key,
        "raw_event_path": str(raw_path),
        "status": "queued",
        "created_at": received_at,
    }
    write_json(raw_path, raw_record)
    write_json(queue_path, queue_record)
    return queue_path


def backfill_once(data_dir: pathlib.Path, channel_limit: int, per_channel: int, types: str) -> dict[str, Any]:
    runtime_dir = runtime_dir_for(data_dir)
    token = load_slack_access_token(runtime_dir)
    team_id = load_team_id(runtime_dir)
    channels = list_channels(token, channel_limit=channel_limit, types=types)
    queued: list[str] = []
    skipped = 0
    scanned = 0
    errors: list[dict[str, str]] = []

    for channel in channels:
        channel_id = channel.get("id")
        if not isinstance(channel_id, str) or not channel_id:
            continue
        try:
            messages = history_for_channel(token, channel_id, per_channel=per_channel)
        except RuntimeError as exc:
            errors.append({"channel_id": channel_id, "error": str(exc)})
            continue
        event_type = event_type_for_channel(channel)
        for message in messages:
            scanned += 1
            payload = payload_for_message(message, channel, team_id)
            key = idempotency_key("slack", payload, event_type)
            if already_queued(runtime_dir, key):
                skipped += 1
                continue
            queued.append(str(save_event(runtime_dir, event_type, payload, key)))

    return {
        "ok": True,
        "provider": "slack",
        "scanned_channels": len(channels),
        "scanned_messages": scanned,
        "queued_count": len(queued),
        "skipped_existing": skipped,
        "errors": errors,
        "queued": queued,
    }
