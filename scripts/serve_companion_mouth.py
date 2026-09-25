"""Local OpenAI-compatible companion mouth. Default is dry-run.

Does not read .env. Does not change AI_PROVIDER. Does not approve cards.
Does not load 7B unless you pass --run (that freeze is the weight load).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.companion_corpus.mouth_endpoint import serve

DEFAULT_MODEL = ROOT / "private" / "companion-lora" / "base-qwen2.5-7b"
DEFAULT_ADAPTER = ROOT / "private" / "companion-lora" / "adapter-qwen2.5-7b-v3"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run",
        action="store_true",
        help="Load mlx 7B + adapter and bind. Default prints the bind plan only.",
    )
    parser.add_argument("--model", default=str(DEFAULT_MODEL))
    parser.add_argument("--adapter-path", default=str(DEFAULT_ADAPTER))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8741)
    parser.add_argument("--max-tokens", type=int, default=512)
    args = parser.parse_args()
    report = {
        "training_job_started": False,
        "ai_provider_changed": False,
        "cards_approved": False,
        "endpoint": f"http://{args.host}:{args.port}/v1/chat/completions",
        "model": args.model,
        "adapter_path": args.adapter_path,
        "mouth_guard": True,
        "sales_policy_engine_chooses_move": True,
        "mode": "live" if args.run else "dry_run",
    }
    if not args.run:
        print(json.dumps(report, indent=2), flush=True)
        print("Dry-run only. Pass --run to load 7B and serve. That freezes this Mac.", flush=True)
        return 0

    from mlx_lm import generate, load

    model, tokenizer = load(args.model, adapter_path=args.adapter_path)

    def _generate(messages: list[dict[str, str]], max_tokens: int) -> str:
        prompt = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        return generate(
            model,
            tokenizer,
            prompt=prompt,
            max_tokens=max_tokens or args.max_tokens,
            verbose=False,
        )

    server = serve(
        host=args.host,
        port=args.port,
        generate=_generate,
        model_name=args.model,
    )
    print(json.dumps({**report, "serving": True}, indent=2), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
