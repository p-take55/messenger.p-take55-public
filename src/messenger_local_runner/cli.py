from __future__ import annotations

import argparse
import json
import os
import pathlib
import platform
import sqlite3
import sys
from datetime import datetime, timezone
from typing import Any

from . import slack_backfill

PROVIDERS = ("slack", "gmail", "chatwork")
SCHEMA_VERSION = 1


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def default_data_dir() -> pathlib.Path:
    override = os.environ.get("MESSENGER_RUNNER_DATA_DIR")
    if override:
        return pathlib.Path(override).expanduser()

    home = pathlib.Path.home()
    system = platform.system().lower()
    if system == "darwin":
        return home / "Library" / "Application Support" / "aachat" / "reply-drafter"
    if system == "windows":
        base = os.environ.get("APPDATA")
        if base:
            return pathlib.Path(base) / "aachat" / "reply-drafter"
    return home / ".local" / "share" / "aachat" / "reply-drafter"


def sqlite_path(data_dir: pathlib.Path) -> pathlib.Path:
    return data_dir / "reply-drafter.sqlite"


def connect(path: pathlib.Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists meta (
          key text primary key,
          value text not null
        );

        create table if not exists reply_requests (
          id text primary key,
          project text not null,
          provider text not null,
          state text not null,
          provider_locator_json text not null,
          idempotency_key text not null unique,
          ask_doc_path text,
          draft_session_id text,
          triage_json text,
          context_summary_json text,
          created_at text not null,
          updated_at text not null
        );

        create table if not exists reply_options (
          id text primary key,
          request_id text not null,
          label text not null,
          body text not null,
          rationale text,
          risk_json text,
          created_at text not null
        );

        create table if not exists reply_decisions (
          id text primary key,
          request_id text not null,
          decision text not null,
          option_id text,
          edited_body text,
          decided_by text,
          decided_from text not null,
          decided_at text not null
        );

        create table if not exists send_attempts (
          id text primary key,
          request_id text not null,
          decision_id text not null,
          provider text not null,
          status text not null,
          provider_result_json text,
          error text,
          attempted_at text not null
        );

        create table if not exists provider_cursors (
          provider text primary key,
          cursor_json text not null,
          updated_at text not null
        );

        create table if not exists connector_health (
          provider text primary key,
          state text not null,
          detail_json text,
          checked_at text not null
        );
        """
    )
    conn.execute(
        "insert or replace into meta(key, value) values (?, ?)",
        ("schema_version", str(SCHEMA_VERSION)),
    )
    now = utc_now()
    for provider in PROVIDERS:
        conn.execute(
            """
            insert or ignore into connector_health(provider, state, detail_json, checked_at)
            values (?, ?, ?, ?)
            """,
            (provider, "disabled", "{}", now),
        )
    conn.commit()


def count_by_state(conn: sqlite3.Connection) -> dict[str, int]:
    states = {
        "received": 0,
        "draft_session_requested": 0,
        "draft_session_running": 0,
        "waiting_for_human": 0,
        "approved": 0,
        "send_queued": 0,
        "send_error": 0,
    }
    for row in conn.execute("select state, count(*) as count from reply_requests group by state"):
        states[str(row["state"])] = int(row["count"])
    return states


def connector_states(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    values: dict[str, dict[str, Any]] = {}
    for provider in PROVIDERS:
        values[provider] = {"state": "unknown"}
    for row in conn.execute("select provider, state, checked_at from connector_health"):
        values[str(row["provider"])] = {
            "state": str(row["state"]),
            "checked_at": str(row["checked_at"]),
        }
    return values


def status_payload(data_dir: pathlib.Path) -> dict[str, Any]:
    path = sqlite_path(data_dir)
    payload: dict[str, Any] = {
        "ok": True,
        "runner": {"running": False, "mode": "cli"},
        "sqlite": {"path": str(path), "ok": path.exists()},
        "connectors": {provider: {"state": "unknown"} for provider in PROVIDERS},
        "queues": {},
        "next_actions": [],
    }

    if not path.exists():
        payload["next_actions"].append(
            {
                "reason": "Local SQLite has not been initialized.",
                "command": "reply-drafter init",
            }
        )
        return payload

    try:
        with connect(path) as conn:
            payload["queues"] = count_by_state(conn)
            payload["connectors"] = connector_states(conn)
    except sqlite3.Error as exc:
        payload["ok"] = False
        payload["sqlite"]["ok"] = False
        payload["sqlite"]["error"] = f"{type(exc).__name__}: {exc}"
    return payload


def print_result(payload: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return

    if payload.get("ok"):
        print("ok")
    else:
        print("error")
    for action in payload.get("next_actions") or []:
        if isinstance(action, dict) and action.get("command"):
            print(f"next: {action['command']}")


def cmd_init(args: argparse.Namespace) -> int:
    data_dir = args.data_dir
    data_dir.mkdir(parents=True, exist_ok=True)
    path = sqlite_path(data_dir)
    with connect(path) as conn:
        migrate(conn)
    print_result(
        {
            "ok": True,
            "action": "initialized",
            "data_dir": str(data_dir),
            "sqlite": {"path": str(path), "ok": True},
            "schema_version": SCHEMA_VERSION,
        },
        as_json=args.json,
    )
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    payload = status_payload(args.data_dir)
    print_result(payload, as_json=args.json)
    return 0 if payload.get("ok") else 1


def cmd_doctor(args: argparse.Namespace) -> int:
    payload = status_payload(args.data_dir)
    payload["checks"] = [
        {
            "name": "sqlite_initialized",
            "ok": bool(payload.get("sqlite", {}).get("ok")),
        },
        {
            "name": "secrets_not_in_sqlite",
            "ok": True,
            "note": "This CLI never stores credential values in SQLite.",
        },
    ]
    print_result(payload, as_json=args.json)
    return 0 if payload.get("ok") else 1


def cmd_noop(args: argparse.Namespace) -> int:
    payload = {
        "ok": True,
        "action": args.command,
        "status": "not_implemented",
        "message": "Provider adapters and background services are not implemented in this CLI stub yet.",
        "data_dir": str(args.data_dir),
    }
    print_result(payload, as_json=args.json)
    return 0


def cmd_catch_up(args: argparse.Namespace) -> int:
    if args.provider != "slack":
        payload = {
            "ok": False,
            "action": "catch-up",
            "provider": args.provider,
            "error": "provider_not_implemented",
            "message": "Only Slack catch-up is implemented.",
        }
        print_result(payload, as_json=args.json)
        return 1

    try:
        result = slack_backfill.backfill_once(
            args.data_dir,
            channel_limit=args.channel_limit,
            per_channel=args.per_channel,
            types=args.types,
        )
    except (RuntimeError, OSError, TimeoutError, json.JSONDecodeError) as exc:
        result = {
            "ok": False,
            "action": "catch-up",
            "provider": "slack",
            "error": str(exc),
        }
        print_result(result, as_json=args.json)
        return 1

    print_result({"ok": True, "action": "catch-up", "provider": "slack", "result": result}, as_json=args.json)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="reply-drafter")
    parser.add_argument("--data-dir", type=pathlib.Path, default=default_data_dir())
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name, handler in [
        ("init", cmd_init),
        ("status", cmd_status),
        ("doctor", cmd_doctor),
        ("start", cmd_noop),
        ("stop", cmd_noop),
        ("process", cmd_noop),
        ("send-approved", cmd_noop),
    ]:
        sub = subparsers.add_parser(name)
        sub.add_argument("--json", action="store_true")
        sub.set_defaults(func=handler)
    catch_up = subparsers.add_parser("catch-up")
    catch_up.add_argument("--json", action="store_true")
    catch_up.add_argument("--provider", choices=PROVIDERS, required=True)
    catch_up.add_argument("--channel-limit", type=int, default=5)
    catch_up.add_argument("--per-channel", type=int, default=20)
    catch_up.add_argument("--types", default=slack_backfill.DEFAULT_TYPES)
    catch_up.set_defaults(func=cmd_catch_up)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.data_dir = args.data_dir.expanduser()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
