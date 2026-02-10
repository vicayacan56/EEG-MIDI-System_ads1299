"""
music_segment.py
----------------

Bloque 1 – Music Segment

Dado:
  - un segmento de EEG (índices y tiempos),
  - un diccionario de características EEG (EEGFeatures),
  - una escala/tonalidad elegida por el usuario,
  - y una main note elegida por el usuario (opcional),

se construye un objeto MusicSegment con:

  - main_note_midi  -> nota central del segmento (FIJA, elegida por el usuario),
  - scale           -> escala/tonalidad fija elegida por el usuario,
  - rhythm_cadence  -> densidad rítmica (LOW/MEDIUM/HIGH),
  - register_hint   -> pista de registro (0..1) para octavas posteriores,
  - features        -> features originales por si se usan más adelante.

La main note NO depende de peak_freq.
peak_freq se sigue utilizando para register_hint y/o futuros
mapeos. No modula la main note.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, Any, Optional, Sequence

import numpy as np

from eeg_segmenter import Segment


# ---------------------------------------------------------------------
# Escala / Tonalidad
# ---------------------------------------------------------------------


@dataclass
class ScaleConfig:
    """
    Representa una escala musical discreta dentro del sistema MIDI.

    Atributos:
        root_midi: nota raíz en MIDI (ej. 60 = C4).
        name: nombre de la escala (ej. "C_major", "A_minor", "D_dorian"...).
        intervals: semitonos desde la raíz que forman la escala dentro
                   de una octava (ej. mayor: [0,2,4,5,7,9,11]).
    """
    root_midi: int
    name: str
    intervals: Sequence[int]

    def contains(self, midi_note: int) -> bool:
        """Devuelve True si la nota MIDI pertenece a la escala (mod 12)."""
        rel = (midi_note - self.root_midi) % 12
        return rel in self.intervals

    def nearest_note(self, midi_note: int) -> int:
        """
        Devuelve la nota MIDI de la escala más cercana a midi_note.
        Útil más adelante para cuantizar pitches, pero no para main_note
        (que ahora decide el usuario).
        """
        best_note = midi_note
        best_dist = float("inf")
        for octave_shift in (-2, -1, 0, 1, 2):
            base = self.root_midi + 12 * octave_shift
            for iv in self.intervals:
                candidate = base + iv
                dist = abs(candidate - midi_note)
                if dist < best_dist:
                    best_dist = dist
                    best_note = candidate
        return best_note


# Algunas escalas típicas por defecto
MAJOR_INTERVALS = [0, 2, 4, 5, 7, 9, 11]
NAT_MINOR_INTERVALS = [0, 2, 3, 5, 7, 8, 10]


# ---------------------------------------------------------------------
# Rhythm cadence
# ---------------------------------------------------------------------


class RhythmCadence(Enum):
    LOW = auto()     # pocas notas por compás
    MEDIUM = auto()  # densidad intermedia
    HIGH = auto()    # muchas notas por compás


@dataclass
class MusicSegment:
    """
    Representa un segmento musical derivado de un segmento EEG.

    Atributos:
        segment: objeto Segment (índices/tiempos originales).
        main_note_midi: nota central que caracteriza el segmento (fija).
        scale: configuración de escala elegida por el usuario.
        rhythm_cadence: densidad rítmica (LOW/MEDIUM/HIGH).
        register_hint: número en [0,1] que sugiere registro (0 grave, 1 agudo).
        features: diccionario de características EEG asociadas al segmento.
    """
    segment: Segment
    main_note_midi: int
    scale: ScaleConfig
    rhythm_cadence: RhythmCadence
    register_hint: float
    features: Dict[str, Any]


class MusicSegmentBuilder:
    """
    Construye objetos MusicSegment a partir de:
      - Segment (de eeg_segmenter),
      - diccionario de features EEG (EEGFeatures),
      - escala y main note elegidas por el usuario.

    Decisiones de diseño:
      - main_note_midi NO depende del EEG: la fija el usuario y se
        mantiene de segmento en segmento hasta que el usuario la cambie.
      - rhythm_cadence se obtiene a partir de la alpha_rate
        (bandpower_rel["alpha"]) con dos umbrales.
      - register_hint se basa en normalizar peak_freq en un rango
        (f_min, f_max) -> [0,1].
    """

    def __init__(
        self,
        fs: float,
        eeg_freq_range: tuple[float, float] = (0.5, 30.0),
        alpha_thresholds: tuple[float, float] = (0.2, 0.5),
    ) -> None:
        """
        Parámetros
        ----------
        fs : float
            Frecuencia de muestreo (por si se necesitara más adelante).
        eeg_freq_range : (f_min, f_max)
            Rango de frecuencias EEG esperado para normalizar peak_freq
            en register_hint.
        alpha_thresholds : (t_low, t_high)
            Umbrales para alpha_rate:
                alpha < t_low  -> RhythmCadence.LOW
                t_low..t_high  -> RhythmCadence.MEDIUM
                alpha > t_high -> RhythmCadence.HIGH
        """
        self.fs = float(fs)
        self.f_min, self.f_max = eeg_freq_range
        self.alpha_low, self.alpha_high = alpha_thresholds

    # ------------------------------------------------------------------
    # mapeos internos
    # ------------------------------------------------------------------
    def _map_rhythm_cadence(self, alpha_rate: float) -> RhythmCadence:
        """
        Mapea alpha_rate (0..1) a una categoría de densidad rítmica.
        """
        if np.isnan(alpha_rate):
            # por defecto, cadencia media
            return RhythmCadence.MEDIUM

        if alpha_rate < self.alpha_low:
            return RhythmCadence.LOW
        elif alpha_rate > self.alpha_high:
            return RhythmCadence.HIGH
        else:
            return RhythmCadence.MEDIUM

    def _map_register_hint(self, peak_freq: float) -> float:
        """
        Normaliza la peak_freq al rango [f_min, f_max] y devuelve
        un valor en [0,1] que sirve como pista de registro:
            0 -> registro bajo
            1 -> registro alto
        """
        if np.isnan(peak_freq) or peak_freq <= 0:
            return 0.5  # valor neutro
        f_clamped = max(self.f_min, min(self.f_max, peak_freq))
        return (f_clamped - self.f_min) / (self.f_max - self.f_min)

    # ------------------------------------------------------------------
    # interfaz pública
    # ------------------------------------------------------------------
    def build_segment(
        self,
        segment: Segment,
        eeg_features: Dict[str, Any],
        user_scale: ScaleConfig,
        user_main_note_midi: Optional[int] = None,
    ) -> MusicSegment:
        """
        Construye un MusicSegment a partir de:
          - Segment (con info temporal),
          - eeg_features (diccionario de features por segmento),
          - user_scale (escala fija elegida por el usuario),
          - user_main_note_midi (nota central elegida por el usuario).

        Si user_main_note_midi es None, se usa user_scale.root_midi
        como main note.
        """
        peak_freq = float(eeg_features.get("peak_freq", np.nan))

        # alpha_rate: usamos bandpower_rel["alpha"] si existe
        bandpower_rel = eeg_features.get("bandpower_rel", {})
        alpha_rate = float(bandpower_rel.get("alpha", np.nan))

        rhythm_cadence = self._map_rhythm_cadence(alpha_rate)
        register_hint = self._map_register_hint(peak_freq)

        # main note FIJA, elegida por el usuario
        if user_main_note_midi is None:
            main_note_midi = int(user_scale.root_midi)
        else:
            main_note_midi = int(user_main_note_midi)

        return MusicSegment(
            segment=segment,
            main_note_midi=main_note_midi,
            scale=user_scale,
            rhythm_cadence=rhythm_cadence,
            register_hint=register_hint,
            features=eeg_features,
        )


# Pequeña prueba sintética
if __name__ == "__main__":
    # Segmento falso de 0 a 10 s
    seg = Segment(start_idx=0, end_idx=2500, t_start=0.0, t_end=10.0)

    # Supongamos que el DSP ha calculado estas features:
    eeg_feats = {
        "peak_freq": 10.0,  # 10 Hz ~ alpha
        "bandpower_rel": {
            "delta": 0.1,
            "theta": 0.2,
            "alpha": 0.5,
            "beta": 0.15,
            "gamma": 0.05,
        },
        "rms": 5e-6,
    }

    # Escala elegida por el usuario: C mayor con raíz en C4 (60)
    user_scale = ScaleConfig(
        root_midi=60,
        name="C_major",
        intervals=MAJOR_INTERVALS,
    )

    builder = MusicSegmentBuilder(
        fs=250.0,
        eeg_freq_range=(0.5, 30.0),
        alpha_thresholds=(0.2, 0.5),
    )

    # main note elegida por el usuario explícitamente (por ejemplo G4 = 67)
    music_seg = builder.build_segment(
        segment=seg,
        eeg_features=eeg_feats,
        user_scale=user_scale,
        user_main_note_midi=67,
    )

    print("MusicSegment generado:")
    print("  main_note_midi:", music_seg.main_note_midi)
    print("  scale:", music_seg.scale.name)
    print("  rhythm_cadence:", music_seg.rhythm_cadence)
    print("  register_hint:", music_seg.register_hint)
    print("  duracion (s):", music_seg.segment.duration_sec)
