"""Manifest of protected (frozen) artifacts and its verification.

``FROZEN.sha256`` (repository root) lists, in ``sha256sum`` format, every versioned file whose
change would alter or misreport the frozen P7-P7c results: evaluation reports, checkpoints,
equity tables, the frozen evaluation scripts and the simulation core they ran on.
Verification is read-only. Regenerating the manifest is an explicit, documented action.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

MANIFEST = "FROZEN.sha256"
PROTECTED_GLOBS = (
    "docs/p7_artifacts/*",
    "docs/p7b_artifacts/*",
    "docs/p7c_artifacts/*",
    "docs/P7_REPORT.md",
    "docs/P7B_REPORT.md",
    "docs/P7C_REPORT.md",
    "artifacts/checkpoints/*",
    "artifacts/tables/*",
    "scripts/run_p7_evaluation.py",
    "scripts/p7b_final_eval.py",
    "scripts/p7c_common.py",
    "scripts/p7c_dev.py",
    "scripts/p7c_final.py",
    # simulation core the frozen evaluations ran on (reproducibility)
    "src/poker_lab/domain/*.py",
    "src/poker_lab/engine/*.py",
    "src/poker_lab/agents/*.py",
    "src/poker_lab/strategy/*.py",
    "src/poker_lab/strategy/data/*",
    "src/poker_lab/tournament/*.py",
    "src/poker_lab/training/*.py",
    "src/poker_lab/evaluation/*.py",
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def protected_files(root: Path) -> list[Path]:
    files: set[Path] = set()
    for pattern in PROTECTED_GLOBS:
        files.update(p for p in root.glob(pattern) if p.is_file() and "__pycache__" not in p.parts)
    return sorted(files)


def build_manifest(root: Path) -> str:
    return "".join(f"{sha256_file(p)}  {p.relative_to(root).as_posix()}\n" for p in protected_files(root))


@dataclass
class FrozenReport:
    checked: int = 0
    ok: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    unlisted: list[str] = field(default_factory=list)  # new protected-pattern files not in the manifest

    @property
    def passed(self) -> bool:
        return not (self.changed or self.missing)

    def as_dict(self) -> dict[str, object]:
        return {"passed": self.passed, "checked": self.checked, "changed": self.changed, "missing": self.missing,
                "unlisted": self.unlisted}


def parse_manifest(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        if line.strip():
            digest, rel = line.split(None, 1)
            out[rel.strip().lstrip("*")] = digest
    return out


def verify_manifest(root: Path, manifest_path: Path | None = None) -> FrozenReport:
    manifest_path = manifest_path or root / MANIFEST
    expected = parse_manifest(manifest_path.read_text(encoding="utf-8"))
    rep = FrozenReport()
    for rel, digest in sorted(expected.items()):
        p = root / rel
        rep.checked += 1
        if not p.is_file():
            rep.missing.append(rel)
        elif sha256_file(p) != digest:
            rep.changed.append(rel)
        else:
            rep.ok.append(rel)
    listed = set(expected)
    rep.unlisted = [p.relative_to(root).as_posix() for p in protected_files(root) if p.relative_to(root).as_posix() not in listed]
    return rep
