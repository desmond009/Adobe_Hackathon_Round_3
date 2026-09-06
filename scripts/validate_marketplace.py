#!/usr/bin/env python3
"""Validates marketplace.json and every referenced skill's SKILL.md.

Checks (spec section 29):
  * marketplace.json is valid JSON and matches scripts/marketplace.schema.json
  * exactly one skill has entrypoint: true
  * every listed skill path exists and contains a SKILL.md
  * every SKILL.md has valid YAML frontmatter with non-empty name + description,
    and the frontmatter `name` matches the skill's directory name
  * no orphaned skill directory under skills/ is missing from marketplace.json,
    and no marketplace.json entry points at a missing directory

Exit code 0 = all checks pass, 1 = at least one failure. Prints a report either way.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import jsonschema
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def load_marketplace(errors: list[str]) -> dict | None:
    manifest_path = REPO_ROOT / "marketplace.json"
    if not manifest_path.exists():
        fail(errors, "marketplace.json not found at repo root")
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(errors, f"marketplace.json is not valid JSON: {exc}")
        return None

    schema_path = REPO_ROOT / "scripts" / "marketplace.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    for err in validator.iter_errors(manifest):
        fail(errors, f"marketplace.json schema violation at {'/'.join(str(p) for p in err.path)}: {err.message}")

    return manifest


def parse_skill_md(path: Path, errors: list[str]) -> dict | None:
    text = path.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(text)
    if not match:
        fail(errors, f"{path}: missing YAML frontmatter (must start with '---')")
        return None
    try:
        frontmatter = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as exc:
        fail(errors, f"{path}: frontmatter is not valid YAML: {exc}")
        return None

    if not isinstance(frontmatter, dict):
        fail(errors, f"{path}: frontmatter must be a YAML mapping")
        return None

    name = frontmatter.get("name")
    description = frontmatter.get("description")
    if not name or not isinstance(name, str):
        fail(errors, f"{path}: frontmatter missing non-empty 'name'")
    elif not _NAME_RE.match(name):
        fail(errors, f"{path}: frontmatter 'name' {name!r} must be lowercase-kebab-case")
    if not description or not isinstance(description, str) or len(description.strip()) < 10:
        fail(errors, f"{path}: frontmatter missing a substantive 'description'")

    body = text[match.end():]
    if len(body.strip()) == 0:
        fail(errors, f"{path}: SKILL.md body is empty")

    return frontmatter


def validate() -> list[str]:
    errors: list[str] = []
    manifest = load_marketplace(errors)
    if manifest is None:
        return errors

    entrypoints = [s for s in manifest.get("skills", []) if s.get("entrypoint")]
    if len(entrypoints) != 1:
        fail(errors, f"expected exactly one entrypoint skill, found {len(entrypoints)}")
    elif manifest.get("entrypoint") != entrypoints[0]["id"]:
        fail(errors, f"top-level 'entrypoint' ({manifest.get('entrypoint')!r}) does not match "
                      f"the skill marked entrypoint:true ({entrypoints[0]['id']!r})")

    listed_dirs = set()
    for skill in manifest.get("skills", []):
        skill_dir = REPO_ROOT / skill["path"]
        listed_dirs.add(skill_dir.resolve())
        if not skill_dir.is_dir():
            fail(errors, f"skill '{skill['id']}': path {skill['path']} does not exist")
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            fail(errors, f"skill '{skill['id']}': no SKILL.md at {skill['path']}")
            continue
        frontmatter = parse_skill_md(skill_md, errors)
        if frontmatter and frontmatter.get("name") != skill["id"]:
            fail(errors, f"skill '{skill['id']}': SKILL.md frontmatter name "
                          f"{frontmatter.get('name')!r} does not match manifest id")

    skills_root = REPO_ROOT / "skills"
    if skills_root.is_dir():
        for entry in skills_root.iterdir():
            if entry.is_dir() and entry.resolve() not in listed_dirs:
                fail(errors, f"orphaned skill directory not listed in marketplace.json: {entry.relative_to(REPO_ROOT)}")

    return errors


def main() -> None:
    errors = validate()
    if errors:
        print(f"FAILED: {len(errors)} issue(s) found\n")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    print("OK: marketplace.json and all SKILL.md files are valid.")


if __name__ == "__main__":
    main()
