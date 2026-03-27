#!/usr/bin/env python3
"""Generate configuration artifacts from a workspace-level ini file."""

from __future__ import annotations

import argparse
import configparser
from pathlib import Path

TESTTOP_DEFAULTS = {
    "l2_sets": 128,
    "l2_ways": 8,
    "l2_banks": 1,
    "l3_sets": 512,
    "l3_ways": 8,
    "l3_banks": 1,
}

MATRIX_DEFAULTS = {
    "m": 64,
    "k": 256,
    "n": 64,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate configuration files from ini")
    parser.add_argument("--ini", required=True, help="Input ini path")
    parser.add_argument("--out-scala", help="Output Scala file path for TestTop parameters")
    parser.add_argument("--out-matrix-header", help="Output C header path for matrix M/K/N parameters")
    return parser.parse_args()


def read_section_values(
    parser: configparser.ConfigParser,
    section_name: str,
    defaults: dict[str, int],
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
        if value <= 0:
            raise ValueError(f"{section_name}.{key} must be > 0, got: {value}")
        values[key] = value

    return values


def read_values(ini_path: Path) -> tuple[dict[str, int], dict[str, int]]:
    testtop_values = dict(TESTTOP_DEFAULTS)
    matrix_values = dict(MATRIX_DEFAULTS)
    if not ini_path.exists():
        return testtop_values, matrix_values

    parser = configparser.ConfigParser()
    parser.read(ini_path)
    testtop_values = read_section_values(parser, "testtop", TESTTOP_DEFAULTS)
    matrix_values = read_section_values(parser, "matrix", MATRIX_DEFAULTS)
    return testtop_values, matrix_values


def render_testtop_scala(values: dict[str, int]) -> str:
    return """package coupledL2

object TestTopIniParams {
  val l2Sets: Int = %(l2_sets)d
  val l2Ways: Int = %(l2_ways)d
  val l2Banks: Int = %(l2_banks)d

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
    if not args.out_scala and not args.out_matrix_header:
        raise ValueError("At least one output must be provided: --out-scala or --out-matrix-header")

    ini_path = Path(args.ini)
    testtop_values, matrix_values = read_values(ini_path)

    if args.out_scala:
        out_scala_path = Path(args.out_scala)
        write_if_changed(out_scala_path, render_testtop_scala(testtop_values))

    if args.out_matrix_header:
        out_header_path = Path(args.out_matrix_header)
        write_if_changed(out_header_path, render_matrix_header(matrix_values))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
