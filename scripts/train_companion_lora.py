"""Local LoRA for the companion mouth. Default is dry-run.

Does not read .env. Does not change AI_PROVIDER. Does not feed alpaca/chatml/sharegpt.
Does not start a job unless you pass --run after reviewing the export.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.companion_corpus.sft_export import STEP2, collect_sft_records, write_sft

ADAPTER_DIR = ROOT / "private" / "companion-lora" / "adapter"
DEFAULT_MODEL = "mlx-community/Qwen2.5-7B-Instruct-4bit"
FORBIDDEN_DATA = ("alpaca_train.jsonl", "alpaca_val.jsonl", "chatml_train.jsonl", "sharegpt_train.jsonl")


def _hardware() -> dict[str, str | bool]:
    machine = subprocess.check_output(["uname", "-m"], text=True).strip()
    brand = ""
    try:
        brand = subprocess.check_output(
            ["sysctl", "-n", "machdep.cpu.brand_string"], text=True
        ).strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    return {
        "machine": machine,
        "cpu": brand,
        "apple_silicon": machine == "arm64",
        "mlx_lm": shutil.which("mlx_lm") is not None or _module_exists("mlx_lm"),
    }


def _module_exists(name: str) -> bool:
    try:
        __import__(name)
    except ImportError:
        return False
    return True


def _assert_clean_sft(sft_dir: Path) -> None:
    for path in sft_dir.glob("*.jsonl"):
        if path.name in FORBIDDEN_DATA:
            raise SystemExit(f"refusing {path.name}: owner textbook pack is not companion SFT")
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            assistant = next(message["content"] for message in row["messages"] if message["role"] == "assistant")
            if "i understand how you feel" in assistant.casefold():
                raise SystemExit("refusing SFT that teaches Feel-Felt-Found as the assistant target")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run",
        action="store_true",
        help="Start mlx_lm LoRA. Default is dry-run (export + hardware check only).",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--iters", type=int, default=200)
    parser.add_argument(
        "--adapter-path",
        default=str(ADAPTER_DIR),
        help="Where to write adapters. Keep 3B and 7B in different folders.",
    )
    parser.add_argument(
        "--resume-adapter-file",
        default=None,
        help="Resume mlx LoRA from an existing adapters.safetensors.",
    )
    args = parser.parse_args()

    summary = write_sft(collect_sft_records())
    sft_dir = Path(summary["dest"])
    _assert_clean_sft(sft_dir)
    hardware = _hardware()
    report = {
        "training_job_started": False,
        "ai_provider_changed": False,
        "cards_approved": False,
        "export": summary,
        "hardware": hardware,
        "adapter_dir": str(Path(args.adapter_path).resolve()),
        "model": args.model,
    }
    if not args.run:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        print("Dry-run only. Pass --run on Apple Silicon after `pip install mlx-lm`.")
        return 0
    if not hardware["apple_silicon"]:
        raise SystemExit("local LoRA recipe is mlx on Apple Silicon; this machine is not arm64")
    if not hardware["mlx_lm"]:
        raise SystemExit(
            "mlx_lm is not installed. On this Mac: python3 -m pip install mlx-lm "
            "(do not put API keys in the command)."
        )
    adapter_path = Path(args.adapter_path)
    adapter_path.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "mlx_lm",
        "lora",
        "--model",
        args.model,
        "--data",
        str(sft_dir),
        "--train",
        "--mask-prompt",
        "--grad-checkpoint",
        "--batch-size",
        "1",
        "--val-batches",
        "1",
        "--max-seq-length",
        "1024",
        "--iters",
        str(args.iters),
        "--save-every",
        "50",
        "--adapter-path",
        str(adapter_path),
        "--clear-cache-threshold",
        "2GB",
    ]
    if args.resume_adapter_file:
        cmd.extend(["--resume-adapter-file", args.resume_adapter_file])
    print("Starting local LoRA (this downloads the base model if missing):")
    print(" ".join(cmd))
    completed = subprocess.run(cmd, cwd=ROOT)
    report["training_job_started"] = completed.returncode == 0
    print(json.dumps({**report, "lora_exit": completed.returncode}, indent=2))
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
