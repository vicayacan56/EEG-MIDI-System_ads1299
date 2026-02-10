"""
eeg_to_bars.py
--------------

Módulo "pegamento" entre el análisis EEG (DSPCore) y el generador
de compases (BarGenerator).

Responsabilidad:
    - Recibir un MusicSegment (ya construido a partir de un Segment + EEG features),
    - Recibir la señal filtrada de ese segmento (x_segment),
    - Dividir ese segmento en n_bars,
    - Calcular para cada bar:
        * estabilidad espectral (usando DSPCore.compute_spectral_stability),
        * amplitud por slot (rejilla 4x4 -> 16 valores),
    - Llamar a BarGenerator.generate_bars(...) y devolver la lista de Bars.

Requiere que DSPCore tenga implementado:
    - compute_spectral_stability(x, fmin, fmax, psd_method="multitaper")
(ver implementación propuesta en dsp_core.py).
"""

from __future__ import annotations

from typing import List

import numpy as np

from dsp_core import DSPCore
from music_segment import MusicSegment
from music_bar import BarGenerator, Bar


def _compute_stability_per_bar(
    dsp: DSPCore,
    x_segment: np.ndarray,
    n_bars: int,
    fmin: float = 0.5,
    fmax: float = 40.0,
) -> list[float]:
    """
    Divide x_segment en n_bars trozos temporales y calcula una métrica
    de estabilidad espectral por compás usando DSPCore.compute_spectral_stability.

    Args
    ----
    dsp : DSPCore
        Núcleo DSP ya configurado (mismo fs que la señal).
    x_segment : np.ndarray
        Señal filtrada (1D) correspondiente SOLO a ese segmento.
    n_bars : int
        Nº de compases que se desea dentro de este segmento.
    fmin, fmax : float
        Rango de frecuencias a considerar para la entropía espectral.

    Returns
    -------
    list[float]
        Lista de long. n_bars con un valor de estabilidad por compás.
        Valores ~1 -> espectro concentrado (más estable),
        valores ~0 -> espectro caótico/plano (menos estable).
    """
    x_segment = np.asarray(x_segment, dtype=float)
    n_total = x_segment.size

    if n_total < 4 or n_bars <= 0:
        return []

    samples_per_bar = n_total // n_bars
    if samples_per_bar < 4:
        # señal demasiado corta para tantos compases; hacemos un único bar
        n_bars = 1
        samples_per_bar = n_total

    stabilities: list[float] = []

    for i in range(n_bars):
        start = i * samples_per_bar
        end = (i + 1) * samples_per_bar if i < n_bars - 1 else n_total
        seg_x = x_segment[start:end]

        stab = dsp.compute_spectral_stability(
            seg_x,
            fmin=fmin,
            fmax=fmax,
            psd_method="multitaper",
        )
        if np.isnan(stab) or np.isinf(stab):
            stab = 0.5  # neutro
        else:
            # clamp a [0,1] por si las moscas
            stab = float(max(0.0, min(1.0, stab)))
        stabilities.append(stab)

    return stabilities


