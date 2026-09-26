"""
Versions — named snapshots that survive closing the program (Section 13).

Each version is one JSON file in the versions folder:
    {"format": "sismolab-version", "name": ..., "saved_at": real UTC time,
     "state": <the same operational state as a structural export>}

The undo stack and other versions are not stored (Section 13 allows it).
Restoring goes through the topology-load validation, so an edited or damaged
version file is rejected instead of corrupting the scenario.
"""

from __future__ import annotations

import os
import re
import unicodedata
from datetime import datetime, timezone

from domain.models import format_time
from domain.storage import StateError, read_json_file, write_json_file

FORMAT_VERSION = "sismolab-version"
MAX_NAME_LENGTH = 60


class VersionStore:
    """Named versions kept as files in one folder."""

    def __init__(self, folder: str) -> None:
        self.folder = folder

    # --- Write ---

    def save(self, name: str, state: dict) -> dict:
        """Store `state` under a new unique name. Returns the version summary."""
        clean = " ".join(str(name).split())
        if not clean:
            raise ValueError("El nombre de la versión no puede estar vacío")
        if len(clean) > MAX_NAME_LENGTH:
            raise ValueError(f"El nombre admite máximo {MAX_NAME_LENGTH} caracteres")
        for version in self.list():
            if version["name"].casefold() == clean.casefold():
                raise ValueError(f"Ya existe una versión llamada '{version['name']}'")

        os.makedirs(self.folder, exist_ok=True)
        version_id = self._free_id(_slug(clean))
        data = {
            "format": FORMAT_VERSION,
            "name": clean,
            "saved_at": format_time(datetime.now(timezone.utc).replace(tzinfo=None)),
            "state": state,
        }
        write_json_file(self._path(version_id), data)
        return _summary(version_id, data)

    # --- Read ---

    def list(self) -> list[dict]:
        """Every version in the folder, oldest first. Damaged files are listed
        as invalid (with the reason) instead of hiding them or failing."""
        if not os.path.isdir(self.folder):
            return []
        versions = []
        for file_name in os.listdir(self.folder):
            if not file_name.endswith(".json"):
                continue
            version_id = file_name[:-len(".json")]
            try:
                summary = _summary(version_id, self._read(version_id))
            except StateError as exc:
                summary = {"id": version_id, "name": version_id, "valid": False,
                           "saved_at": "", "error": "; ".join(exc.problems)}
            # saved_at has second precision; the file time orders versions
            # saved within the same second.
            modified = os.stat(self._path(version_id)).st_mtime_ns
            versions.append((summary["saved_at"], modified, summary))
        versions.sort(key=lambda item: item[:2])
        return [summary for _, _, summary in versions]

    def load_state(self, version_id: str) -> tuple[str, dict]:
        """Return (name, stored state) of one version."""
        data = self._read(version_id)
        return data["name"], data["state"]

    # --- Helpers ---

    def _read(self, version_id: str) -> dict:
        if not re.fullmatch(r"[a-z0-9_-]+", version_id):
            raise StateError([f"Invalid version id {version_id!r}"])
        path = self._path(version_id)
        if not os.path.isfile(path):
            raise StateError([f"Version {version_id!r} does not exist"])
        data = read_json_file(path)
        if data.get("format") != FORMAT_VERSION:
            raise StateError([f"{version_id}.json is not a SismoLab version file"])
        if not isinstance(data.get("name"), str) or not isinstance(data.get("state"), dict):
            raise StateError([f"{version_id}.json needs a 'name' and a 'state' object"])
        return data

    def _path(self, version_id: str) -> str:
        return os.path.join(self.folder, version_id + ".json")

    def _free_id(self, base: str) -> str:
        """File names must not collide even when two names share a slug."""
        candidate, counter = base, 2
        while os.path.exists(self._path(candidate)):
            candidate, counter = f"{base}-{counter}", counter + 1
        return candidate


def _slug(name: str) -> str:
    """'Antes de la corrección' -> 'antes-de-la-correccion' (safe file name)."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")
    return slug or "version"


def _summary(version_id: str, data: dict) -> dict:
    """What the version list shows, read from the stored state."""
    state = data["state"]
    tree = state.get("active_tree")
    nodes = tree.get("nodes") if isinstance(tree, dict) else None
    archived = state.get("archived")
    return {
        "id": version_id,
        "name": data["name"],
        "valid": True,
        "saved_at": data.get("saved_at", ""),
        "clock": state.get("clock", ""),
        "mode": state.get("mode", "normal"),
        "active": len(nodes) if isinstance(nodes, list) else 0,
        "archived": len(archived) if isinstance(archived, list) else 0,
    }
