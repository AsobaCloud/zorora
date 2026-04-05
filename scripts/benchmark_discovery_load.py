#!/usr/bin/env python3
"""
Phase 1 — Discovery / Imaging API baseline (server + transfer size).

Run with the web app up, e.g.:
  ZORORA_BENCH_URL=http://127.0.0.1:5000 python3 scripts/benchmark_discovery_load.py

Captures latency and response bytes for the same GETs the UI uses in loadImagingView.
Re-run after changes to compare cold server work and payload sizes.
"""

from __future__ import annotations

import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed


def _get(url: str) -> tuple[float, int]:
    t0 = time.perf_counter()
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = resp.read()
    elapsed = time.perf_counter() - t0
    return elapsed, len(body)


def main() -> int:
    base = os.environ.get("ZORORA_BENCH_URL", "http://127.0.0.1:5000").rstrip("/")
    paths = [
        "/api/imaging/config",
        "/api/pipeline/assets",
        "/api/scouting/watchlist",
        "/api/imaging/deposits",
        "/api/imaging/concessions",
        "/api/imaging/generation",
    ]
    urls = [base + p for p in paths]

    print(f"Benchmark target: {base}\n")

    print("--- Sequential GET ---")
    seq_total = 0.0
    for url in urls:
        try:
            dt, nbytes = _get(url)
            seq_total += dt
            print(f"  {dt:6.2f}s  {nbytes // 1024:6d} KiB  {url.replace(base, '')}")
        except urllib.error.URLError as e:
            print(f"  FAIL  {url}: {e}", file=sys.stderr)
            print(
                "Start the app (e.g. zorora web) or set ZORORA_BENCH_URL.",
                file=sys.stderr,
            )
            return 1

    print(f"  TOTAL sequential: {seq_total:.2f}s\n")

    print("--- Parallel GET (all 6) ---")
    t0 = time.perf_counter()
    results: dict[str, tuple[float, int]] = {}
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(_get, u): u for u in urls}
        for fut in as_completed(futs):
            u = futs[fut]
            try:
                results[u] = fut.result()
            except Exception as e:
                print(f"  FAIL {u}: {e}", file=sys.stderr)
                return 1
    wall = time.perf_counter() - t0
    total_bytes = 0
    for url in urls:
        dt, nbytes = results[url]
        total_bytes += nbytes
        print(f"  {dt:6.2f}s  {nbytes // 1024:6d} KiB  {url.replace(base, '')}")
    print(f"  Wall-clock (parallel): {wall:.2f}s  combined ~{total_bytes // 1024} KiB\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
