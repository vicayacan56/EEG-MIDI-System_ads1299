# src/scale_registry.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from music_segment import ScaleConfig
from music_utils import note_name_to_midi


# ---------------------------------------------------------------------
# Catálogo de escalas por familia
# ---------------------------------------------------------------------

SCALE_FAMILIES: Dict[str, Dict[str, List[int]]] = {
    "Diatonic": {
        "Major (Ionian)": [0, 2, 4, 5, 7, 9, 11],
        "Natural Minor (Aeolian)": [0, 2, 3, 5, 7, 8, 10],
    },
    "Minor Variants": {
        "Harmonic Minor": [0, 2, 3, 5, 7, 8, 11],
        "Melodic Minor (Asc)": [0, 2, 3, 5, 7, 9, 11],
    },
    "Modes": {
        "Ionian": [0, 2, 4, 5, 7, 9, 11],
        "Dorian": [0, 2, 3, 5, 7, 9, 10],
        "Phrygian": [0, 1, 3, 5, 7, 8, 10],
        "Lydian": [0, 2, 4, 6, 7, 9, 11],
        "Mixolydian": [0, 2, 4, 5, 7, 9, 10],
        "Aeolian": [0, 2, 3, 5, 7, 8, 10],
        "Locrian": [0, 1, 3, 5, 6, 8, 10],
    },
    "Pentatonic": {
        "Pentatonic Major": [0, 2, 4, 7, 9],
        "Pentatonic Minor": [0, 3, 5, 7, 10],
    },
    "Blues": {
        "Blues Minor": [0, 3, 5, 6, 7, 10],
    },
    "Symmetric": {
        "Chromatic": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
        "Whole Tone": [0, 2, 4, 6, 8, 10],
        "Octatonic (Half-Whole)": [0, 1, 3, 4, 6, 7, 9, 10],
        "Octatonic (Whole-Half)": [0, 2, 3, 5, 6, 8, 9, 11],
    },
    "World": {
        "Spanish Gypsy (Phrygian Dominant)": [0, 1, 4, 5, 7, 8, 10],
        "Double Harmonic Major (Balkan/Byzantine)": [0, 1, 4, 5, 7, 8, 11],
        "Hungarian Minor (Balkan/Gypsy)": [0, 2, 3, 6, 7, 8, 11],
        "Ukrainian Dorian": [0, 2, 3, 6, 7, 9, 10],
        "Hijaz": [0, 1, 4, 5, 7, 8, 10],
        "Hijazkar": [0, 1, 4, 5, 7, 8, 11],
        "Hirajoshi (Japan)": [0, 2, 3, 7, 8],
        "In Sen (Japan)": [0, 1, 5, 7, 10],
        "Bhairav (India, simplified)": [0, 1, 4, 5, 7, 8, 11],
    },
    "Ambient": {
        "Suspended (no 3rd)": [0, 2, 5, 7, 9],
    },
}


# ---------------------------------------------------------------------
# API pública (para CLI/GUI)
# ---------------------------------------------------------------------

def list_families() -> List[str]:
    return sorted(SCALE_FAMILIES.keys())


def list_scales(family: str) -> List[str]:
    if family not in SCALE_FAMILIES:
        raise ValueError(f"Familia no reconocida: '{family}'. Opciones: {list_families()}")
    return sorted(SCALE_FAMILIES[family].keys())


def build_scale_config(family: str, scale_name: str, root_note: str) -> ScaleConfig:
    """
    Construye ScaleConfig a partir de (familia, nombre de escala, root_note).
    root_note admite por ejemplo: "C4", "D#3", "Bb3", "F#4"
    """
    if family not in SCALE_FAMILIES:
        raise ValueError(f"Familia no reconocida: '{family}'. Opciones: {list_families()}")

    scales = SCALE_FAMILIES[family]
    if scale_name not in scales:
        raise ValueError(
            f"Escala no reconocida en '{family}': '{scale_name}'. "
            f"Opciones: {list_scales(family)}"
        )

    intervals = scales[scale_name]
    root_midi = note_name_to_midi(root_note)

    return ScaleConfig(
        root_midi=int(root_midi),
        name=f"{root_note}_{scale_name}",
        intervals=intervals,
    )
