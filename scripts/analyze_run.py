#!/usr/bin/env python3
"""Analyze latest Matrix-CPL2 run artifacts.

The script keeps the 4 requested features as independent functions:
1) show ini config + cache/matrix sizes
2) show simulation cycles from tltest_v3lt.log
3) show key L2/L3 request counters
4) run plot_mshr.py to draw snapshots
"""

from __future__ import annotations

import argparse
import configparser
import re
import subprocess
from pathlib import Path
from typing import Dict, Tuple


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze latest TL test run")
    parser.add_argument("run_dir", help="Path to tl-test run directory")
    parser.add_argument("--no-plot", action="store_true", help="Skip running plot_mshr.py")
    return parser.parse_args()


def resolve_paths(run_dir: Path, script_repo_root: Path) -> Tuple[Path, Path, Path, Path]:
    candidate_ini = run_dir / "configuration.ini"
    if candidate_ini.exists():
        ini_path = candidate_ini
    else:
        candidate_repo_root = run_dir.parent.parent
        candidate_repo_ini = candidate_repo_root / "configuration.ini"
        if candidate_repo_ini.exists():
            ini_path = candidate_repo_ini
        else:
            ini_path = script_repo_root / "configuration.ini"

    log_path = run_dir / "tltest_v3lt.log"
    perf_path = run_dir / "tltest_v3lt_perf.log"
    db_path = run_dir / "chiseldb.db"
    return ini_path, log_path, perf_path, db_path


def read_ini(ini_path: Path) -> Dict[str, Dict[str, str]]:
    cfg = configparser.ConfigParser()
    if not ini_path.exists():
        raise FileNotFoundError(f"ini file not found: {ini_path}")
    cfg.read(ini_path)
    return {sec: dict(cfg[sec]) for sec in cfg.sections()}


