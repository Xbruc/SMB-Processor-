from __future__ import annotations

from collections import Counter
from pathlib import Path


def summarize_cli(path: Path) -> dict[str, int]:
    counts: Counter[str] = Counter()
    if not path.is_file():
        return {}
    labels = {
        ("5", "4", "4"): "oceano_nivel",
        ("4", "5", "5"): "rio_vazao",
        ("4", "4", "4"): "livre",
        ("2", "2", "2"): "parede",
    }
    for line in path.read_text(encoding="ascii").splitlines():
        cols = line.split()
        if len(cols) >= 3:
            counts[labels.get(tuple(cols[:3]), "outro")] += 1
    return dict(counts)


def validate_prn(path: Path) -> list[str]:
    errors = []
    if not path.is_file():
        return ["Arquivo PRN não encontrado."]
    lines = path.read_text(encoding="ascii").splitlines()
    if len(lines) < 3:
        return ["PRN sem dados suficientes."]
    if not lines[0].startswith("T "):
        errors.append("O cabeçalho não começa com T.")
    columns = len(lines[0].split())
    if len(lines[1].split()) != columns:
        errors.append("Cabeçalho e unidades têm números diferentes de colunas.")
    previous = None
    for number, line in enumerate(lines[2:], 3):
        parts = line.split()
        if len(parts) != columns:
            errors.append(f"Linha {number} possui {len(parts)} colunas.")
            break
        current = float(parts[0])
        if previous is not None and current <= previous:
            errors.append(f"Tempo não crescente na linha {number}.")
            break
        previous = current
    return errors
