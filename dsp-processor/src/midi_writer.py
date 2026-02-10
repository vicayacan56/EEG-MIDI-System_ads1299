"""
midi_writer.py
--------------

Bloque 4 ~ MIDI Writer

Convierte una lista de NoteEvent (music_note.NoteEvent) en un
archivo MIDI estándar de 1 pista usando la librería `mido`.

- Soporta múltiples canales e instrumentos (program) según el NoteEvent.
- Usa un tempo fijo en BPM.
- Convierte tiempos en segundos -> ticks MIDI con resolución configurable.

Requiere:
    pip install mido
"""

from __future__ import annotations

from typing import List, Dict, Tuple


from music_note import NoteEvent

try:
    import mido
except ImportError as e:
    raise ImportError(
        "La librería 'mido' no está instalada. "
        "Instálala con:  pip install mido"
    ) from e


def _compute_ticks_per_second(
    bpm: float,
    ticks_per_beat: int,
) -> float:
    """
    Calcula cuántos ticks MIDI corresponden a 1 segundo de tiempo real.

    Fórmulas:
        - 1 beat dura: 60 / bpm segundos
        - ticks por beat = ticks_per_beat
        => ticks/seg = ticks_per_beat / (60 / bpm) = ticks_per_beat * bpm / 60
    """
    return ticks_per_beat * (bpm / 60.0)


def write_midi_from_notes(
    notes: List[NoteEvent],
    output_path: str,
    bpm: float = 120.0,
    ticks_per_beat: int = 480,
) -> None:
    """
    Escribe un archivo MIDI a partir de una lista de NoteEvent.

    Args
    ----
    notes : List[NoteEvent]
        Lista de eventos de nota (t_start, t_end en segundos, pitch, velocity, etc.).
    output_path : str
        Ruta del archivo .mid a crear.
    bpm : float
        Tempo en beats por minuto.
    ticks_per_beat : int
        Resolución temporal del MIDI (PPQ).

    Notas:
        - Si notes está vacía, se genera un MIDI con solo el tempo.
        - Se asume que t_start y t_end están en segundos y t_start >= 0.
    """
    # Ordenamos notas por tiempo de inicio
    notes = sorted(notes, key=lambda n: (n.t_start, n.t_end))

    mid = mido.MidiFile(ticks_per_beat=ticks_per_beat)
    track = mido.MidiTrack()
    mid.tracks.append(track)

    # Meta-mensaje de tempo
    # tempo = microsegundos por negra
    tempo_us_per_beat = mido.bpm2tempo(bpm)
    track.append(mido.MetaMessage("set_tempo", tempo=tempo_us_per_beat, time=0))

    if not notes:
        # No hay notas, solo escribimos el archivo con el tempo
        mid.save(output_path)
        return

    # Calcular ticks por segundo
    ticks_per_second = _compute_ticks_per_second(bpm, ticks_per_beat)

    # Ajustar tiempos para que la primera nota empiece en t=0
    t0 = min(n.t_start for n in notes)
    if t0 < 0:
        # Si hubiese tiempos negativos por algún bug, los desplazamos
        t0 = t0
    # Recalculamos todos los tiempos relativos
    # También podrías clamp a 0: max(0, n.t_start - t0), pero
    # en principio t_start ya es >=0 en tu pipeline.
    def _to_ticks(t: float) -> int:
        rel_t = t - t0
        if rel_t < 0:
            rel_t = 0.0
        return int(round(rel_t * ticks_per_second))

    # 1) Construir lista de eventos (note_on / note_off) con tiempos absolutos en ticks
    events: List[Tuple[int, str, int, int, int]] = []
    # (tick_abs, tipo, pitch, velocity, channel)

    for n in notes:
        start_tick = _to_ticks(n.t_start)
        end_tick = _to_ticks(n.t_end)

        start_tick = max(0, start_tick)
        end_tick = max(start_tick + 1, end_tick)  # asegurar duración mínima

        # note_on
        events.append(
            (start_tick, "on", n.pitch_midi, n.velocity, n.channel)
        )
        # note_off
        events.append(
            (end_tick, "off", n.pitch_midi, 0, n.channel)
        )

    # Ordenar eventos por tiempo; en caso de empate, note_off antes de note_on
    events.sort(key=lambda e: (e[0], 0 if e[1] == "off" else 1))

    # 2) Detectar programas por canal (primer program que aparezca)
    #    Si diferentes notas tienen diferentes programs en el mismo canal,
    #    tomamos el del primer NoteEvent.
    channel_program: Dict[int, int] = {}
    for n in notes:
        if n.channel not in channel_program:
            channel_program[n.channel] = n.program

    # Insertamos mensajes de cambio de programa al principio (time=0)
    for ch, prog in channel_program.items():
        track.append(
            mido.Message(
                "program_change",
                program=prog,
                channel=ch,
                time=0,
            )
        )

    # 3) Convertir tiempos absolutos en delta times e insertar en la pista
    last_tick = 0
    for tick_abs, ev_type, pitch, velocity, channel in events:
        delta = tick_abs - last_tick
        last_tick = tick_abs

        if ev_type == "on":
            msg = mido.Message(
                "note_on",
                note=pitch,
                velocity=velocity,
                channel=channel,
                time=delta,
            )
        else:
            msg = mido.Message(
                "note_off",
                note=pitch,
                velocity=velocity,
                channel=channel,
                time=delta,
            )

        track.append(msg)

    # Guardar archivo
    mid.save(output_path)


# Prueba rápida
if __name__ == "__main__":
    # Pequeño test con dos notas
    n1 = NoteEvent(t_start=0.0, t_end=0.5, pitch_midi=60, velocity=100, channel=0, program=0)
    n2 = NoteEvent(t_start=0.5, t_end=1.0, pitch_midi=64, velocity=100, channel=0, program=0)

    write_midi_from_notes([n1, n2], "test_output.mid", bpm=120.0, ticks_per_beat=480)
    print("MIDI de prueba escrito en test_output.mid")
