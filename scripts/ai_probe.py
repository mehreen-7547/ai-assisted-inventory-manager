"""Test BOTH free pretrained Chronos models on CPU in separate processes.

Usage (Python 3.12 or 3.13):
    python scripts/ai_probe.py
    python scripts/ai_probe.py --model bolt

The first run downloads weights. No model is trained. The output includes
WORKED/NOT WORKED, elapsed seconds, and peak process memory in MB.
"""

import argparse
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time

MODELS = {
    "bolt": "amazon/chronos-bolt-tiny",
    "chronos2": "amazon/chronos-2",
}
RESULT_MARKER = "__AI_PROBE_RESULT__="


def worker(model_key):
    """Run one model; a separate process gives independent memory results."""
    import torch
    from chronos import BaseChronosPipeline

    torch.set_num_threads(min(4, os.cpu_count() or 1))
    # Synthetic 90-day retail series with weekly variation; no training.
    history = [float(max(0, round(12 + 4 * math.sin(2 * math.pi * i / 7))))
               for i in range(90)]
    context = torch.tensor(history, dtype=torch.float32)
    inputs = context.unsqueeze(0) if model_key == "bolt" else [context]

    load_start = time.perf_counter()
    pipeline = BaseChronosPipeline.from_pretrained(
        MODELS[model_key], device_map="cpu"
    )
    load_seconds = time.perf_counter() - load_start

    forecast_start = time.perf_counter()
    with torch.inference_mode():
        quantiles, _ = pipeline.predict_quantiles(
            inputs, prediction_length=30, quantile_levels=[0.1, 0.5, 0.9]
        )
    forecast_seconds = time.perf_counter() - forecast_start

    first = quantiles[0]
    if first.ndim == 3:
        first = first[0]
    if tuple(first.shape) != (30, 3):
        raise RuntimeError(f"Unexpected forecast shape: {tuple(first.shape)}")
    if not torch.isfinite(first).all().item():
        raise RuntimeError("Forecast contains non-finite values")

    return {
        "model": MODELS[model_key],
        "worked": True,
        "load_seconds": round(load_seconds, 2),
        "forecast_seconds": round(forecast_seconds, 2),
        "forecast_days": 30,
        "first_day_p10_p50_p90": [round(float(v), 2) for v in first[0].tolist()],
    }


def measure_process(model_key, timeout_seconds):
    """Measure wall time and peak resident memory while child loads/runs AI."""
    import psutil

    start = time.perf_counter()
    peak_bytes = 0
    timed_out = False
    script = str(Path(__file__).resolve())
    with tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as log:
        proc = subprocess.Popen(
            [sys.executable, script, "--worker", model_key],
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        psproc = psutil.Process(proc.pid)
        while proc.poll() is None:
            try:
                processes = [psproc] + psproc.children(recursive=True)
                memory = sum(p.memory_info().rss for p in processes if p.is_running())
                peak_bytes = max(peak_bytes, memory)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            if time.perf_counter() - start > timeout_seconds:
                timed_out = True
                proc.kill()
                break
            time.sleep(0.1)
        proc.wait()
        elapsed = round(time.perf_counter() - start, 2)
        log.seek(0)
        output = log.read()

    result = {
        "model": MODELS[model_key],
        "worked": False,
        "seconds_taken": elapsed,
        "peak_process_memory_mb": round(peak_bytes / 1024 / 1024, 1),
        "python": platform.python_version(),
    }
    if timed_out:
        result["error"] = f"Timed out after {timeout_seconds} seconds"
    elif proc.returncode != 0:
        result["error"] = "\n".join(output.strip().splitlines()[-10:]) or "Process failed"
    else:
        for line in output.splitlines():
            if line.startswith(RESULT_MARKER):
                try:
                    details = json.loads(line[len(RESULT_MARKER):])
                    result.update(details)
                    result["worked"] = True
                except json.JSONDecodeError as exc:
                    result["error"] = f"Could not parse model result: {exc}"
                break
        if not result["worked"] and "error" not in result:
            result["error"] = "Model finished without a valid result"
    return result


def main():
    parser = argparse.ArgumentParser(description="Local CPU feasibility test")
    parser.add_argument("--model", choices=("both", "bolt", "chronos2"), default="both")
    parser.add_argument("--timeout", type=int, default=900,
                        help="Maximum seconds for each model, including first download")
    parser.add_argument("--worker", choices=("bolt", "chronos2"), help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.worker:
        try:
            result = worker(args.worker)
            print(RESULT_MARKER + json.dumps(result), flush=True)
            return 0
        except Exception as exc:
            print(f"{type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
            return 1

    if sys.version_info[:2] not in ((3, 12), (3, 13)):
        print("Use Python 3.12 or 3.13 for this test.")
        return 1
    try:
        import psutil  # noqa: F401
    except ImportError:
        print("Install requirements-ai.txt first (psutil is missing).")
        return 1

    keys = ("bolt", "chronos2") if args.model == "both" else (args.model,)
    results = []
    print("AI feasibility test: CPU only, pretrained weights, no training")
    print("First run downloads weights; times include downloads and loading.\n")
    for key in keys:
        print(f"Testing {MODELS[key]} ...", flush=True)
        result = measure_process(key, args.timeout)
        results.append(result)
        print(f"  WORKED: {'YES' if result['worked'] else 'NO'}")
        print(f"  SECONDS TAKEN: {result['seconds_taken']:.2f}")
        print(f"  PEAK MEMORY: {result['peak_process_memory_mb']:.1f} MB")
        if result.get("worked"):
            print(f"  FORECAST ONLY: {result['forecast_seconds']:.2f} seconds")
            print(f"  FIRST DAY P10/P50/P90: {result['first_day_p10_p50_p90']}")
        else:
            print(f"  ERROR: {result.get('error', 'Unknown error')}")
        print()

    path = Path("ai_probe_results.json")
    path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Results saved to {path.resolve()}")
    return 0 if all(item["worked"] for item in results) else 1


if __name__ == "__main__":
    sys.exit(main())
