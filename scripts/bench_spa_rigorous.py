#!/usr/bin/env python3
"""
Rigorous SPA HTTP benchmarks — protocol (read this before trusting numbers)

PRIMARY METRICS (match how index.html loads data)
  • bundle_wall: elapsed from firing a tab's requests in parallel until the last
    completes — same shape as Promise.all (slowest leg sets perceived wait).
  • slowest_leg: max of individual request latencies inside that bundle.
  • bytes_total: sum of raw response body sizes (transfer weight).

MODES
  • bundle (default): one parallel batch per tab per iteration — headline numbers.
  • isolated: each endpoint timed alone, sequentially within an iteration —
    attributes delay to a specific URL (no parallel contention on the client).

CONTROLS (minimize "endless trial and error")
  • Warmup iterations are discarded (TCP/TLS + server cold paths).
  • Default: one requests.Session per iteration (HTTP keep-alive, like a open tab).
  • Use the same machine/network for before/after deploy comparisons.
  • Report median + p90 + p95; mean alone is misleading for skewed latency.

SAMPLE SIZE
  • Default N=15 iterations after warmup. For CI/regression gates use N>=30.

OUTPUT
  • Human table to stdout; optional --csv for paired statistical analysis in R/pandas.

ENV
  • ZORORA_BENCH_URL   base URL (default https://zorora.asoba.co)
  • ZORORA_BENCH_N     iterations (default 15)
  • ZORORA_BENCH_WARMUP (default 1)
"""
from __future__ import annotations

import argparse
import csv
import os
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable

import requests

DEFAULT_BASE = "https://zorora.asoba.co"


@dataclass(frozen=True)
class BundleSpec:
    key: str
    label: str
    jobs: tuple[Callable[[requests.Session], tuple[str, float, int, int]], ...]


def _pctile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return float("nan")
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * p
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def _stats(vals: list[float]) -> dict[str, float]:
    vals = sorted(vals)
    return {
        "n": float(len(vals)),
        "mean": statistics.fmean(vals),
        "stdev": statistics.stdev(vals) if len(vals) > 1 else 0.0,
        "median": statistics.median(vals),
        "p90": _pctile(vals, 0.90),
        "p95": _pctile(vals, 0.95),
    }


def _gv_jobs():
    gv_params = {"topic": "", "date_from": None, "date_to": None}

    def f1(s: requests.Session):
        return _timed_get(s, "/api/news-intel/facets")

    def f2(s: requests.Session):
        return _timed_post_json(s, "/api/news-intel/stats", gv_params)

    def f3(s: requests.Session):
        return _timed_post_json(
            s, "/api/news-intel/articles", {**gv_params, "limit": 200}
        )

    def f4(s: requests.Session):
        return _timed_get(s, "/api/market/latest")

    return (f1, f2, f3, f4)


def _imaging_jobs():
    return (
        lambda s: _timed_get(s, "/api/imaging/config"),
        lambda s: _timed_get(s, "/api/pipeline/assets"),
        lambda s: _timed_get(s, "/api/scouting/watchlist"),
        lambda s: _timed_get(s, "/api/imaging/deposits"),
        lambda s: _timed_get(s, "/api/imaging/concessions"),
        lambda s: _timed_get(s, "/api/imaging/generation"),
    )


def _regulatory_jobs():
    return (
        lambda s: _timed_get(s, "/api/regulatory/events?limit=20"),
        lambda s: _timed_get(s, "/api/regulatory/provenance"),
        lambda s: _timed_get(s, "/api/regulatory/rps?limit=10"),
        lambda s: _timed_get(s, "/api/regulatory/eia/capacity?limit=10"),
        lambda s: _timed_get(s, "/api/regulatory/eia/generation?limit=10"),
        lambda s: _timed_get(s, "/api/regulatory/rates?limit=10"),
    )


def _timed_get(session: requests.Session, path: str):
    url = session.base_url + path  # type: ignore[attr-defined]
    timeout = float(getattr(session, "_timeout", 120))
    t0 = time.perf_counter()
    r = session.get(url, timeout=timeout)
    dt = time.perf_counter() - t0
    return path, dt, r.status_code, len(r.content)


def _timed_post_json(session: requests.Session, path: str, payload: dict):
    url = session.base_url + path  # type: ignore[attr-defined]
    timeout = float(getattr(session, "_timeout", 120))
    t0 = time.perf_counter()
    r = session.post(url, json=payload, timeout=timeout)
    dt = time.perf_counter() - t0
    return path, dt, r.status_code, len(r.content)


def _make_session(base: str, timeout: float) -> requests.Session:
    s = requests.Session()
    s.base_url = base.rstrip("/")  # type: ignore[attr-defined]
    s._timeout = timeout  # type: ignore[attr-defined]
    return s


