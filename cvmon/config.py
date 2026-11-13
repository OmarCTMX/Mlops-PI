"""Carga y validación de la configuración. El hash de la configuración identifica cada evento."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent

SOURCE_TYPES = {"ipwebcam", "webcam", "video", "sequence"}
RULE_TYPES = {
    "low_confidence_share",
    "confidence_shift",
    "stream_stale",
    "inference_error_rate",
    "version_mismatch",
}


class ConfigError(ValueError):
    """Configuración inválida."""


def load_config(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.is_absolute() and not p.exists():
        p = ROOT / p
    with open(p, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    validate_config(cfg)
    return cfg


def validate_thresholds(lower: float, upper: float) -> None:
    """Regla R3: 0 <= inferior < superior <= 1."""
    if not isinstance(lower, (int, float)) or not isinstance(upper, (int, float)):
        raise ConfigError("Los umbrales deben ser numéricos")
    if not (0.0 <= lower < upper <= 1.0):
        raise ConfigError(
            f"Umbrales inválidos: se exige 0 <= inferior < superior <= 1 (inferior={lower}, superior={upper})"
        )


def validate_config(cfg: dict[str, Any]) -> None:
    if not isinstance(cfg, dict):
        raise ConfigError("La configuración debe ser un mapa YAML")
    for section in ("source", "sampling", "model", "thresholds", "capture", "alerts"):
        if section not in cfg:
            raise ConfigError(f"Falta la sección '{section}'")
    if cfg["source"].get("type") not in SOURCE_TYPES:
        raise ConfigError(f"source.type debe ser uno de {sorted(SOURCE_TYPES)}")
    validate_thresholds(cfg["thresholds"].get("lower"), cfg["thresholds"].get("upper"))
    if cfg["sampling"].get("sample_interval_s", -1) < 0:
        raise ConfigError("sampling.sample_interval_s debe ser >= 0 (0 = inferir todos los frames)")
    if cfg["sampling"].get("queue_size", 0) < 1:
        raise ConfigError("sampling.queue_size debe ser >= 1")
    ids = set()
    for rule in cfg["alerts"].get("rules", []):
        if rule.get("type") not in RULE_TYPES:
            raise ConfigError(f"Regla {rule.get('id')}: tipo desconocido {rule.get('type')}")
        if rule["id"] in ids:
            raise ConfigError(f"Regla duplicada: {rule['id']}")
        ids.add(rule["id"])
        for key in ("severity", "action"):
            if not rule.get(key):
                raise ConfigError(f"Regla {rule['id']}: falta '{key}'")


def config_hash(cfg: dict[str, Any]) -> str:
    """SHA-256 (16 hex) de la configuración canónica. Excluye los datos personales del proyecto."""
    clean = {k: v for k, v in cfg.items() if k != "project"}
    blob = json.dumps(clean, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def apply_overrides(cfg: dict[str, Any], overrides: list[str]) -> dict[str, Any]:
    """Aplica 'a.b.c=valor' (valor interpretado como YAML). Los overrides quedan en config_hash."""
    for item in overrides or []:
        if "=" not in item:
            raise ConfigError(f"Override inválido (se espera clave=valor): {item}")
        key, raw = item.split("=", 1)
        node = cfg
        parts = key.strip().split(".")
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        node[parts[-1]] = yaml.safe_load(raw)
    validate_config(cfg)
    return cfg


def resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p
