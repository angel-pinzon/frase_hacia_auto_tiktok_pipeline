"""Carga de configuracion y rutas compartidas entre los modulos del pipeline."""

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
ENV_PATH = ROOT / ".env"


def load_env():
    """Vuelca las claves de .env en el entorno sin pisar las ya definidas."""
    if not ENV_PATH.exists():
        return
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def deep_merge(base, extra):
    """Mezcla recursiva: 'extra' pisa a 'base' sin borrar el resto de claves."""
    merged = dict(base)
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(meta=None):
    """Carga config.json y le aplica los 'overrides' del video en curso."""
    with open(CONFIG_PATH, encoding="utf-8") as fh:
        config = json.load(fh)

    if meta is None:
        meta_path = (ROOT / config.get("output_dir", "output")
                     / config["active_character"] / "script_meta.json")
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))

    overrides = (meta or {}).get("overrides")
    if overrides:
        print(f"Ajustes propios de este video: {json.dumps(overrides, ensure_ascii=False)}")
        config = deep_merge(config, overrides)
    return config


def active_character(config):
    key = config["active_character"]
    if key not in config["characters"]:
        raise KeyError(f"El personaje activo '{key}' no existe en config.json")
    return config["characters"][key]


def output_dir(config):
    """Cada personaje escribe en su carpeta para no pisarse entre si."""
    path = ROOT / config.get("output_dir", "output") / config["active_character"]
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve(path_str):
    path = Path(path_str)
    return path if path.is_absolute() else ROOT / path