def _run_bundle(
    session: requests.Session,
    jobs: tuple,
) -> tuple[float, float, int, list[tuple[str, float, int, int]]]:
    def _wrap(j):
        def _inner():
            return j(session)

        return _inner

    t_wall = time.perf_counter()
    results: list[tuple[str, float, int, int]] = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(_wrap(j)) for j in jobs]
        for fut in as_completed(futs):
            path, dt, code, nbytes = fut.result()
            results.append((path, dt, code, nbytes))
    wall = time.perf_counter() - t_wall
    slowest = max(r[1] for r in results)
    total_b = sum(r[3] for r in results)
    return wall, slowest, total_b, results


def _bundles() -> list[BundleSpec]:
    return [
        BundleSpec("html", "HTML shell", (lambda s: _timed_get(s, "/"),)),
        BundleSpec(
            "research",
            "Research (history)",
            (lambda s: _timed_get(s, "/api/research/history?limit=50"),),
        ),
        BundleSpec("alerts", "Alerts", (lambda s: _timed_get(s, "/api/alerts"),)),
        BundleSpec("global", "Global View", _gv_jobs()),
        BundleSpec("regulatory", "Regulatory", _regulatory_jobs()),
        BundleSpec("imaging", "Discovery / Imaging", _imaging_jobs()),
        BundleSpec(
            "scouting",
            "Scouting",
            (lambda s: _timed_get(s, "/api/scouting/items?type=greenfield"),),
        ),
    ]


