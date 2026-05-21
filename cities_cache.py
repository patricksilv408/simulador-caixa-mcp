"""
Cache estático de cidades por UF.
Gerado pelo populate_cache.py — não editar manualmente.
"""

import json
import os
from typing import Optional
from models import Cidade

_CACHE_FILE = os.path.join(os.path.dirname(__file__), "cities_cache.json")
_cache: dict[str, list[dict]] = {}


def _load():
    global _cache
    if not _cache:
        with open(_CACHE_FILE, encoding="utf-8") as f:
            _cache = json.load(f)


def get_cities(uf: str) -> list[Cidade]:
    _load()
    uf = uf.upper()
    return [Cidade(id=c["id"], nome=c["nome"], uf=uf) for c in _cache.get(uf, [])]


def find_city_id(uf: str, city_name: str) -> Optional[str]:
    """Busca o ID de uma cidade pelo nome (case-insensitive, sem acentos)."""
    _load()
    uf = uf.upper()
    name_norm = _normalize(city_name)
    for c in _cache.get(uf, []):
        if _normalize(c["nome"]) == name_norm:
            return c["id"]
    # Busca parcial se não encontrar exato
    for c in _cache.get(uf, []):
        if name_norm in _normalize(c["nome"]):
            return c["id"]
    return None


def _normalize(s: str) -> str:
    import unicodedata
    s = s.upper().strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s
