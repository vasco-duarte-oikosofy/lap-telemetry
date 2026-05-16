#!/usr/bin/env python3
"""
Register a track outline: generate ES module, update manifest, rebuild bundle.

Usage:
    python3 scripts/register_outline.py data/track-outlines/bahrain_outline.json

This command:
1. Validates the outline JSON
2. Generates the ES module (calls generate_outline_module.js)
3. Adds import + map entries to trackOutlineManifest.js
4. Rebuilds dist/compare.html

Idempotent: running twice makes no changes on the second run.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# ── Project root ──────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / "web" / "js" / "trackOutlineManifest.js"
BACKUP_PATH = ROOT / "web" / "js" / "trackOutlineManifest_backup.js"
GENERATE_SCRIPT = ROOT / "scripts" / "generate_outline_module.js"

# ── ANSI helpers ───────────────────────────────────────────────────────────
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
RESET = "\033[0m"


def ok(msg: str) -> None:
    print(f"{GREEN}✅ {msg}{RESET}")


def info(msg: str) -> None:
    print(f"{YELLOW}ℹ️  {msg}{RESET}")


def fail(msg: str) -> None:
    print(f"{RED}❌ {msg}{RESET}", file=sys.stderr)


# ── Step 0: Validate outline JSON ──────────────────────────────────────────

REQUIRED_TOP_LEVEL = {
    "schema_version": (int,),
    "source": (str,),
    "track_name": (str,),
    "sim_track_name": (str,),
    "coordinate_system": (str,),
    "units": (str,),
    "track_name_mapping": (dict,),
    "centerline": (list,),
}

REQUIRED_TRACK_NAME_MAPPING = {
    "canonical_sim_track_name": (str,),
    "accepted_sim_track_names": (list,),
}

REQUIRED_CENTERLINE_ITEM = {"x": (int, float), "y": (int, float)}


def validate_outline(data: dict, path: str) -> list[str]:
    """Validate outline JSON structure. Returns list of error messages."""
    errors: list[str] = []

    # Top-level required fields
    for key, expected_types in REQUIRED_TOP_LEVEL.items():
        if key not in data:
            errors.append(f"Missing required field: '{key}'")
        elif not isinstance(data[key], expected_types):
            type_names = "/".join(t.__name__ for t in expected_types)
            errors.append(
                f"Field '{key}' has wrong type: "
                f"expected {type_names}, got {type(data[key]).__name__}"
            )

    # track_name_mapping sub-fields
    mapping = data.get("track_name_mapping", {})
    for key, expected_types in REQUIRED_TRACK_NAME_MAPPING.items():
        if key not in mapping:
            errors.append(f"Missing field in track_name_mapping: '{key}'")
        elif not isinstance(mapping[key], expected_types):
            type_names = "/".join(t.__name__ for t in expected_types)
            errors.append(
                f"track_name_mapping.'{key}' has wrong type: "
                f"expected {type_names}, got {type(mapping[key]).__name__}"
            )

    # accepted_sim_track_names must be strings
    if "accepted_sim_track_names" in mapping:
        names = mapping["accepted_sim_track_names"]
        for i, name in enumerate(names):
            if not isinstance(name, str):
                errors.append(
                    f"track_name_mapping.accepted_sim_track_names[{i}] "
                    f"must be a string, got {type(name).__name__}"
                )
        # Check for duplicates
        if len(names) != len(set(names)):
            errors.append(
                "track_name_mapping.accepted_sim_track_names contains duplicates"
            )

    # centerline must have points with x,y
    centerline = data.get("centerline", [])
    if isinstance(centerline, list):
        if len(centerline) < 2:
            errors.append(
                f"centerline must have at least 2 points, got {len(centerline)}"
            )
        for i, point in enumerate(centerline):
            if not isinstance(point, dict):
                errors.append(f"centerline[{i}] must be an object, got {type(point).__name__}")
                continue
            for key, expected_types in REQUIRED_CENTERLINE_ITEM.items():
                if key not in point:
                    errors.append(f"centerline[{i}] missing field: '{key}'")
                elif not isinstance(point[key], expected_types):
                    errors.append(
                        f"centerline[{i}].'{key}' has wrong type: "
                        f"expected {'/'.join(t.__name__ for t in expected_types)}, "
                        f"got {type(point[key]).__name__}"
                    )

    # layout_name must be a string if present
    if "layout_name" in data and not isinstance(data["layout_name"], str):
        errors.append(
            f"Field 'layout_name' has wrong type: "
            f"expected str, got {type(data['layout_name']).__name__}"
        )

    # alignment must be an object if present
    if "alignment" in data and not isinstance(data["alignment"], dict):
        errors.append(
            f"Field 'alignment' has wrong type: "
            f"expected dict, got {type(data['alignment']).__name__}"
        )

    # visual_qa must be an object if present
    if "visual_qa" in data and not isinstance(data["visual_qa"], dict):
        errors.append(
            f"Field 'visual_qa' has wrong type: "
            f"expected dict, got {type(data['visual_qa']).__name__}"
        )

    # caveats must be a list if present
    if "caveats" in data and not isinstance(data["caveats"], list):
        errors.append(
            f"Field 'caveats' has wrong type: "
            f"expected list, got {type(data['caveats']).__name__}"
        )

    return errors


# ── Step 1: Generate ES module ─────────────────────────────────────────────

def generate_es_module(outline_path: str) -> tuple[str, str]:
    """Run generate_outline_module.js. Returns (module_file, export_name)."""
    result = subprocess.run(
        ["node", str(GENERATE_SCRIPT), outline_path],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        fail(f"generate_outline_module.js failed:\n{result.stderr}")
        sys.exit(1)

    # Parse output like: "Wrote web/js/staticBahrain_outlineOutlineData.js (42 KB, export: BAHRAIN_OUTLINE_STATIC_OUTLINE)"
    output = result.stdout.strip()
    match = re.search(r"Wrote\s+(\S+)\s+\([^)]*export:\s*(\w+)\)", output)
    if not match:
        fail(f"Could not parse generate_outline_module.js output:\n{output}")
        sys.exit(1)

    module_file = match.group(1)  # e.g., "web/js/staticBahrain_outlineOutlineData.js"
    export_name = match.group(2)  # e.g., "BAHRAIN_OUTLINE_STATIC_OUTLINE"
    return module_file, export_name


# ── Step 2: Update manifest ────────────────────────────────────────────────

def read_manifest() -> str:
    """Read the current manifest file."""
    return MANIFEST_PATH.read_text(encoding="utf-8")


def write_manifest(content: str) -> None:
    """Write the manifest file."""
    MANIFEST_PATH.write_text(content, encoding="utf-8")


def backup_manifest() -> None:
    """Create a backup of the manifest."""
    shutil.copy2(MANIFEST_PATH, BACKUP_PATH)


def slugify(name: str) -> str:
    """Match the JS slugify function in the manifest."""
    s = str(name or "").lower()
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"[^a-z0-9-]", "", s)
    return s


def find_import_block(content: str) -> tuple[int, int]:
    """Find the range of the import block (first to last import line)."""
    lines = content.split("\n")
    first_import = None
    last_import = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("import ") and " from " in stripped:
            if first_import is None:
                first_import = i
            last_import = i
    if first_import is None:
        return (-1, -1)
    return (first_import, last_import)


def find_outlines_map_range(content: str) -> tuple[int, int]:
    """Find the start and end line of the OUTLINES Map constructor."""
    lines = content.split("\n")
    start = None
    end = None
    depth = 0
    for i, line in enumerate(lines):
        if "new Map([" in line:
            start = i
            depth = line.count("[") - line.count("]")
        elif start is not None:
            depth += line.count("[") - line.count("]")
            if depth <= 0:
                end = i
                break
    return (start or -1, end or -1)


def _find_existing_map_entries(lines: list[str], map_start: int, map_end: int) -> dict[str, tuple[int, str]]:
    """Parse existing entries in the OUTLINES map.
    Returns {slug: (line_index, export_name)}
    """
    entries = {}
    for i in range(map_start, map_end + 1):
        m = re.match(r"\s*\['([^']+)'\s*,\s*(\w+)\s*\]", lines[i])
        if m:
            entries[m.group(1)] = (i, m.group(2))
    return entries


def _export_name_in_map(lines: list[str], map_start: int, map_end: int, export_name: str) -> bool:
    """Check if an export name is already used in the OUTLINES map."""
    for i in range(map_start, map_end + 1):
        if export_name in lines[i]:
            return True
    return False


def _find_block_for_export(lines: list[str], map_start: int, map_end: int, export_name: str) -> tuple[int, int] | None:
    """Find the line range of the block for a given export_name.

    A block = comment line(s) + all entry lines using that export.
    Returns (first_line, last_line) or None if export not found in map.
    """
    # Find all lines referencing this export
    entry_lines = []
    for i in range(map_start, map_end + 1):
        if export_name in lines[i]:
            entry_lines.append(i)
    if not entry_lines:
        return None

    first_entry = entry_lines[0]
    last_entry = entry_lines[-1]

    # Walk backwards from first_entry to find the block's comment
    comment_start = first_entry
    for i in range(first_entry - 1, map_start - 1, -1):
        stripped = lines[i].strip()
        if stripped.startswith("//"):
            comment_start = i
        else:
            break

    return (comment_start, last_entry)


def update_manifest(
    content: str,
    export_name: str,
    module_filename: str,
    track_keys: list[str],
    track_name_display: str,
) -> str:
    """Add import and map entries to manifest if not already present.

    Args:
        content: Current manifest content
        export_name: JS export constant name (e.g., BAHRAIN_OUTLINE_STATIC_OUTLINE)
        module_filename: Just the filename (e.g., staticBahrain_outlineOutlineData.js)
        track_keys: List of slugified track names for the OUTLINES map
        track_name_display: Human-readable name for the comment

    Returns:
        Updated manifest content
    """
    lines = content.split("\n")

    import_statement = f"import {{ {export_name} }} from './{module_filename}';"

    # Check if import already exists
    import_already_present = any(
        export_name in line and "import" in line for line in lines
    )

    added_import = False
    if not import_already_present:
        # Find last import line and insert after it
        _, last_import = find_import_block(content)
        if last_import == -1:
            fail("No import block found in manifest")
            sys.exit(1)
        lines.insert(last_import + 1, import_statement)
        added_import = True

    # Re-parse lines after potential insertion
    content = "\n".join(lines)
    lines = content.split("\n")

    # Check which track keys already exist in the OUTLINES map
    map_start, map_end = find_outlines_map_range(content)
    if map_start == -1:
        fail("Could not find OUTLINES Map in manifest")
        sys.exit(1)

    existing_entries = _find_existing_map_entries(lines, map_start, map_end)
    existing_keys = set(existing_entries.keys())
    export_in_map = _export_name_in_map(lines, map_start, map_end, export_name)

    entries_to_add = [k for k in track_keys if k not in existing_keys]

    if not added_import and not entries_to_add:
        # Already fully registered — no changes needed
        return content  # unchanged

    # Add new entries to the OUTLINES map
    if entries_to_add:
        if export_in_map:
            # This track already has a block — append new entries after it
            block = _find_block_for_export(lines, map_start, map_end, export_name)
            if block:
                insert_idx = block[1] + 1  # After the last entry in this block
                insert_lines = [f"  ['{k}', {export_name}]," for k in entries_to_add]
                for i, line in enumerate(insert_lines):
                    lines.insert(insert_idx + i, line)
            else:
                # Fallback: insert before closing
                close_line = map_end
                insert_lines = [f"  // {track_name_display}"]
                insert_lines.extend(f"  ['{k}', {export_name}]," for k in entries_to_add)
                for i, line in enumerate(insert_lines):
                    lines.insert(close_line + i, line)
        else:
            # Brand new track — add comment + entries before the closing ]);
            close_line = map_end
            insert_lines = [f"  // {track_name_display}"]
            insert_lines.extend(f"  ['{k}', {export_name}]," for k in entries_to_add)
            for i, line in enumerate(insert_lines):
                lines.insert(close_line + i, line)

    content = "\n".join(lines)
    return content


# ── Step 3: Build ──────────────────────────────────────────────────────────

def run_build() -> bool:
    """Run npm run build. Returns True on success."""
    result = subprocess.run(
        ["npm", "run", "build"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    if result.returncode != 0:
        fail(f"npm run build failed:\n{result.stderr}")
        return False
    return True


# ── Main ───────────────────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) != 2:
        fail("Usage: python3 scripts/register_outline.py <outline.json>")
        sys.exit(1)

    outline_path = sys.argv[1]
    outline_file = Path(outline_path)

    # Resolve to absolute path
    if not outline_file.is_absolute():
        outline_file = ROOT / outline_file

    if not outline_file.exists():
        fail(f"File not found: {outline_file}")
        sys.exit(1)

    # ── Step 0: Validate ──────────────────────────────────────────────
    print(f"\n📋 Validating {outline_file.name}...")
    try:
        with open(outline_file, "r", encoding="utf-8") as f:
            outline_data = json.load(f)
    except json.JSONDecodeError as e:
        fail(f"Invalid JSON: {e}")
        sys.exit(1)

    errors = validate_outline(outline_data, str(outline_file))
    if errors:
        fail("Outline validation failed:")
        for err in errors:
            print(f"  • {err}", file=sys.stderr)
        sys.exit(1)
    ok("Outline JSON is valid")

    # Extract metadata
    track_name = outline_data["track_name"]
    mapping = outline_data["track_name_mapping"]
    canonical_sim = mapping["canonical_sim_track_name"]
    accepted_sim_names = mapping["accepted_sim_track_names"]

    # Collect all track keys for the OUTLINES map
    # Use dict.fromkeys to preserve order while deduplicating
    track_keys = list(dict.fromkeys(
        [canonical_sim] + accepted_sim_names
    ))
    # Also add slugified LMU names if present
    if "accepted_lmu_track_names" in mapping:
        for lmu_name in mapping["accepted_lmu_track_names"]:
            slug = slugify(lmu_name)
            if slug not in track_keys:
                track_keys.append(slug)
    if "canonical_lmu_track_name" in mapping:
        slug = slugify(mapping["canonical_lmu_track_name"])
        if slug not in track_keys:
            track_keys.append(slug)

    # ── Step 1: Generate ES module ─────────────────────────────────────
    print(f"\n📦 Generating ES module for '{track_name}'...")
    module_file, export_name = generate_es_module(str(outline_file))
    ok(f"Generated ES module: {module_file}")
    print(f"   Export name: {export_name}")

    # Get just the filename for the import path
    module_filename = Path(module_file).name

    # ── Step 2: Update manifest ────────────────────────────────────────
    print(f"\n📝 Updating manifest...")
    manifest_content = read_manifest()

    # Check if already fully registered
    current_lines = manifest_content.split("\n")
    import_exists = any(
        export_name in line and "import" in line for line in current_lines
    )

    # Check if all track keys already exist in the map
    map_start, map_end = find_outlines_map_range(manifest_content)
    existing_entries = _find_existing_map_entries(current_lines, map_start, map_end)
    existing_keys = set(existing_entries.keys())

    all_keys_present = all(k in existing_keys for k in track_keys)

    if import_exists and all_keys_present:
        info("Outline already registered in manifest")
        info("ES module up-to-date")
        info("No changes needed")
        return

    # Backup the manifest
    backup_manifest()
    ok("Backed up manifest to trackOutlineManifest_backup.js")

    # Update manifest
    updated = update_manifest(
        manifest_content,
        export_name,
        module_filename,
        track_keys,
        track_name,
    )

    write_manifest(updated)

    if not import_exists:
        ok("Added import to manifest")
    else:
        info("Import already present in manifest")

    added_keys = [k for k in track_keys if k not in existing_keys]
    if added_keys:
        ok(f"Added {len(added_keys)} entries to OUTLINES map:")
        for key in added_keys:
            print(f"   - {key}")
    else:
        info("All map entries already present")

    # Validate the updated manifest can be parsed
    print("\n🔍 Validating updated manifest...")
    updated_content = read_manifest()
    if "export function findOutlineByTrackName" not in updated_content:
        fail("Updated manifest is missing exports — file may be corrupted")
        # Restore backup
        shutil.copy2(BACKUP_PATH, MANIFEST_PATH)
        fail("Restored manifest from backup")
        sys.exit(1)

    # Check that the import is syntactically valid
    if export_name in updated_content and module_filename in updated_content:
        ok("Manifest validation passed")
    else:
        fail("Manifest validation failed — import may be missing")
        shutil.copy2(BACKUP_PATH, MANIFEST_PATH)
        fail("Restored manifest from backup")
        sys.exit(1)

    # ── Step 3: Rebuild ────────────────────────────────────────────────
    print("\n🔨 Rebuilding dist/compare.html...")
    if not run_build():
        fail("Build failed — restoring manifest from backup")
        shutil.copy2(BACKUP_PATH, MANIFEST_PATH)
        sys.exit(1)
    ok("Rebuilt dist/compare.html")

    # ── Summary ─────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    ok(f"Generated ES module: web/js/{module_filename}")
    if not import_exists or added_keys:
        ok("Updated manifest: web/js/trackOutlineManifest.js")
        if added_keys:
            ok(f"Added {len(added_keys)} entries to OUTLINES map:")
            for key in added_keys:
                print(f"     - {key}")
    ok("Rebuilt dist/compare.html")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()