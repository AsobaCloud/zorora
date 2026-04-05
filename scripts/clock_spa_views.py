#!/usr/bin/env python3
"""
Wall-clock each main sidebar "page" the way the SPA loads data: HTML shell,
then the parallel/serial fetches that tab uses (from index.html).

Not browser paint time — just HTTP completion times, which is what you can
script without a headless browser.
"""
from __future__ import annotations

import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

DEFAULT_BASE = "https://zorora.asoba.co"


def _ms(seconds: float) -> str:
    return f"{seconds * 1000:.0f}ms"


def main() -> int:
    base = os.environ.get("ZORORA_CLOCK_URL", DEFAULT_BASE).rstrip("/")
    timeout = float(os.environ.get("ZORORA_CLOCK_TIMEOUT", "120"))
    sess = requests.Session()

    def get(path: str) -> tuple[str, float, int, int]:
        url = f"{base}{path}"
        t0 = time.perf_counter()
        r = sess.get(url, timeout=timeout)
        dt = time.perf_counter() - t0
        return path, dt, r.status_code, len(r.content)

    def post_json(path: str, payload: dict) -> tuple[str, float, int, int]:
        url = f"{base}{path}"
        t0 = time.perf_counter()
        r = sess.post(url, json=payload, timeout=timeout)
        dt = time.perf_counter() - t0
        return path, dt, r.status_code, len(r.content)

    print(f"Target: {base}\n")

    # 1) True page: HTML
    path, dt, code, nbytes = get("/")
    print(f"HTML shell          GET  /     → {_ms(dt)}  HTTP {code}  {nbytes // 1024} KiB")

    # 2) Per-tab API bundles (wall = slowest when fired together like Promise.all)
    bundles: list[tuple[str, list]] = []

    bundles.append(
        (
            "Research (history)",
            [lambda: get("/api/research/history?limit=50")],
        )
    )
    bundles.append(("Alerts", [lambda: get("/api/alerts")]))

    gv_params = {"topic": "", "date_from": None, "date_to": None}
    bundles.append(
        (
            "Global View",
            [
                lambda: get("/api/news-intel/facets"),
                lambda: post_json("/api/news-intel/stats", gv_params),
                lambda: post_json("/api/news-intel/articles", {**gv_params, "limit": 200}),
                lambda: get("/api/market/latest"),
            ],
        )
    )

    bundles.append(
        (
            "Regulatory",
            [
                lambda: get("/api/regulatory/events?limit=20"),
                lambda: get("/api/regulatory/provenance"),
                lambda: get("/api/regulatory/rps?limit=10"),
                lambda: get("/api/regulatory/eia/capacity?limit=10"),
                lambda: get("/api/regulatory/eia/generation?limit=10"),
                lambda: get("/api/regulatory/rates?limit=10"),
            ],
        )
    )

    bundles.append(
        (
            "Discovery / Imaging",
            [
                lambda: get("/api/imaging/config"),
                lambda: get("/api/pipeline/assets"),
                lambda: get("/api/scouting/watchlist"),
                lambda: get("/api/imaging/deposits"),
                lambda: get("/api/imaging/concessions"),
                lambda: get("/api/imaging/generation"),
            ],
        )
    )

    bundles.append(
        (
            "Scouting",
            [lambda: get("/api/scouting/items?type=greenfield")],
        )
    )

    for label, jobs in bundles:
        t_wall = time.perf_counter()
        results: list[tuple[str, float, int, int]] = []
        with ThreadPoolExecutor(max_workers=8) as ex:
            futs = [ex.submit(j) for j in jobs]
            for fut in as_completed(futs):
                results.append(fut.result())
        wall = time.perf_counter() - t_wall
        worst = max(results, key=lambda x: x[1])
        total_bytes = sum(x[3] for x in results)
        ok = all(x[2] == 200 for x in results)
        status = "all 200" if ok else "see codes"
        print(
            f"{label:22} parallel bundle → wall {_ms(wall)}  (slowest: {worst[0]} {_ms(worst[1])})  "
            f"~{total_bytes // 1024} KiB total  [{status}]"
        )
        for p, dt, code, nb in sorted(results, key=lambda x: -x[1]):
            if len(results) > 1:
                print(f"    {p:48} {_ms(dt):>8}  {code}  {nb // 1024} KiB")

    print(
        "\nDigest tab: no API call on tab switch (renders staged items only).\n"
        "Compare panel: only fetches when watchlist sites are selected.\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
