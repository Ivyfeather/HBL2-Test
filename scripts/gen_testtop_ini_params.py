#!/usr/bin/env python3
"""Generate configuration artifacts from a workspace-level ini file."""

from __future__ import annotations

import argparse
import configparser
from pathlib import Path
import re

TESTTOP_DEFAULTS = {
    "l2_sets": 128,
    "l2_ways": 8,
    "l2_banks": 1,
    "l3cdir_sets": 128,
    "l3cdir_ways": 10,
    "l3_sets": 512,
    "l3_ways": 8,
    "l3_banks": 1,
}

MATRIX_DEFAULTS = {
    "m": 64,
    "k": 256,
    "n": 64,
}

TLTEST_DEFAULTS = {
    "l1_sets": 32,
    "l1_ways": 8,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate configuration files from ini")
    parser.add_argument("--ini", required=True, help="Input ini path")
    parser.add_argument("--out-scala", help="Output Scala file path for TestTop parameters")
    parser.add_argument("--out-matrix-header", help="Output C header path for matrix M/K/N parameters")
    parser.add_argument("--out-tltest-ini", help="Output tltest ini path for l1 cache parameters")
    return parser.parse_args()


def read_section_values(
    parser: configparser.ConfigParser,
    section_name: str,
    defaults: dict[str, int],
    min_value: int = 1,
) -> dict[str, int]:
    values = dict(defaults)
    if section_name not in parser:
        return values

    section = parser[section_name]
    for key in defaults:
        if key not in section:
            continue
        try:
            value = int(section[key].strip())
        except ValueError as exc:
            raise ValueError(f"{section_name}.{key} must be an integer, got: {section[key]!r}") from exc
        if value < min_value:
            if min_value == 0:
                raise ValueError(f"{section_name}.{key} must be >= 0, got: {value}")
            raise ValueError(f"{section_name}.{key} must be >= {min_value}, got: {value}")
        values[key] = value

    return values


def read_values(ini_path: Path) -> tuple[dict[str, int], dict[str, int], dict[str, int]]:
    testtop_values = dict(TESTTOP_DEFAULTS)
    matrix_values = dict(MATRIX_DEFAULTS)
    tltest_values = dict(TLTEST_DEFAULTS)
    if not ini_path.exists():
        return testtop_values, matrix_values, tltest_values

    parser = configparser.ConfigParser()
    parser.read(ini_path)
    testtop_values = read_section_values(parser, "testtop", TESTTOP_DEFAULTS)
    matrix_values = read_section_values(parser, "matrix", MATRIX_DEFAULTS)
    tltest_values = read_section_values(parser, "tltest", TLTEST_DEFAULTS, min_value=0)
    return testtop_values, matrix_values, tltest_values


def _upsert_key_in_section(content: str, section: str, key: str, value: int | str) -> str:
    pattern = re.compile(rf"^(\s*{re.escape(key)}\s*=\s*)([^#\n]*?)(\s*(#.*)?)$", re.MULTILINE)
    if pattern.search(content):
        return pattern.sub(rf"\g<1>{value}\g<3>", content, count=1)

    section_match = re.search(rf"(?m)^\[{re.escape(section)}\]\s*$", content)
    if not section_match:
        raise ValueError(f"[{section}] section not found in target file")

    insert_pos = section_match.end()
    next_section_match = re.search(r"(?m)^\[", content[insert_pos:])
    if next_section_match:
        insert_pos = insert_pos + next_section_match.start()
    else:
        insert_pos = len(content)

    insertion = f"{key:<28}= {value}\n"
    return content[:insert_pos] + insertion + content[insert_pos:]


def _rewrite_sequence_modes(content: str, mode_count: int, mode_value: str) -> str:
    section_match = re.search(r"\[tltest\.sequence\]", content)
    if not section_match:
        raise ValueError("[tltest.sequence] section not found in target file")

    body_start = section_match.end()
    next_section_match = re.search(r"(?m)^\[", content[body_start:])
    if next_section_match:
        body_end = body_start + next_section_match.start()
    else:
        body_end = len(content)

    body = content[body_start:body_end]
    body_lines = body.splitlines(keepends=True)

    # Keep comments/blank lines and remove all existing mode.N assignments.
    kept_lines = [ln for ln in body_lines if not re.match(r"^\s*mode\.\d+\s*=", ln)]
    generated_lines = [f"mode.{i:<22}= {mode_value}\n" for i in range(mode_count)]

    # Always start a new line after the section header.
    new_body = "\n" + "".join(generated_lines) + "".join(kept_lines)

    return content[:body_start] + new_body + content[body_end:]


def update_tltest_ini(path: Path, tltest_values: dict[str, int], testtop_values: dict[str, int]) -> None:
    if not path.exists():
        raise FileNotFoundError(f"tltest ini file not found: {path}")

    content = path.read_text(encoding="utf-8")
    key_map = {
        "cache.cagent.sets": tltest_values["l1_sets"],
        "cache.cagent.ways": tltest_values["l1_ways"],
        "core.tl_m": testtop_values["l2_banks"],
    }

    for key, value in key_map.items():
        content = _upsert_key_in_section(content, "tltest.config", key, value)

    sequence_count = testtop_values["l2_banks"] + 2
    content = _rewrite_sequence_modes(content, sequence_count, "TRACE_WITH_FENCE")

    write_if_changed(path, content)


def render_testtop_scala(values: dict[str, int]) -> str:
    return """package coupledL2

object TestTopIniParams {
  val l2Sets: Int = %(l2_sets)d
  val l2Ways: Int = %(l2_ways)d
  val l2Banks: Int = %(l2_banks)d
  val l3CDirSets: Int = %(l3cdir_sets)d
  val l3CDirWays: Int = %(l3cdir_ways)d

  val l3Sets: Int = %(l3_sets)d
  val l3Ways: Int = %(l3_ways)d
  val l3Banks: Int = %(l3_banks)d
}
""" % values


def render_matrix_header(values: dict[str, int]) -> str:
    return """#ifndef GENERATED_MATRIX_CONFIG_H
#define GENERATED_MATRIX_CONFIG_H

#define MATRIX_M %(m)d
#define MATRIX_K %(k)d
#define MATRIX_N %(n)d

#endif
""" % values


def write_if_changed(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    path.write_text(content, encoding="utf-8")


def main() -> int:
    args = parse_args()
    if not args.out_scala and not args.out_matrix_header and not args.out_tltest_ini:
        raise ValueError(
            "At least one output must be provided: --out-scala or --out-matrix-header or --out-tltest-ini"
        )

    ini_path = Path(args.ini)
    testtop_values, matrix_values, tltest_values = read_values(ini_path)

    if args.out_scala:
        out_scala_path = Path(args.out_scala)
        write_if_changed(out_scala_path, render_testtop_scala(testtop_values))

    if args.out_matrix_header:
        out_header_path = Path(args.out_matrix_header)
        write_if_changed(out_header_path, render_matrix_header(matrix_values))

    if args.out_tltest_ini:
        out_tltest_ini_path = Path(args.out_tltest_ini)
        update_tltest_ini(out_tltest_ini_path, tltest_values, testtop_values)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
