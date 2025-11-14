#!/usr/bin/env python3
"""
Utility script to generate tuned.openshift.io/v1 Tuned manifests.

The script is intentionally dependency-free so it can run anywhere Python 3.8+
is available (CI, developer workstations, or automation pipelines).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import OrderedDict
from typing import Dict, Iterable, List, Sequence, Tuple


def _parse_key_value_pairs(
    raw_values: Sequence[str],
    *,
    parameter: str,
    allow_empty_value: bool = False,
) -> List[Tuple[str, str]]:
    """Split KEY=VALUE (or KEY when allow_empty_value=True) pairs."""
    parsed: List[Tuple[str, str]] = []
    for raw in raw_values:
        if "=" in raw:
            key, value = raw.split("=", 1)
        elif allow_empty_value:
            key, value = raw, ""
        else:
            raise ValueError(f"{parameter} expects KEY=VALUE entries, got '{raw}'")
        key = key.strip()
        value = value.strip()
        if not key:
            raise ValueError(f"{parameter} entries must include a non-empty key (got '{raw}')")
        parsed.append((key, value))
    return parsed


def _parse_section_entries(raw_values: Sequence[str]) -> List[Tuple[str, str, str]]:
    """
    Parse SECTION:KEY=VALUE entries for arbitrary tuned.ini sections.

    Examples:
        bootloader:cmdline_ocp_realtime=+nohz_full=1-3
        service:service.stalld=start,enable
    """
    parsed: List[Tuple[str, str, str]] = []
    for raw in raw_values:
        if ":" not in raw:
            raise ValueError(
                f"--section expects SECTION:KEY=VALUE entries, got '{raw}'"
            )
        section, remainder = raw.split(":", 1)
        section = section.strip()
        if not section:
            raise ValueError(f"--section requires a section name before ':', got '{raw}'")
        key_value = _parse_key_value_pairs([remainder], parameter="--section")
        parsed.append((section, key_value[0][0], key_value[0][1]))
    return parsed


def _build_profile_ini(
    *,
    summary: str,
    includes: Sequence[str],
    main_options: Sequence[Tuple[str, str]],
    variables: Sequence[Tuple[str, str]],
    sysctls: Sequence[Tuple[str, str]],
    extra_sections: Sequence[Tuple[str, str, str]],
) -> str:
    sections: "OrderedDict[str, List[str]]" = OrderedDict()
    sections["main"] = [f"summary={summary}"]
    if includes:
        sections["main"].append(f"include={','.join(includes)}")
    for key, value in main_options:
        sections["main"].append(f"{key}={value}")

    if variables:
        sections["variables"] = [f"{key}={value}" for key, value in variables]
    if sysctls:
        sections["sysctl"] = [f"{key}={value}" for key, value in sysctls]

    for section, key, value in extra_sections:
        section = section.strip()
        if not section:
            continue
        if section not in sections:
            sections[section] = []
        sections[section].append(f"{key}={value}")

    rendered_sections: List[str] = []
    non_empty_sections = [(name, lines) for name, lines in sections.items() if lines]
    for idx, (name, lines) in enumerate(non_empty_sections):
        rendered_sections.append(f"[{name}]")
        rendered_sections.extend(lines)
        if idx != len(non_empty_sections) - 1:
            rendered_sections.append("")
    return "\n".join(rendered_sections)


def _json_string(value: str) -> str:
    """Return a JSON-encoded string (adds surrounding quotes, escapes)."""
    return json.dumps(value)


def _render_manifest(
    *,
    profile_name: str,
    namespace: str,
    profile_ini: str,
    machine_config_labels: Sequence[Tuple[str, str]],
    match_labels: Sequence[Tuple[str, str]],
    priority: int,
) -> str:
    lines: List[str] = [
        "apiVersion: tuned.openshift.io/v1",
        "kind: Tuned",
        "metadata:",
        f"  name: {profile_name}",
    ]
    if namespace:
        lines.append(f"  namespace: {namespace}")
    lines.extend(
        [
            "spec:",
            "  profile:",
            "  - data: |",
        ]
    )
    profile_lines = profile_ini.splitlines()
    if not profile_lines:
        raise ValueError("Profile contents may not be empty")
    for entry in profile_lines:
        # Preserve blank lines for readability inside the literal block.
        if entry:
            lines.append(f"      {entry}")
        else:
            lines.append("      ")
    lines.append(f"    name: {profile_name}")

    if not machine_config_labels and not match_labels:
        raise ValueError("At least one --machine-config-label or --match-label must be provided")

    lines.append("  recommend:")

    if machine_config_labels:
        lines.append("  - machineConfigLabels:")
        for key, value in machine_config_labels:
            lines.append(f"      {key}: {_json_string(value)}")
        start_written = True
    else:
        start_written = False

    if match_labels:
        prefix = "    match:" if start_written else "  - match:"
        lines.append(prefix)
        item_indent = "      - " if start_written else "    - "
        value_indent = "        " if start_written else "      "
        for label, value in match_labels:
            lines.append(f"{item_indent}label: {_json_string(label)}")
            if value != "":
                lines.append(f"{value_indent}value: {_json_string(value)}")
        start_written = True

    priority_prefix = "    priority" if start_written else "  - priority"
    lines.append(f"{priority_prefix}: {priority}")

    profile_prefix = "    profile" if start_written else "  - profile"
    lines.append(f"{profile_prefix}: {_json_string(profile_name)}")

    return "\n".join(lines) + "\n"


def generate_manifest(args: argparse.Namespace) -> str:
    includes = [value.strip() for value in args.include or [] if value.strip()]

    main_options = _parse_key_value_pairs(args.main_option or [], parameter="--main-option")
    variables = _parse_key_value_pairs(args.variable or [], parameter="--variable")
    sysctls = _parse_key_value_pairs(args.sysctl or [], parameter="--sysctl")
    extra_sections = _parse_section_entries(args.section or [])

    match_labels = _parse_key_value_pairs(
        args.match_label or [],
        parameter="--match-label",
        allow_empty_value=True,
    )
    machine_config_labels = _parse_key_value_pairs(
        args.machine_config_label or [],
        parameter="--machine-config-label",
        allow_empty_value=True,
    )

    profile_ini = _build_profile_ini(
        summary=args.summary,
        includes=includes,
        main_options=main_options,
        variables=variables,
        sysctls=sysctls,
        extra_sections=extra_sections,
    )

    manifest = _render_manifest(
        profile_name=args.profile_name,
        namespace=args.namespace,
        profile_ini=profile_ini,
        machine_config_labels=machine_config_labels,
        match_labels=match_labels,
        priority=args.priority,
    )
    return manifest


def parse_arguments(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate tuned.openshift.io/v1 Tuned manifests for the Node Tuning Operator.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--profile-name", required=True, help="Name of the Tuned profile and resource")
    parser.add_argument("--summary", required=True, help="Summary placed inside the [main] section")
    parser.add_argument(
        "--namespace",
        default="openshift-cluster-node-tuning-operator",
        help="Namespace to place in metadata.namespace",
    )
    parser.add_argument(
        "--include",
        action="append",
        help="Append an entry to the 'include=' list (multiple flags allowed)",
    )
    parser.add_argument(
        "--main-option",
        action="append",
        help="Add KEY=VALUE to the [main] section beyond summary/include",
    )
    parser.add_argument(
        "--variable",
        action="append",
        help="Add KEY=VALUE to the [variables] section",
    )
    parser.add_argument(
        "--sysctl",
        action="append",
        help="Add KEY=VALUE to the [sysctl] section",
    )
    parser.add_argument(
        "--section",
        action="append",
        help="Add arbitrary SECTION:KEY=VALUE lines (e.g. bootloader:cmdline=...)",
    )
    parser.add_argument(
        "--machine-config-label",
        action="append",
        help="Add a MachineConfigPool selector (key=value) under machineConfigLabels",
    )
    parser.add_argument(
        "--match-label",
        action="append",
        help="Add a node label entry (key[=value]) under recommend[].match[]",
    )
    parser.add_argument(
        "--priority",
        type=int,
        default=20,
        help="Recommendation priority",
    )
    parser.add_argument(
        "--output",
        help="Output file path; defaults to <profile-name>.yaml in the current directory",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print manifest to stdout instead of writing to disk",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str]) -> int:
    args = parse_arguments(argv)
    try:
        manifest = generate_manifest(args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.dry_run:
        sys.stdout.write(manifest)
        return 0

    output_path = args.output or f"{args.profile_name}.yaml"
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(manifest)
    print(f"Wrote Tuned manifest to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

