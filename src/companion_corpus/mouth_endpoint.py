"""OpenAI-compatible companion mouth. Weights stay off until --run.

Does not change AI_PROVIDER. SalesPolicyEngine still chooses SalesMove.
Every assistant JSON goes through mouth_guard before it leaves the process.
"""

from __future__ import annotations

import json
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Callable
from urllib.parse import urlparse

from src.companion_corpus.lora_eval import extract_json_object
from src.companion_corpus.mouth_guard import (
    DEFAULT_GIFT_PATTERNS,
    END_CONTACT_CLOSE,
    SAFE_NO_GIFT,
    guard_payload,
)

GenerateFn = Callable[[list[dict[str, str]], int], str]

ANALYZER_FALLBACK = {
    "observed_stage": "HUMAN_REVIEW",
    "confidence": 0.0,
    "customer_intent": "unparsed companion output",
    "signals": [],
    "objections": [],
    "commitment_level": "UNKNOWN",
    "recommended_moves": ["HANDOFF_TO_HUMAN"],
    "requested_callback_at": None,
    "requires_human": True,
}


def _last_user_text(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            return str(message.get("content") or "")
    return ""


def _system_text(messages: list[dict[str, Any]]) -> str:
    return "\n".join(
        str(message.get("content") or "")
        for message in messages
        if message.get("role") == "system"
    )


def row_from_messages(messages: list[dict[str, Any]]) -> dict[str, Any]:
    user = _last_user_text(messages).strip()
    system = _system_text(messages)
    row: dict[str, Any] = {"task": "analyzer", "customer_message": "", "forbidden_patterns": []}
    if user.startswith("{"):
        try:
            parsed = json.loads(user)
        except json.JSONDecodeError:
            parsed = {}
        if isinstance(parsed, dict) and parsed.get("task") in {"analyzer", "generator"}:
            row["task"] = parsed["task"]
            row["customer_message"] = str(parsed.get("customer_message") or "")
            if parsed.get("approved_move"):
                row["approved_move"] = parsed["approved_move"]
            if parsed.get("forbidden_patterns"):
                row["forbidden_patterns"] = list(parsed["forbidden_patterns"])
            return _with_default_gifts(row)
    if "SalesResponseOutput" in user or "approved_move" in system or "SalesResponseOutput" in system:
        row["task"] = "generator"
        facts = _json_after(user, r"ALLOWED_KNOWLEDGE_AND_FACTS[^\n]*\n")
        if isinstance(facts, dict) and facts.get("approved_move"):
            row["approved_move"] = facts["approved_move"]
        row["customer_message"] = _customer_content_json(user)
        return _with_default_gifts(row)
    row["customer_message"] = _customer_content_json(user) or user
    return row


def _with_default_gifts(row: dict[str, Any]) -> dict[str, Any]:
    if row.get("task") == "generator":
        patterns = list(row.get("forbidden_patterns") or [])
        for pattern in DEFAULT_GIFT_PATTERNS:
            if pattern not in patterns:
                patterns.append(pattern)
        row["forbidden_patterns"] = patterns
    return row


def _customer_content_json(user: str) -> str:
    match = re.search(
        r"CUSTOMER_CONTENT_JSON[^\n]*\n(.*?)(?:\nEXPECTED_STRUCTURED_OUTPUT|\Z)",
        user,
        flags=re.DOTALL,
    )
    if not match:
        return ""
    blob = match.group(1).strip()
    try:
        value = json.loads(blob)
    except json.JSONDecodeError:
        return blob
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def _json_after(text: str, header: str) -> Any:
    match = re.search(header + r"(\{.*)", text, flags=re.DOTALL)
    if not match:
        return None
    blob = match.group(1).strip()
    decoder = json.JSONDecoder()
    try:
        value, _ = decoder.raw_decode(blob)
    except json.JSONDecodeError:
        return None
    return value


def fallback_payload(row: dict[str, Any]) -> dict[str, Any]:
    if row.get("task") == "analyzer":
        return dict(ANALYZER_FALLBACK)
    approved = str(row.get("approved_move") or "END_CONTACT")
    text = END_CONTACT_CLOSE if approved == "END_CONTACT" else SAFE_NO_GIFT
    return {
        "move": approved,
        "message_text": text,
        "knowledge_ids": [],
        "business_fact_ids": [],
        "customer_evidence_ids": [],
        "used_safe_fallback": True,
    }


def guard_assistant_text(messages: list[dict[str, Any]], raw: str) -> str:
    row = row_from_messages(messages)
    try:
        payload = extract_json_object(raw)
    except (ValueError, json.JSONDecodeError):
        payload = fallback_payload(row)
    guarded = guard_payload(row, payload)
    return json.dumps(guarded, ensure_ascii=False)


def chat_completion(
    *,
    messages: list[dict[str, Any]],
    generate: GenerateFn,
    model: str,
    max_tokens: int = 512,
) -> dict[str, Any]:
    normalized = [
        {"role": str(item.get("role") or "user"), "content": str(item.get("content") or "")}
        for item in messages
    ]
    raw = generate(normalized, max_tokens)
    content = guard_assistant_text(normalized, raw)
    return {
        "id": "chatcmpl-companion-mouth",
        "object": "chat.completion",
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "mouth_guard": True,
        "ai_provider_unchanged": True,
    }


class MouthHandler(BaseHTTPRequestHandler):
    generate: GenerateFn
    model_name: str

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if urlparse(self.path).path in {"/v1/models", "/models"}:
            self._json(
                200,
                {
                    "object": "list",
                    "data": [{"id": self.model_name, "object": "model", "owned_by": "evorove-local"}],
                },
            )
            return
        self._json(404, {"error": {"message": "not found"}})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length") or "0")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._json(400, {"error": {"message": "invalid json"}})
            return
        if path not in {"/v1/chat/completions", "/chat/completions"}:
            self._json(404, {"error": {"message": "not found"}})
            return
        messages = body.get("messages") or []
        if not isinstance(messages, list) or not messages:
            self._json(400, {"error": {"message": "messages required"}})
            return
        max_tokens = int(body.get("max_tokens") or 512)
        try:
            payload = chat_completion(
                messages=messages,
                generate=self.generate,
                model=str(body.get("model") or self.model_name),
                max_tokens=max_tokens,
            )
        except Exception as exc:
            self._json(500, {"error": {"message": str(exc), "type": type(exc).__name__}})
            return
        self._json(200, payload)


def serve(*, host: str, port: int, generate: GenerateFn, model_name: str) -> HTTPServer:
    handler = type(
        "BoundMouthHandler",
        (MouthHandler,),
        {"generate": staticmethod(generate), "model_name": model_name},
    )
    # MLX generate must run on the thread that loaded the model.
    return HTTPServer((host, port), handler)
