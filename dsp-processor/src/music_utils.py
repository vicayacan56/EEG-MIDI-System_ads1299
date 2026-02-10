"""
music_utils.py
--------------

Utilidades musicales generales para conversión nota<->MIDI, escalas, etc.
"""

from __future__ import annotations


# Mapa de notas en semitonos relativos a C
NOTE_OFFSETS = {
    "C": 0,
    "C#": 1, "Db": 1,
    "D": 2,
    "D#": 3, "Eb": 3,
    "E": 4,
    "F": 5,
    "F#": 6, "Gb": 6,
    "G": 7,
    "G#": 8, "Ab": 8,
    "A": 9,
    "A#": 10, "Bb": 10,
    "B": 11,
}


def note_name_to_midi(name: str) -> int:
    """
    Convierte una nota textual tipo "C4", "G#3", "Bb5" en un número MIDI.

    Robustez añadida:
      - admite mayúsculas/minúsculas ("bb3", "g#4", "c4")
      - admite accidental unicode '♭' y '♯'
      - admite entradas tipo "BB3" (se interpreta como "Bb3", por compatibilidad)
    """
    if name is None:
        raise ValueError("Nota inválida: None")

    s = name.strip()
    if len(s) < 2:
        raise ValueError(f"Formato inválido de nota: '{name}'")

    # Normalizar símbolos unicode comunes
    s = s.replace("♭", "b").replace("♯", "#")

    # --------------------------
    # Parseo: letra + accidental (opcional) + octava (entera)
    # --------------------------
    # 1) letra
    letter = s[0].upper()
    if letter not in ("A", "B", "C", "D", "E", "F", "G"):
        raise ValueError(f"Letra de nota inválida en '{name}'")

    # 2) accidental opcional
    accidental = ""
    idx = 1

    if idx < len(s) and s[idx] in ("#", "b", "B"):
        acc_char = s[idx]
        # Compatibilidad: si alguien puso "BB3", lo tratamos como "Bb3"
        # (es decir, 'B' como bemol), ya que el segundo 'B' suele ser un typo de casing.
        if acc_char == "#":
            accidental = "#"
        else:
            accidental = "b"
        idx += 1

        # Caso especial: si el accidental fue 'B' (mayúscula) y el siguiente char también es 'B'
        # (ej: "BB3"), ignoramos el segundo 'B' accidental por compatibilidad.
        if idx < len(s) and s[idx] == "B" and accidental == "b":
            # "BB3" -> interpretamos como "Bb3" y avanzamos una posición
            idx += 1

    # 3) octava: lo que queda
    octave_part = s[idx:]
    if octave_part == "":
        raise ValueError(f"Falta la octava en '{name}'")

    if not octave_part.lstrip("-").isdigit():
        raise ValueError(f"Octava inválida en '{name}'")

    octave = int(octave_part)

    # 4) nota normalizada para el diccionario
    normalized_note = letter + accidental

    # Nota: nuestro NOTE_OFFSETS usa "Bb" / "Db" / "Eb" / "Gb" / "Ab"
    # por lo que para bemoles hay que capitalizar la letra y usar 'b' minúscula.
    if accidental == "b":
        normalized_note = letter + "b"

    if normalized_note not in NOTE_OFFSETS:
        raise ValueError(f"Nota no reconocida: '{normalized_note}' (entrada: '{name}')")

    midi = 12 + NOTE_OFFSETS[normalized_note] + 12 * octave

    if not (0 <= midi <= 127):
        raise ValueError(f"MIDI fuera de rango: {midi} (entrada: '{name}')")

    return int(midi)


def midi_to_note_name(midi: int) -> str:
    """
    Convierte un número MIDI en un nombre de nota tipo 'C4', 'F#3', etc.
    """
    if not (0 <= midi <= 127):
        raise ValueError("MIDI fuera de rango (0–127).")

    octave = (midi // 12) - 1
    semitone = midi % 12

    # elegimos la representación en sostenidos por simplicidad
    for note, offset in NOTE_OFFSETS.items():
        if offset == semitone and len(note) <= 2:  # evitamos duplicados (C# y Db)
            return f"{note}{octave}"

    raise RuntimeError("Error interno al convertir MIDI a nota.")


# Prueba rápida
if __name__ == "__main__":
    tests = [
        "C4", "G#3", "Bb5", "F#2", "A4", "C0", "C8",
        "bb3", "BB3", "db4", "Eb4", "g#4", "c#4", "c4",
        "F♯3", "B♭3"
    ]
    for t in tests:
        midi = note_name_to_midi(t)
        name_back = midi_to_note_name(midi)
        print(f"{t:6s} -> {midi:3d} -> {name_back}")
