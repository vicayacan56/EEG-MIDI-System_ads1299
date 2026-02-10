"""
music_bar.py
------------

Bloque 2 – Bar Generator

A partir de:
  - un MusicSegment (segmento musical derivado de EEG),
  - una lista de medidas de "estabilidad espectral" por compás,
  - una lista de envolventes de amplitud EEG por compás (16 slots),

genera una lista de objetos Bar con:
  - chord (acorde diatónico dentro de la escala),
  - patrón de note_positions (16 slots ON/OFF).

La lógica sigue el espíritu del paper:
  - la varianza/cambio espectral se asocia a la "estabilidad" del acorde,
  - la amplitude + rhythm_cadence determinan en qué slots hay notas ON.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence

import numpy as np

from music_segment import MusicSegment, RhythmCadence, ScaleConfig


@dataclass
class Bar:
    """
    Representa un compás dentro de un MusicSegment.

    Atributos:
        index: índice del compás dentro del segmento (0,1,2,...).
        t_start: tiempo de inicio (segundos, en el marco global del EEG).
        t_end: tiempo de fin (segundos).
        chord_root_midi: nota MIDI raíz del acorde.
        chord_pitches: lista de notas MIDI que forman el acorde (triada).
        note_positions: array bool/int de longitud n_slots (por defecto 16),
                        1 -> note-on en esa posición, 0 -> no.
        stability: valor de estabilidad espectral asociado al compás (0..1, approx).
        amplitude_slots: amplitud EEG por slot (normalizada o sin normalizar).
    """
    index: int
    t_start: float
    t_end: float
    chord_root_midi: int
    chord_pitches: List[int]
    note_positions: np.ndarray
    stability: float
    amplitude_slots: np.ndarray


class BarGenerator:
    """
    Generador de Bars a partir de un MusicSegment.

    Entrada principal:
        - MusicSegment (ya contiene:
            - main_note_midi,
            - scale (ScaleConfig),
            - rhythm_cadence,
            - register_hint, etc.)
        - stability_per_bar: lista de floats [0..1] que representan cuánta
          variación espectral hay en cada compás dentro del segmento
          (0 = muy estable, 1 = muy variable).
        - amplitude_slots_per_bar: lista de arrays (n_slots,) con una medida
          de amplitud EEG (o derivada) por cada slot 4x4 (16 posiciones).

    Decisiones de diseño (modificables):
        - un Bar tiene 4 beats x 4 positions = 16 slots.
        - chord selection:
            stability baja  -> grado I
            estabilidad med -> grado IV
            estabilidad alta-> grado V
          (todo diatónico dentro de scale.intervals)
        - note_positions:
            el número de notes-on se basa en rhythm_cadence,
            y las posiciones se eligen según la amplitud (umbral + top-k).
    """

    def __init__(
        self,
        beats_per_bar: int = 4,
        slots_per_beat: int = 4,
        low_notes_per_bar: int = 3,
        medium_notes_per_bar: int = 6,
        high_notes_per_bar: int = 16,
        amplitude_threshold_rel: float = 0.5,
    ) -> None:
        """
        Parámetros
        ----------
        beats_per_bar : int
            Nº de beats en un compás (4 para 4/4).
        slots_per_beat : int
            Nº de subposiciones por beat (4 -> rejilla 4x4 = 16).
        low_notes_per_bar / medium_notes_per_bar / high_notes_per_bar :
            Nº aproximado de notes-on por compás según RhythmCadence.
        amplitude_threshold_rel : float
            Umbral relativo para amplitud. Se usa como fracción del
            máximo de amplitud en el compás para decidir qué slots
            son "candidatos" a note-on. (ej. 0.5 -> amplitud > 50% del max).
        """
        self.beats_per_bar = int(beats_per_bar)
        self.slots_per_beat = int(slots_per_beat)
        self.n_slots = self.beats_per_bar * self.slots_per_beat

        self.low_notes_per_bar = int(low_notes_per_bar)
        self.medium_notes_per_bar = int(medium_notes_per_bar)
        self.high_notes_per_bar = int(high_notes_per_bar)

        self.amplitude_threshold_rel = float(amplitude_threshold_rel)

    # ------------------------------------------------------------------
    # Utilidades para acordes
    # ------------------------------------------------------------------
    def _build_diatonic_triad(
        self,
        scale: ScaleConfig,
        degree_idx: int,
        base_octave_offset: int = 0,
    ) ->(tuple[int, List[int]]):
        """
        Construye una triada diatónica a partir de la escala.

        scale.intervals define los semitonos de la escala en una octava:
            intervals = [0, 2, 4, 5, 7, 9, 11] para mayor.

        La triada del grado d usa:
            intervals[d], intervals[d+2], intervals[d+4] (mod len(intervals)).

        degree_idx se considera 0-based (0=I,1=II,...).
        base_octave_offset desplaza la raíz una o más octavas desde scale.root_midi.
        """
        intervals = list(scale.intervals)
        n_degrees = len(intervals)
        d = degree_idx % n_degrees

        root_interval = intervals[d]
        third_interval = intervals[(d + 2) % n_degrees]
        fifth_interval = intervals[(d + 4) % n_degrees]

        root_midi = scale.root_midi + 12 * base_octave_offset + root_interval
        third_midi = scale.root_midi + 12 * base_octave_offset + third_interval
        fifth_midi = scale.root_midi + 12 * base_octave_offset + fifth_interval

        triad = [root_midi, third_midi, fifth_midi]
        return root_midi, triad

    def _choose_chord_degree(self, stability: float) -> int:
        """
        Elige un grado de la escala (0-based) a partir de la estabilidad.
        Regla simple:
            estabilidad baja  (0..0.33) -> I (grado 0)
            estabilidad media (0.33..0.66) -> IV (grado 3)
            estabilidad alta  (0.66..1.0) -> V (grado 4)
        Esto se puede generalizar más adelante.
        """
        if stability <= 0.33:
            return 0  # I
        elif stability <= 0.66:
            return 3  # IV
        else:
            return 4  # V

    # ------------------------------------------------------------------
    # Utilidades para note_positions
    # ------------------------------------------------------------------
    def _target_notes_for_cadence(self, cadence: RhythmCadence) -> int:
        """
        Devuelve el nº aproximado de notes-on objetivo según RhythmCadence.
        """
        if cadence == RhythmCadence.LOW:
            return self.low_notes_per_bar
        elif cadence == RhythmCadence.HIGH:
            return self.high_notes_per_bar
        else:
            return self.medium_notes_per_bar

    def _choose_note_positions(
        self,
        cadence: RhythmCadence,
        amplitude_slots: np.ndarray,
    ) -> np.ndarray:
        """
        Determina un patrón de note_positions (n_slots,) a partir de:
            - rhythm_cadence (nº de notas objetivo),
            - amplitude_slots (amplitud EEG por slot).

        Estrategia:
            1) Normalizar amplitudes a [0,1] si no lo están.
            2) Calcular umbral = amplitude_threshold_rel * max.
            3) Tomar como candidatos los slots con amplitud >= umbral.
            4) Ordenar candidatos por amplitud descendente.
            5) Activar note-on en los top-K (K = target_notes), sin repetir.
            6) Si hay menos candidatos que K, rellenar con las máximas restantes.
        """
        amps = np.asarray(amplitude_slots, dtype=float)
        if amps.size != self.n_slots:
            raise ValueError(
                f"amplitude_slots debe tener longitud {self.n_slots}, "
                f"recibido {amps.size}"
            )

        # Normalización simple para evitar problemas con escalas muy distintas
        max_amp = np.max(np.abs(amps)) if amps.size > 0 else 0.0
        if max_amp > 0:
            amps_norm = amps / max_amp
        else:
            amps_norm = amps.copy()  # todo 0

        # Nº objetivo de notas
        target_notes = self._target_notes_for_cadence(cadence)
        target_notes = max(1, min(target_notes, self.n_slots))

        # Candidatos: >= umbral relativo
        thr = self.amplitude_threshold_rel
        candidate_idxs = np.where(amps_norm >= thr)[0]

        if candidate_idxs.size == 0:
            # si no hay candidatos, se toman simplemente los slots de mayor amplitud
            candidate_idxs = np.argsort(-amps_norm)  # descending

        # Ordenar candidatos por amplitud descendente
        sorted_candidates = sorted(
            candidate_idxs,
            key=lambda idx: amps_norm[idx],
            reverse=True,
        )

        note_positions = np.zeros(self.n_slots, dtype=int)

        # Activar top-K
        for idx in sorted_candidates[:target_notes]:
            note_positions[idx] = 1

        return note_positions

    def _build_note_positions(
        self,
        amplitude_slots: np.ndarray,
        rhythm_cadence,
    ) -> np.ndarray:
        """
        Wrapper: a partir de la cadencia rítmica decide cuántas notas
        debe haber en el compás y llama a _choose_note_positions.
        """
        
        return self._choose_note_positions(
            cadence=rhythm_cadence,
            amplitude_slots=amplitude_slots,
            
        )

    def _map_stability_to_degree_idx(
        self,
        stability: float,
        n_degrees: int,
    ) -> int:
        """
        Mapea una estabilidad en [0,1] a un grado diatónico.

        Idea simple:
          - estabilidad baja  -> acordes "tensos" (por ejemplo V)
          - estabilidad media -> acordes "subdominantes" (IV)
          - estabilidad alta  -> acordes "estables" (I)

        Usamos grados relativos:
          0 -> I
          3 -> IV
          4 -> V
        (asumiendo escala mayor con al menos 5 grados).
        """
        # seguridad
        if np.isnan(stability) or np.isinf(stability):
            stability = 0.5
        stability = max(0.0, min(1.0, float(stability)))

        # Valores típicos
        if n_degrees < 5:
            # si es una escala muy rara, cae siempre al grado 0
            return 0

        if stability < 0.33:
            # inestable -> dominante (V)
            degree_idx = 4
        elif stability < 0.66 and stability >= 0.33:
            # medio -> subdominante (IV)
            degree_idx = 3
        else:
            # muy estable -> tónica (I)
            degree_idx = 0

        # Por seguridad, clamp a rango [0, n_degrees-1]
        degree_idx = max(0, min(n_degrees - 1, degree_idx))
        return degree_idx
    

    # ------------------------------------------------------------------
    # Interfaz principal
    # ------------------------------------------------------------------
    def generate_bars(
        self,
        segment: MusicSegment,
        stability_per_bar: Sequence[float],
        amplitude_slots_per_bar: Sequence[Sequence[float]],
        base_octave_offset: int = 0,
    ) -> List[Bar]:
        """
        Genera una lista de Bars dentro de un MusicSegment.

        Args
        ----
        segment : MusicSegment
            Segmento musical base (t_start, t_end, escala, cadencia, etc.).
        stability_per_bar : Sequence[float]
            Lista de valores de estabilidad espectral (0..1 aprox) por compás.
        amplitude_slots_per_bar : Sequence[Sequence[float]]
            Lista de listas/arrays, uno por compás, con amplitud por slot
            (de longitud n_slots, por defecto 16).
        base_octave_offset : int
            Desplazamiento en octavas para construir el acorde con respecto
            a scale.root_midi.

        Returns
        -------
        List[Bar]
        """
        n_bars = len(stability_per_bar)
        if n_bars == 0:
            return []

        if len(amplitude_slots_per_bar) != n_bars:
            raise ValueError(
                "stability_per_bar y amplitude_slots_per_bar deben tener "
                "la misma longitud."
            )

        total_duration = segment.segment.duration_sec
        bar_duration = total_duration / n_bars

        bars: list[Bar] = []
        n_degrees = len(segment.scale.intervals)  # suele ser 7 en mayor/menor

        for i in range(n_bars):
            stab = stability_per_bar[i] if i < len(stability_per_bar) else 0.5
            amp_slots = amplitude_slots_per_bar[i]

            # --- elegir grado del acorde en función de estabilidad ---
            degree_idx = self._map_stability_to_degree_idx(
                stability=stab,
                n_degrees=n_degrees,
            )

            # construir la triada para ese grado
            chord_root_midi, chord_pitches = self._build_diatonic_triad(
                scale=segment.scale,
                degree_idx=degree_idx,
                base_octave_offset=base_octave_offset,
            )

            # patrón rítmico ON/OFF
            note_positions = self._build_note_positions(
                amplitude_slots=amp_slots,
                rhythm_cadence=segment.rhythm_cadence,
            )

            # tiempos del bar
            bar_t_start = segment.segment.t_start + i * bar_duration
            bar_t_end = bar_t_start + bar_duration

            bar = Bar(
                index=i,
                t_start=bar_t_start,
                t_end=bar_t_end,
                chord_root_midi=chord_root_midi,
                chord_pitches=chord_pitches,
                note_positions=note_positions,
                stability=stab,
                amplitude_slots=amp_slots,
            )
            bars.append(bar)

        print("[DEBUG] grados por bar:", [self._map_stability_to_degree_idx(s, n_degrees) for s in stability_per_bar])
        return bars



# Pequeña prueba sintética
if __name__ == "__main__":
    from eeg_segmenter import Segment
    from music_segment import ScaleConfig, MAJOR_INTERVALS, MusicSegment, RhythmCadence

    # Segmento ficticio 8 s
    seg = Segment(start_idx=0, end_idx=2000, t_start=0.0, t_end=8.0)

    # EEG features inventados
    eeg_feats = {
        "peak_freq": 10.0,
        "bandpower_rel": {"alpha": 0.4},
        "rms": 5e-6,
    }

    # Escala C mayor, main note G4
    scale = ScaleConfig(root_midi=60, name="C_major", intervals=MAJOR_INTERVALS)
    music_seg = MusicSegment(
        segment=seg,
        main_note_midi=67,
        scale=scale,
        rhythm_cadence=RhythmCadence.MEDIUM,
        register_hint=0.5,
        features=eeg_feats,
    )

    # Generamos 4 compases dentro de los 8 s
    stability_vals = [0.1, 0.4, 0.7, 0.9]  # estable -> I, medio -> IV, inestable -> V
    # amplitud aleatoria por slot
    rng = np.random.default_rng(123)
    amp_slots_list = [rng.random(16) for _ in range(4)]

    gen = BarGenerator()
    bars = gen.generate_bars(music_seg, stability_vals, amp_slots_list)

    for b in bars:
        print(f"Bar {b.index}: t=({b.t_start:.2f}-{b.t_end:.2f})s")
        print("  stability:", b.stability)
        print("  chord_root_midi:", b.chord_root_midi, "pitches:", b.chord_pitches)
        print("  note_positions:", b.note_positions)