def main() -> int:
    p = argparse.ArgumentParser(description="Rigorous SPA bundle / isolated HTTP benchmarks")
    p.add_argument(
        "--mode",
        choices=("bundle", "isolated", "both"),
        default="bundle",
        help="bundle=parallel per tab; isolated=each request alone (attribution)",
    )
    p.add_argument("--csv", metavar="FILE", help="append one row per measurement to CSV")
    p.add_argument(
        "--tag",
        default="",
        help="label for this run (stored in CSV column run_tag for before/after joins)",
    )
    p.add_argument("--sleep", type=float, default=0.0, help="seconds between iterations")
    args = p.parse_args()

    base = os.environ.get("ZORORA_BENCH_URL", DEFAULT_BASE).rstrip("/")
    timeout = float(os.environ.get("ZORORA_BENCH_TIMEOUT", "120"))
    n = int(os.environ.get("ZORORA_BENCH_N", "15"))
    warmup = int(os.environ.get("ZORORA_BENCH_WARMUP", "1"))

    bundles = _bundles()

    print(f"Target: {base}")
    print(f"Iterations: {n} (warmup discarded: {warmup})  mode={args.mode}")
    print("Keep-alive: new Session per iteration\n")

    rows_for_csv: list[dict] = []

    def run_bundle_mode():
        for spec in bundles:
            walls: list[float] = []
            slowest: list[float] = []
            bytes_tot: list[int] = []
            per_path: dict[str, list[float]] = {}

            for i in range(warmup + n):
                sess = _make_session(base, timeout)
                wall, slow, tb, res = _run_bundle(sess, spec.jobs)
                for path, dt, _, _ in res:
                    per_path.setdefault(path, []).append(dt)
                if i >= warmup:
                    walls.append(wall)
                    slowest.append(slow)
                    bytes_tot.append(tb)
                if args.sleep > 0:
                    time.sleep(args.sleep)

            ws = _stats(walls)
            ss = _stats(slowest)
            bt = _stats([float(b) for b in bytes_tot])
            print(f"=== {spec.label} [{spec.key}] parallel bundle ===")
            print(
                f"  wall:   median {ws['median']:.3f}s  p90 {ws['p90']:.3f}s  "
                f"p95 {ws['p95']:.3f}s  mean {ws['mean']:.3f}s  stdev {ws['stdev']:.3f}s"
            )
            print(
                f"  slowest leg (per iter max): median {ss['median']:.3f}s  "
                f"p90 {ss['p90']:.3f}s  p95 {ss['p95']:.3f}s"
            )
            print(
                f"  bytes_total: median {bt['median'] / 1024:.0f} KiB  "
                f"p90 {bt['p90'] / 1024:.0f} KiB"
            )

            rows_for_csv.append(
                {
                    "run_tag": args.tag,
                    "scenario": spec.key,
                    "mode": "bundle",
                    "metric": "wall_s",
                    **{k: ws[k] for k in ("median", "p90", "p95", "mean", "stdev", "n")},
                }
            )
            rows_for_csv.append(
                {
                    "run_tag": args.tag,
                    "scenario": spec.key,
                    "mode": "bundle",
                    "metric": "slowest_leg_s",
                    **{k: ss[k] for k in ("median", "p90", "p95", "mean", "stdev", "n")},
                }
            )

            if len(spec.jobs) > 1:
                print("  Per-endpoint latency (isolated within parallel burst — median across iters):")
                for path in sorted(per_path.keys()):
                    vals = per_path[path][warmup:]
                    st = _stats(vals)
                    print(
                        f"    {path:52} med {st['median']:.3f}s  "
                        f"p90 {st['p90']:.3f}s  p95 {st['p95']:.3f}s"
                    )

    def run_isolated_mode():
        gv_params = {"topic": "", "date_from": None, "date_to": None}
        isolated_specs: list[tuple[str, Callable[[requests.Session], tuple]]] = [
            ("/", lambda s: _timed_get(s, "/")),
            (
                "/api/research/history?limit=50",
                lambda s: _timed_get(s, "/api/research/history?limit=50"),
            ),
            ("/api/alerts", lambda s: _timed_get(s, "/api/alerts")),
            ("/api/news-intel/facets", lambda s: _timed_get(s, "/api/news-intel/facets")),
            (
                "/api/news-intel/stats",
                lambda s: _timed_post_json(s, "/api/news-intel/stats", gv_params),
            ),
            (
                "/api/news-intel/articles",
                lambda s: _timed_post_json(
                    s, "/api/news-intel/articles", {**gv_params, "limit": 200}
                ),
            ),
            ("/api/market/latest", lambda s: _timed_get(s, "/api/market/latest")),
            (
                "/api/regulatory/events?limit=20",
                lambda s: _timed_get(s, "/api/regulatory/events?limit=20"),
            ),
            (
                "/api/regulatory/provenance",
                lambda s: _timed_get(s, "/api/regulatory/provenance"),
            ),
            (
                "/api/regulatory/rps?limit=10",
                lambda s: _timed_get(s, "/api/regulatory/rps?limit=10"),
            ),
            (
                "/api/regulatory/eia/capacity?limit=10",
                lambda s: _timed_get(s, "/api/regulatory/eia/capacity?limit=10"),
            ),
            (
                "/api/regulatory/eia/generation?limit=10",
                lambda s: _timed_get(s, "/api/regulatory/eia/generation?limit=10"),
            ),
            (
                "/api/regulatory/rates?limit=10",
                lambda s: _timed_get(s, "/api/regulatory/rates?limit=10"),
            ),
            ("/api/imaging/config", lambda s: _timed_get(s, "/api/imaging/config")),
            ("/api/pipeline/assets", lambda s: _timed_get(s, "/api/pipeline/assets")),
            (
                "/api/scouting/watchlist",
                lambda s: _timed_get(s, "/api/scouting/watchlist"),
            ),
            ("/api/imaging/deposits", lambda s: _timed_get(s, "/api/imaging/deposits")),
            (
                "/api/imaging/concessions",
                lambda s: _timed_get(s, "/api/imaging/concessions"),
            ),
            (
                "/api/imaging/generation",
                lambda s: _timed_get(s, "/api/imaging/generation"),
            ),
            (
                "/api/scouting/items?type=greenfield",
                lambda s: _timed_get(s, "/api/scouting/items?type=greenfield"),
            ),
        ]

        print("=== ISOLATED (sequential requests, one session per iteration) ===\n")
        for path, job in isolated_specs:
            times: list[float] = []
            bytes_list: list[int] = []
            for i in range(warmup + n):
                sess = _make_session(base, timeout)
                _, dt, code, nbytes = job(sess)
                if code != 200:
                    print(f"WARN {path} HTTP {code}", file=sys.stderr)
                if i >= warmup:
                    times.append(dt)
                    bytes_list.append(nbytes)
                if args.sleep > 0:
                    time.sleep(args.sleep)
            st = _stats(times)
            nb = statistics.median(bytes_list) if bytes_list else 0
            print(
                f"{path:55} med {st['median']:.3f}s  p90 {st['p90']:.3f}s  "
                f"p95 {st['p95']:.3f}s  ~{nb / 1024:.0f} KiB"
            )
            rows_for_csv.append(
                {
                    "run_tag": args.tag,
                    "scenario": path,
                    "mode": "isolated",
                    "metric": "request_s",
                    **{k: st[k] for k in ("median", "p90", "p95", "mean", "stdev", "n")},
                }
            )

    if args.mode in ("bundle", "both"):
        run_bundle_mode()
        print()
    if args.mode in ("isolated", "both"):
        run_isolated_mode()

    if args.csv:
        exists = os.path.isfile(args.csv)
        fieldnames = [
            "run_tag",
            "scenario",
            "mode",
            "metric",
            "n",
            "mean",
            "stdev",
            "median",
            "p90",
            "p95",
        ]
        with open(args.csv, "a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            if not exists:
                w.writeheader()
            for row in rows_for_csv:
                w.writerow(row)
        print(f"\nWrote {len(rows_for_csv)} summary rows → {args.csv}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