def _compute_amplitude_slots_per_bar(
    x_segment: np.ndarray,
    n_bars: int,
    n_slots_per_bar: int,
) -> list[np.ndarray]:
    """
    Calcula la 'amplitud' por slot (RMS simple) para cada compás.

    Proceso:
        - Se divide x_segment en n_bars trozos (como en stability).
        - Cada bar se divide en n_slots_per_bar subventanas.
        - Para cada slot, se calcula una medida de amplitud (RMS).

    Args
    ----
    x_segment : np.ndarray
        Señal filtrada 1D del segmento.
    n_bars : int
        Nº de compases en el segmento.
    n_slots_per_bar : int
        Nº de slots por compás (debe coincidir con bar_gen.n_slots).

    Returns
    -------
    list[np.ndarray]
        Lista de longitud n_bars, cada elemento es un array (n_slots_per_bar,)
        con la amplitud estimada en cada slot.
    """
    x_segment = np.asarray(x_segment, dtype=float)
    n_total = x_segment.size

    if n_total == 0 or n_bars <= 0:
        return []

    samples_per_bar = n_total // n_bars
    if samples_per_bar == 0:
        n_bars = 1
        samples_per_bar = n_total

    amp_slots_list: list[np.ndarray] = []

    for i in range(n_bars):
        start_bar = i * samples_per_bar
        end_bar = (i + 1) * samples_per_bar if i < n_bars - 1 else n_total
        bar_x = x_segment[start_bar:end_bar]

        n_bar_samples = bar_x.size
        if n_bar_samples == 0:
            amp_slots_list.append(np.zeros(n_slots_per_bar, dtype=float))
            continue

        samples_per_slot = max(1, n_bar_samples // n_slots_per_bar)

        slots_amp = np.zeros(n_slots_per_bar, dtype=float)

        for s in range(n_slots_per_bar):
            start_slot = s * samples_per_slot
            end_slot = (s + 1) * samples_per_slot if s < n_slots_per_bar - 1 else n_bar_samples
            slot_x = bar_x[start_slot:end_slot]

            if slot_x.size == 0:
                slots_amp[s] = 0.0
            else:
                # RMS como medida de amplitud
                slots_amp[s] = float(np.sqrt(np.mean(slot_x ** 2)))

        amp_slots_list.append(slots_amp)

    return amp_slots_list


def generate_bars_for_segment(
    dsp: DSPCore,
    bar_gen: BarGenerator,
    music_segment: MusicSegment,
    x_segment: np.ndarray,
    n_bars: int,
    stability_fmin: float = 0.5,
    stability_fmax: float = 40.0,
) -> List[Bar]:
    """
    Función de alto nivel para generar los Bars de un MusicSegment.

    Args
    ----
    dsp : DSPCore
        Núcleo DSP con fs configurado.
    bar_gen : BarGenerator
        Generador de Bars (music_bar.BarGenerator).
    music_segment : MusicSegment
        Segmento musical para el que queremos crear compases.
    x_segment : np.ndarray
        Señal filtrada del canal correspondiente, SOLO en ese segmento.
        Suele obtenerse como x_filt[segment.start_idx : segment.end_idx+1].
    n_bars : int
        Nº de compases que queremos en este MusicSegment.
    stability_fmin, stability_fmax : float
        Rango de frecuencias usado para el cálculo de estabilidad espectral.

    Returns
    -------
    List[Bar]
        Lista de compases generados dentro del segmento.
    """
    x_segment = np.asarray(x_segment, dtype=float)
    if x_segment.size < 4 or n_bars <= 0:
        return []

    # 1) Estabilidad por compás (entropía espectral)
    stability_per_bar = _compute_stability_per_bar(
        dsp=dsp,
        x_segment=x_segment,
        n_bars=n_bars,
        fmin=stability_fmin,
        fmax=stability_fmax,
    )
    stab_arr = np.asarray(stability_per_bar, dtype=float)

    # saneamos NaN/Inf → 0.5
    bad = ~np.isfinite(stab_arr)
    if np.any(bad):
        stab_arr[bad] = 0.5

    if stab_arr.size == 0:
        stab_norm = np.zeros(0, dtype=float)
    else:
        s_min = float(stab_arr.min())
        s_max = float(stab_arr.max())
        if s_max - s_min > 1e-6:
            # normalizamos a [0, 1] por segmento
            stab_norm = (stab_arr - s_min) / (s_max - s_min)
        else:
            # si casi no hay variación, forzamos un gradiente artificial suave
            stab_norm = np.linspace(0.2, 0.8, num=stab_arr.size)

    stability_per_bar_norm = stab_norm.tolist()

    print("[DEBUG] stability_per_bar (raw):", stability_per_bar[:16], "...")
    print("[DEBUG] stability_per_bar (norm):", stability_per_bar_norm[:16], "...")


    # 2) Amplitud por slot en cada compás
    amp_slots_per_bar = _compute_amplitude_slots_per_bar(
        x_segment=x_segment,
        n_bars=n_bars,
        n_slots_per_bar=bar_gen.n_slots,
    )

    # 3) Generar Bars usando el BarGenerator
    bars = bar_gen.generate_bars(
        segment=music_segment,
        stability_per_bar=stability_per_bar_norm,
        amplitude_slots_per_bar=amp_slots_per_bar,
        base_octave_offset=0,  # se puede exponer como parámetro más adelante
    )

    return bars


# Pequeña prueba sintética
if __name__ == "__main__":
    from eeg_segmenter import Segment
    from music_segment import ScaleConfig, MAJOR_INTERVALS, MusicSegment, RhythmCadence
    from music_bar import BarGenerator
    from dsp_core import DSPCore

    fs = 250.0
    t = np.arange(0, 8.0, 1/fs)  # 8 s
    # señal alfa de 10 Hz con un poco de ruido
    x = 20e-6 * np.sin(2 * np.pi * 10 * t) + 5e-6 * np.random.randn(t.size)

    # Segmento completo
    seg = Segment(start_idx=0, end_idx=len(x)-1, t_start=0.0, t_end=t[-1])

    eeg_feats = {
        "peak_freq": 10.0,
        "bandpower_rel": {"alpha": 0.4},
        "rms": float(np.sqrt(np.mean(x**2))),
    }

    scale = ScaleConfig(root_midi=60, name="C_major", intervals=MAJOR_INTERVALS)
    music_seg = MusicSegment(
        segment=seg,
        main_note_midi=60,  # C4
        scale=scale,
        rhythm_cadence=RhythmCadence.MEDIUM,
        register_hint=0.5,
        features=eeg_feats,
    )

    dsp = DSPCore(fs=fs, window_sec=4.0)
    bar_gen = BarGenerator()

    bars = generate_bars_for_segment(
        dsp=dsp,
        bar_gen=bar_gen,
        music_segment=music_seg,
        x_segment=x,
        n_bars=4,
        stability_fmin=0.5,
        stability_fmax=40.0,
    )

    for b in bars:
        print(f"Bar {b.index}: t=({b.t_start:.2f}-{b.t_end:.2f})s")
        print("  stability:", b.stability)
        print("  chord_root_midi:", b.chord_root_midi, "pitches:", b.chord_pitches)
        print("  note_positions:", b.note_positions)
