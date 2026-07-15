import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from core.config import RESOURCE_DIR, USER_DATA_DIR, logger


SUPPORTED_PET_SCHEMA = 1


@dataclass(frozen=True)
class PetPack:
    pet_id: str
    name: str
    root: Path
    sprite_path: Path
    manifest: Dict

    @property
    def motion_presets(self) -> Dict:
        return self.manifest.get("motion_presets", {})

    def motion_for(self, state: str) -> Dict:
        fallback = self.motion_presets.get("idle", {})
        return dict(fallback, **self.motion_presets.get(state, {}))

    def animation_for(self, name: str) -> Optional[Dict]:
        spec = self.manifest.get("animations", {}).get(name)
        if not isinstance(spec, dict):
            return None

        frame_names = spec.get("frames", [])
        durations = spec.get("durations_ms", [])
        if not isinstance(frame_names, list) or not frame_names:
            return None
        if not isinstance(durations, list) or len(durations) != len(frame_names):
            return None

        frame_paths = []
        for frame_name in frame_names:
            frame_path = _resolve_inside(self.root, str(frame_name))
            if not frame_path or not frame_path.is_file():
                return None
            frame_paths.append(frame_path)

        try:
            normalized_durations = [max(35, int(value)) for value in durations]
            reference_height = max(1, int(spec.get("reference_height", 198)))
            baseline = max(1, int(spec.get("baseline", 203)))
            idle_frame_indices = {
                int(value)
                for value in spec.get("idle_frame_indices", [])
                if 0 <= int(value) < len(frame_paths)
            }
        except (TypeError, ValueError):
            return None

        return {
            "frames": frame_paths,
            "durations_ms": normalized_durations,
            "reference_height": reference_height,
            "baseline": baseline,
            "idle_frame_indices": idle_frame_indices,
        }


def pet_search_roots() -> List[Path]:
    # User packs take precedence so an installed pack can override a bundled pack.
    return [USER_DATA_DIR / "pets", RESOURCE_DIR / "assets" / "pets"]


def _resolve_inside(root: Path, relative_path: str) -> Optional[Path]:
    try:
        root = root.resolve()
        candidate = (root / relative_path).resolve()
        candidate.relative_to(root)
        return candidate
    except (OSError, ValueError):
        return None


def _load_pack(manifest_path: Path) -> Optional[PetPack]:
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        if data.get("schema_version") != SUPPORTED_PET_SCHEMA:
            raise ValueError("unsupported schema version")

        pet_id = str(data.get("id", "")).strip()
        name = str(data.get("name", "")).strip()
        sprite_name = str(data.get("sprite", "")).strip()
        if not pet_id or not name or not sprite_name:
            raise ValueError("id, name and sprite are required")
        if not pet_id.replace("-", "").replace("_", "").isalnum():
            raise ValueError("invalid pet id")

        sprite_path = _resolve_inside(manifest_path.parent, sprite_name)
        if not sprite_path or not sprite_path.is_file():
            raise ValueError("sprite file is missing or outside the pack")

        return PetPack(
            pet_id=pet_id,
            name=name,
            root=manifest_path.parent,
            sprite_path=sprite_path,
            manifest=data,
        )
    except Exception as exc:
        logger.warning("忽略无效宠物包 %s: %s", manifest_path, exc)
        return None


def discover_pet_packs() -> List[PetPack]:
    packs = {}
    for root in pet_search_roots():
        if not root.exists():
            continue
        for manifest_path in sorted(root.glob("*/pet.json")):
            pack = _load_pack(manifest_path)
            if pack and pack.pet_id not in packs:
                packs[pack.pet_id] = pack
    return sorted(packs.values(), key=lambda item: item.name.casefold())


def get_pet_pack(pet_id: str) -> Optional[PetPack]:
    packs = discover_pet_packs()
    for pack in packs:
        if pack.pet_id == pet_id:
            return pack
    return packs[0] if packs else None
