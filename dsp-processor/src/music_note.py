"""
music_note.py
-------------

Bloque 3 – Note Generator

Convierte:
  - un MusicSegment,
  - una lista de Bars (acordes + note_positions),

en una lista de eventos de nota de alto nivel (NoteEvent), listos
para ser convertidos a MIDI en el siguiente bloque.

Reglas implementadas (inspiradas en el paper + tus requisitos):

  - Cada '1' en note_positions es un note-on.
  - La nota dura hasta el siguiente note-on o el final del bar.
  - Los pitch se seleccionan a partir de:
        * chord tones (notas del acorde),
        * non-chord tones (otras notas de la escala),
    usando:
        * chord tones en downbeats (primer slot de cada beat),
        * non-chord tones en upbeats cuando sea posible.
  - El salto entre notas se limita a 7 semitonos (se elige el
    candidato más cercano a la nota anterior).
  - El registro se ajusta usando segment.register_hint.
  - El velocity depende de la posición rítmica (downbeat/upbeat)
    y puede escalarse suavemente por la energía (RMS).

NOTA: Este módulo NO escribe archivos MIDI, solo define NoteEvent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Optional

import numpy as np

from music_segment import MusicSegment, ScaleConfig
from music_bar import Bar
from music_segment import RhythmCadence


@dataclass
class NoteEvent:
    """
    Evento de nota de alto nivel.

    Atributos:
        t_start: tiempo absoluto de inicio (segundos).
        t_end: tiempo absoluto de final (segundos).
        pitch_midi: número de nota MIDI (0..127).
        velocity: intensidad (1..127).
        channel: canal MIDI (0..15).
        program: instrumento/timbre (0..127, p.ej. 0=piano).
    """
    t_start: float
    t_end: float
    pitch_midi: int
    velocity: int
    channel: int = 0
    program: int = 0  # piano por defecto


class NoteGenerator:
    """
    Generador de notas a partir de Bars.

    Uso típico:
        gen = NoteGenerator()
        notes = gen.generate_notes_for_segment(music_segment, bars)

    Parámetros de diseño:
        - max_interval_semitones: salto máximo permitido entre notas.
        - base_velocity_downbeat / beat / offbeat: niveles básicos.
        - velocity_rms_scaling: si True, escala la dinámica global por RMS.
    """

    def __init__(
        self,
        beats_per_bar: int = 4,
        slots_per_beat: int = 4,
        max_interval_semitones: int = 12,
        base_velocity_downbeat: int = 105,
        base_velocity_beat: int = 90,
        base_velocity_offbeat: int = 75,
        velocity_rms_scaling: bool = True,
        min_velocity: int = 30,
        max_velocity: int = 120,
        default_channel: int = 0,
        default_program: int = 0,
    ) -> None:
        self.beats_per_bar = int(beats_per_bar)
        self.slots_per_beat = int(slots_per_beat)
        self.n_slots = self.beats_per_bar * self.slots_per_beat

        self.max_interval = int(max_interval_semitones)
        self.base_velocity_downbeat = int(base_velocity_downbeat)
        self.base_velocity_beat = int(base_velocity_beat)
        self.base_velocity_offbeat = int(base_velocity_offbeat)
        self.velocity_rms_scaling = bool(velocity_rms_scaling)
        self.min_velocity = int(min_velocity)
        self.max_velocity = int(max_velocity)
        self.default_channel = int(default_channel)
        self.default_program = int(default_program)

    # ------------------------------------------------------------------
    # Utilidades de pitch
    # ------------------------------------------------------------------
    def _compute_register_center(self, segment: MusicSegment) -> int:
        """
        Calcula una nota MIDI "centro" de registro para el segmento, a partir de:
          - main_note_midi,
          - register_hint en [0,1], que desplaza hacia grave/agudo.

        Implementación simple:
            center = main_note_midi + (register_hint - 0.5) * 12
        """
        base = segment.main_note_midi
        offset = (segment.register_hint - 0.5) * 12.0
        center = int(round(base + offset))
        # clamp a un rango aceptable
        center = max(36, min(96, center))  # C2..C7 aprox.
        return center

    def _build_scale_pitches_around(
        self,
        scale: ScaleConfig,
        center_pitch: int,
        radius_semitones: int = 12,
    ) -> List[int]:
        """
        Construye una lista de notas de la escala en un rango
        [center_pitch-radius, center_pitch+radius].
        """
        pitches: List[int] = []
        low = center_pitch - radius_semitones
        high = center_pitch + radius_semitones

        # Recorremos varias octavas alrededor
        for midi in range(low, high + 1):
            if scale.contains(midi):
                pitches.append(midi)
        return pitches

    def _split_chord_nonchord(
        self,
        scale_pitches: Sequence[int],
        chord_pitches: Sequence[int],
    ) -> (tuple[int, List[int]]):
        """
        Separa scale_pitches en dos listas:
          - chord_tones: pertenecen al acorde (misma clase de pitch mod 12).
          - non_chord_tones: resto de la escala.
        """
        chord_classes = {(p % 12) for p in chord_pitches}
        chord_tones = []
        non_chord_tones = []

        for p in scale_pitches:
            if (p % 12) in chord_classes:
                chord_tones.append(p)
            else:
                non_chord_tones.append(p)

        # Seguridad: si no hay chord_tones, usamos chord_pitches directamente
        if not chord_tones:
            chord_tones = list(chord_pitches)

        return chord_tones, non_chord_tones

    def _compute_eeg_tension_from_features(self, segment: MusicSegment) -> float:
        """
        Calcula un escalar de 'tensión' EEG en [0,1] a partir de
        bandpower_rel["alpha"] y bandpower_rel["beta"].

        - alpha alto, beta bajo  -> tensión baja (≈0).
        - beta alto, alpha baja  -> tensión alta (≈1).
        - valores raros -> 0.5 (neutro).
        """
        feats = segment.features or {}
        band_rel = feats.get("bandpower_rel", {}) or {}

        alpha_rel = float(band_rel.get("alpha", 0.0))
        beta_rel  = float(band_rel.get("beta", 0.0))

        total = alpha_rel + beta_rel
        if total <= 0:
            return 0.5  # sin info → neutro

        # proporción de beta sobre alpha+beta
        tension = beta_rel / total   # 0 → todo alfa, 1 → todo beta
        # clamp por si acaso
        tension = max(0.0, min(1.0, tension))
        return tension

    def _choose_pitch_candidate(
        self,
        chord_tones: Sequence[int],
        non_chord_tones: Sequence[int],
        slot_idx: int,
        prev_pitch: Optional[int],
        segment: MusicSegment,
    ) -> int:
        """
        Elige un pitch candidato para un slot concreto, combinando:
        - reglas musicales (acorde vs nota de paso, downbeat/upbeat),
        - continuidad melódica (cerca de prev_pitch),
        - modulación por EEG (alpha/beta) para subir/bajar el registro.

        La selección EEG no rompe la escala ni el acorde.
        """
        # 1) decidir si estamos en downbeat o no
        is_downbeat = (slot_idx % self.slots_per_beat == 0)

        # 2) determinar el conjunto de candidatos (igual que antes)
        if is_downbeat:
            candidates = list(chord_tones)
        else:
            if non_chord_tones:
                candidates = list(non_chord_tones)
            else:
                candidates = list(chord_tones)

        if not candidates:
            return int(segment.main_note_midi)

        # 3) si no hay nota previa, usamos el centro de registro y la tensión EEG
        center = self._compute_register_center(segment)
        tension = self._compute_eeg_tension_from_features(segment)
        # desplazamiento máximo de ±7 semitonos respecto al centro
        pitch_target = center + (tension - 0.5) * 14.0

        if prev_pitch is None:
            # primera nota: equilibrio entre centro y objetivo EEG
            # coste = combinación de distancia al centro y al target EEG
            w_center = 0.5
            w_eeg = 0.5

            def cost_first(p: int) -> float:
                return (
                    w_center * abs(p - center)
                    + w_eeg * abs(p - pitch_target)
                )

            best = min(candidates, key=cost_first)
            return int(best)

        # 4) si hay nota previa, combinamos:
        #    - suavidad melódica (cerca de prev_pitch)
        #    - empuje EEG hacia pitch_target
        w_melodic = 0.7
        w_eeg = 0.3

        def cost(p: int) -> float:
            return (
                w_melodic * abs(p - prev_pitch)
                + w_eeg * abs(p - pitch_target)
            )

        best = min(candidates, key=cost)
        return int(best)

    def _select_chord_voices(
        self,
        chord_tones: Sequence[int],
        center_pitch: int,
        max_voices: int = 3,
    ) -> list[int]:
        """
        Selecciona un conjunto de voces del acorde alrededor de center_pitch.

        - Ordena chord_tones por proximidad a center_pitch.
        - Elige hasta max_voices tonos.
        - Devuelve las voces ordenadas de grave a agudo.
        """
        if not chord_tones:
            return []

        # Ordenar por proximidad al centro
        sorted_by_center = sorted(chord_tones, key=lambda p: abs(p - center_pitch))
        voices = sorted_by_center[:max_voices]
        voices.sort()
        return voices


    def _apply_interval_constraint(
        self,
        candidate: int,
        prev_pitch: Optional[int],
        segment: MusicSegment,
    ) -> int:
        """
        Aplica el límite de salto máximo (en semitonos) entre notas.
        Si el candidato está a más de max_interval, se intenta ajustarlo
        usando octavas (±12). Si aun así no se logra, se fuerza al
        centro de registro del segmento.
        """
        if prev_pitch is None:
            return int(candidate)

        diff = candidate - prev_pitch
        max_int = self.max_interval

        # Intentar traer el candidato cerca desplazando octavas
        # mientras el salto supere el máximo.
        while diff > max_int:
            candidate -= 12
            diff = candidate - prev_pitch
        while diff < -max_int:
            candidate += 12
            diff = candidate - prev_pitch

        if abs(candidate - prev_pitch) > max_int:
            # si aún así no se controla el salto, caemos al centro
            candidate = self._compute_register_center(segment)

        # clamp MIDI
        candidate = max(0, min(127, candidate))
        return int(candidate)

    # ------------------------------------------------------------------
    # Utilidades de velocity
    # ------------------------------------------------------------------
    def _base_velocity_for_slot(self, slot_idx: int) -> int:
        """
        Determina el velocity base según la posición rítmica:
          - Downbeat (primer slot de cada compás) -> más fuerte.
          - Otros beats (primer slot de cada beat) -> intermedio.
          - Offbeats -> más flojo.
        """
        # primer slot de todo el compás
        if slot_idx == 0:
            return self.base_velocity_downbeat

        # primer slot de cada beat (pero no el primero del compás)
        if (slot_idx % self.slots_per_beat) == 0:
            return self.base_velocity_beat

        # resto
        return self.base_velocity_offbeat

    def _rms_scaling_factor(self, segment: MusicSegment) -> float:
        """
        Calcula un factor de escala [0.8..1.2] aproximadamente,
        a partir de segment.features["rms"].

        Si no hay rms, devuelve 1.0.
        """
        if not self.velocity_rms_scaling:
            return 1.0

        rms = float(segment.features.get("rms", 0.0))
        if rms <= 0:
            return 1.0

        # mapeo logarítmico suave
        # valores típicos de EEG (~uV) -> factores cerca de 1
        val = np.log10(rms + 1e-20)  # valor negative
        # Normalizamos a un rango arbitrario y saturamos
        # Esto es muy heurístico; se puede ajustar con datos reales.
        factor = 1.0 + 0.2 * np.tanh(val + 6.0)  # desplaza el rango
        return float(factor)

    def _dynamic_octave_shift(
        self,
        bar,
        slot_idx: int,
        high_thresh: float = 0.8,
        low_thresh: float = 0.2,
    ) -> int:
        """
        Devuelve un desplazamiento de octava (en semitonos) para un slot dado,
        en función de la amplitud relativa en ese slot.

        - Si la amplitud relativa > high_thresh -> +12 semitonos.
        - Si la amplitud relativa < low_thresh  -> -12 semitonos.
        - Si no, 0.
        """
        amps = getattr(bar, "amplitude_slots", None)
        if amps is None or len(amps) <= slot_idx:
            return 0

        amps = np.asarray(amps, dtype=float)
        if amps.size == 0:
            return 0

        a = float(amps[slot_idx])
        a_max = float(np.max(amps))
        if a_max <= 0:
            return 0

        rel = a / a_max  # 0..1

        if rel > high_thresh:
            return +12
        elif rel < low_thresh:
            return -12
        return 0
    # ------------------------------------------------------------------
    # Interfaz principal
    # ------------------------------------------------------------------
    def generate_notes_for_segment(
        self,
        segment: MusicSegment,
        bars: Sequence[Bar],
        channel: Optional[int] = None,
        program: Optional[int] = None,
    ) -> List[NoteEvent]:
        """
        Genera una lista de NoteEvent para un MusicSegment a partir
        de su secuencia de Bars.

        Args
        ----
        segment : MusicSegment
            Segmento musical que define escala, main_note, register_hint, etc.
        bars : Sequence[Bar]
            Lista de compases (chord + note_positions).
        channel : Optional[int]
            Canal MIDI para las notas (por defecto default_channel).
        program : Optional[int]
            Programa/instrumento MIDI (por defecto default_program).

        Returns
        -------
        List[NoteEvent]
        """
        if channel is None:
            channel = self.default_channel
        if program is None:
            program = self.default_program

        notes: List[NoteEvent] = []
        prev_pitch: Optional[int] = None

        scale = segment.scale
        center_pitch = self._compute_register_center(segment)
        rms_factor = self._rms_scaling_factor(segment)

        for bar in bars:
            n_slots = len(bar.note_positions)
            if n_slots != self.n_slots:
                # si difiere, recalculamos derivando slots_per_beat
                # (para ahora asumimos que coincide)
                raise ValueError(
                    f"Bar con n_slots={n_slots}, pero NoteGenerator espera {self.n_slots}"
                )

            bar_duration = bar.t_end - bar.t_start
            if bar_duration <= 0:
                continue

            slot_duration = bar_duration / n_slots

            # Precomputar pitches base para este bar (escala alrededor del centro)
            scale_pitches = self._build_scale_pitches_around(
                scale=scale,
                center_pitch=center_pitch,
                radius_semitones=12,
            )
            chord_tones, non_chord_tones = self._split_chord_nonchord(
                scale_pitches=scale_pitches,
                chord_pitches=bar.chord_pitches,
            )
            chord_voices = self._select_chord_voices(
                chord_tones=chord_tones,
                center_pitch=center_pitch,
                max_voices=3,
            )
    

            # Recorremos slots, cada '1' es un note-on
            for slot_idx, is_on in enumerate(bar.note_positions):
                if not is_on:
                    continue

                # t_start de la nota
                t_start = bar.t_start + slot_idx * slot_duration

                # buscar siguiente note-on o final de bar
                next_on_idx = None
                for j in range(slot_idx + 1, n_slots):
                    if bar.note_positions[j] == 1:
                        next_on_idx = j
                        break

                if next_on_idx is None:
                    t_end = bar.t_end
                else:
                    t_end = bar.t_start + next_on_idx * slot_duration

                if t_end <= t_start:
                    continue  # por seguridad numérica

                # 1) elegir pitch candidato
                candidate_pitch = self._choose_pitch_candidate(
                    chord_tones=chord_tones,
                    non_chord_tones=non_chord_tones,
                    slot_idx=slot_idx,
                    prev_pitch=prev_pitch,
                    segment=segment,
                )
                 # 2) aplicar un posible salto de octava dinámico
                octave_shift = self._dynamic_octave_shift(bar, slot_idx)
                candidate_pitch += octave_shift

                # 3) aplicar límite de salto
                pitch = self._apply_interval_constraint(
                    candidate=candidate_pitch,
                    prev_pitch=prev_pitch,
                    segment=segment,
                )

                prev_pitch = pitch

                # 3) velocity
                base_vel = self._base_velocity_for_slot(slot_idx)
                vel = int(round(base_vel * rms_factor))
                vel = max(self.min_velocity, min(self.max_velocity, vel))

                 # ----- CASO ESPECIAL: DOWNBEAT DEL COMPÁS (SLOT 0) -> ACORDE COMPLETO -----
                if slot_idx == 0 and chord_voices:
                    # Hacemos sonar el acorde elegido para ese bar
                    # con el mismo rango de tiempo [t_start, t_end]
                    # y canales/programa del segmento.
                    for voice_idx, voice_pitch in enumerate(chord_voices):
                        # Atenuar ligeramente las voces superiores
                        factor_voice = 1.0 - 0.1 * voice_idx
                        vel_voice = int(round(vel * factor_voice))
                        vel_voice = max(self.min_velocity, min(self.max_velocity, vel_voice))

                        notes.append(
                            NoteEvent(
                                t_start=float(t_start),
                                t_end=float(t_end),
                                pitch_midi=int(voice_pitch),
                                velocity=int(vel_voice),
                                channel=channel,
                                program=program,
                            )
                        )

                    # Para la línea melódica, consideramos que la última voz (más aguda)
                    # es la "melody lead" desde la que continuaremos.
                    prev_pitch = chord_voices[-1]
                    continue

                note = NoteEvent(
                    t_start=float(t_start),
                    t_end=float(t_end),
                    pitch_midi=int(pitch),
                    velocity=int(vel),
                    channel=channel,
                    program=program,
                )
                notes.append(note)

        # Ordenar por tiempo por si acaso
        notes.sort(key=lambda n: n.t_start)
        return notes


# Prueba rápida (muy simplificada)
if __name__ == "__main__":
    from eeg_segmenter import Segment
    from music_segment import ScaleConfig, MAJOR_INTERVALS
    from music_bar import Bar

    # Segmento ficticio 4 s
    seg = Segment(start_idx=0, end_idx=1000, t_start=0.0, t_end=4.0)
    feats = {"rms": 5e-6}
    scale = ScaleConfig(root_midi=60, name="C_major", intervals=MAJOR_INTERVALS)

    from music_segment import MusicSegment, RhythmCadence
    music_seg = MusicSegment(
        segment=seg,
        main_note_midi=60,
        scale=scale,
        rhythm_cadence=RhythmCadence.MEDIUM,
        register_hint=0.5,
        features=feats,
    )

    # Un bar ficticio: acorde C mayor, unos cuantos slots ON
    note_positions = np.zeros(16, dtype=int)
    note_positions[[0, 3, 5, 8, 12]] = 1
    bar = Bar(
        index=0,
        t_start=0.0,
        t_end=4.0,
        chord_root_midi=60,
        chord_pitches=[60, 64, 67],
        note_positions=note_positions,
        stability=0.8,
        amplitude_slots=np.ones(16),
    )

    gen = NoteGenerator()
    notes = gen.generate_notes_for_segment(music_seg, [bar])

    for n in notes:
        print(
            f"t=({n.t_start:.2f}-{n.t_end:.2f}) "
            f"pitch={n.pitch_midi} vel={n.velocity}"
        )