def human_size(n: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    value = float(n)
    idx = 0
    while value >= 1024.0 and idx < len(units) - 1:
        value /= 1024.0
        idx += 1
    if idx == 0:
        return f"{int(value)} {units[idx]}"
    return f"{value:.2f} {units[idx]}"


def analyze_config_and_sizes(ini_data: Dict[str, Dict[str, str]]) -> None:
    print("\n=== [1] Config + Size Summary ===")
    for sec, kv in ini_data.items():
        print(f"[{sec}]")
        for k, v in kv.items():
            print(f"  {k} = {v}")

    testtop = ini_data.get("testtop", {})
    matrix = ini_data.get("matrix", {})

    l2_sets = int(testtop.get("l2_sets", "128"))
    l2_ways = int(testtop.get("l2_ways", "8"))
    l2_banks = int(testtop.get("l2_banks", "1"))
    l3_sets = int(testtop.get("l3_sets", "512"))
    l3_ways = int(testtop.get("l3_ways", "8"))
    l3_banks = int(testtop.get("l3_banks", "1"))
    l3cdir_sets = int(testtop.get("l3cdir_sets", str(l2_sets * l2_banks)))
    l3cdir_ways = int(testtop.get("l3cdir_ways", str(l2_ways)))

    block_bytes = 64
    l2_bytes = l2_sets * l2_ways * l2_banks * block_bytes
    l3_bytes = l3_sets * l3_ways * l3_banks * block_bytes

    m = int(matrix.get("m", "64"))
    k = int(matrix.get("k", "256"))
    n = int(matrix.get("n", "64"))
    matrix_formula = m * k + k * n + m * n * 4

    print("\nCache capacity (assume 64B line):")
    print(f"  L2: {l2_sets} sets * {l2_ways} ways * {l2_banks} banks * 64B = {l2_bytes} B ({human_size(l2_bytes)})")
    print(f"  L3: {l3_sets} sets * {l3_ways} ways * {l3_banks} banks * 64B = {l3_bytes} B ({human_size(l3_bytes)})")
    print(f"  L3 client-dir params: sets={l3cdir_sets}, ways={l3cdir_ways}")

    print("\nMatrix size summary:")
    print(f"  m={m}, k={k}, n={n}")
    print(f"  Formula (m*k + k*n + m*n*4) = {matrix_formula} ({human_size(matrix_formula)})")


def parse_sim_cycles(log_path: Path) -> Tuple[int | None, int | None]:
    if not log_path.exists():
        raise FileNotFoundError(f"log file not found: {log_path}")

    complete_cycle = None
    final_cycle = None

    p_complete = re.compile(r"all requests completed at cycle\s+(\d+)")
    p_final = re.compile(r"\[(\d+)\].*Finalize\(\)")

    with log_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            m1 = p_complete.search(line)
            if m1:
                complete_cycle = int(m1.group(1))
            m2 = p_final.search(line)
            if m2:
                final_cycle = int(m2.group(1))

    return complete_cycle, final_cycle


def print_sim_cycles(log_path: Path) -> None:
    print("\n=== [2] Simulation Cycles ===")
    complete_cycle, final_cycle = parse_sim_cycles(log_path)
    if complete_cycle is None and final_cycle is None:
        print("  Could not find cycle markers in log.")
        return
    if complete_cycle is not None:
        print(f"  all requests completed at cycle: {complete_cycle}")
        return
    if final_cycle is not None:
        print(f"  finalize marker at: {final_cycle}")


def parse_perf_metrics(text: str) -> Dict[str, int]:
    # Example line:
    # [PERF ][time= ...] coupledL2.tl2tl.MainPipe@...: acquireBlock, 67103
    metric = {}
    pat = re.compile(r"\[PERF \].*?:\s*([A-Za-z0-9_]+),\s*([0-9]+)")
    for line in text.splitlines():
        m = pat.search(line)
        if m:
            metric[m.group(1)] = int(m.group(2))
    return metric


def print_key_counters(log_path: Path, perf_path: Path) -> None:
    print("\n=== [3] Key Request Counters (L2/L3) ===")

    text = ""
    if perf_path.exists():
        text = perf_path.read_text(encoding="utf-8", errors="ignore")
    elif log_path.exists():
        text = log_path.read_text(encoding="utf-8", errors="ignore")
    else:
        print("  Neither perf log nor raw log exists.")
        return

    metrics = parse_perf_metrics(text)

    l2_keys = [
        "acquireBlock",
        "acquirePerm",
        "probe",
        "release",
        "releaseData",
        "get_miss",
    ]
    l3_keys = [
        "hc_req_acquire_block",
        "hc_req_acquire_perm",
        "hc_req_probe",
        "hc_req_release",
        "hc_req_release_data",
        "hc_req_get",
        "hc_req_put",
    ]

    print("  L2 (coupledL2.tl2tl.MainPipe):")
    for k in l2_keys:
        v = metrics.get(k)
        print(f"    {k:24s}: {v if v is not None else 'N/A'}")

    print("  L3 (huancun.MSHRAlloc):")
    for k in l3_keys:
        v = metrics.get(k)
        print(f"    {k:24s}: {v if v is not None else 'N/A'}")


def run_plot_mshr(script_repo_root: Path, db_path: Path) -> None:
    print("\n=== [4] Run plot_mshr.py ===")
    plot_script = script_repo_root / "scripts" / "plot_mshr.py"
    if not plot_script.exists():
        print(f"  plot script not found: {plot_script}")
        return
    if not db_path.exists():
        print(f"  db not found: {db_path}")
        return

    cmd = ["python3", str(plot_script), str(db_path), "both"]
    print("  Running:", " ".join(cmd))
    print("  Output: PNG files only (no interactive window).")
    try:
        subprocess.run(cmd, check=False, cwd=str(script_repo_root))
    except Exception as e:
        print(f"  Failed to run plot_mshr.py: {e}")


def main() -> int:
    args = parse_args()

    run_dir = Path(args.run_dir).resolve()
    if not run_dir.exists() or not run_dir.is_dir():
        raise FileNotFoundError(f"run directory not found: {run_dir}")

    script_repo_root = Path(__file__).resolve().parent.parent
    ini_path, log_path, perf_path, db_path = resolve_paths(run_dir, script_repo_root)

    ini_data = read_ini(ini_path)
    analyze_config_and_sizes(ini_data)
    print_sim_cycles(log_path)
    print_key_counters(log_path, perf_path)
    if not args.no_plot:
        run_plot_mshr(script_repo_root, db_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
