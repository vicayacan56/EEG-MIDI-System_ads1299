"""
eeg_segmenter.py
----------------

Bloque 0 – Segmentador EEG → Segmentos musicales

Implementa una lógica inspirada en el paper de brainwave music:
- La música tiene la misma duración que el EEG.
- Se crean segmentos cuando la señal se desvía lo suficiente de la media
  del segmento actual, según:

      |x(i) - mean_segment| / |mean_segment| > threshold

Este módulo está pensado para trabajar:
- Offline: con arrays 1D (una señal ya filtrada de un canal).
- En streaming: añadiendo muestras progresivamente.

Más adelante, estos segmentos se usarán para fijar los parámetros
del "Music Segment" (main_note, escala, rhythm_cadence, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np


@dataclass
class Segment:
    """
    Representa un segmento de EEG continuo.

    Atributos:
        start_idx: índice de muestra inicial (incluido).
        end_idx: índice de muestra final (incluido).
        t_start: tiempo de inicio en segundos.
        t_end: tiempo de fin en segundos.
    """
    start_idx: int
    end_idx: int
    t_start: float
    t_end: float

    @property
    def duration_sec(self) -> float:
        return self.t_end - self.t_start


class EEGSegmenter:
    """
    Segmentador de señal EEG basado en un criterio relativo de desviación
    respecto a la media del segmento actual.

    Regla básica (inspirada en el paper):
        Cuando se cumple
            |x(i) - mean_segment| / (|mean_segment| + eps) > rel_threshold
        se considera que comienza un nuevo segmento en i.

    Parámetros
    ----------
    fs : float
        Frecuencia de muestreo en Hz.
    rel_threshold : float
        Umbral relativo para la inequación anterior. El paper usa
        conceptualmente un valor 1.0 (desviación > 100%), pero aquí
        se deja configurable.
    min_duration_sec : float
        Duración mínima permitida para un segmento (en segundos).
        Si se detecta un posible cambio antes de este tiempo, se
        ignora para evitar microsegmentos.
    use_abs : bool
        Si True, trabaja con el valor absoluto de la señal (útil si
        la señal oscila alrededor de 0).
    eps : float
        Pequeño valor para evitar división por cero.
    """

    def __init__(
        self,
        fs: float,
        rel_threshold: float = 1.0,
        min_duration_sec: float = 1.0,
        use_abs: bool = True,
        eps: float = 1e-9,
    ) -> None:
        self.fs = float(fs)
        self.rel_threshold = float(rel_threshold)
        self.min_duration_sec = float(min_duration_sec)
        self.use_abs = bool(use_abs)
        self.eps = float(eps)

        # Estado interno para modo streaming
        self._reset_state()

    # ------------------------------------------------------------------
    # Estado interno
    # ------------------------------------------------------------------
    def _reset_state(self) -> None:
        """Resetea el estado interno para modo streaming."""
        self._current_start_idx: Optional[int] = None
        self._current_sum: float = 0.0
        self._current_count: int = 0

    def reset(self) -> None:
        """Interfaz pública para resetear el estado streaming."""
        self._reset_state()

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------
    def _preprocess_abs_signal(self, x: np.ndarray) -> np.ndarray:
        """
        Preprocesado simple para la señal de entrada, previo a la
        segmentación. Aquí solo se aplica |x| si use_abs=True.

        (El filtrado/limpieza se hace fuera, en EEGSignalProcessor+DSPCore.)
        """
        x = np.asarray(x, dtype=float)
        if self.use_abs:
            x = np.abs(x)
        return x

    # ------------------------------------------------------------------
    # Modo OFFLINE: segmentar un array completo
    # ------------------------------------------------------------------
    def segment_array(self, x: np.ndarray) -> List[Segment]:
        """
        Segmenta un array 1D completo usando la regla de desviación
        relativa. Devuelve una lista de Segment.

        La última muestra siempre cierra el último segmento.
        """
        x = self._preprocess_abs_signal(x)
        n = x.size
        segments: List[Segment] = []

        if n == 0:
            return segments

        # Índice inicial del segmento actual
        seg_start = 0
        seg_sum = float(x[0])
        seg_count = 1

        for i in range(1, n):
            xi = float(x[i])
            # media del segmento actual hasta i-1
            mean_seg = seg_sum / seg_count if seg_count > 0 else 0.0

            # criterio de salto de segmento (paper-like)
            denom = abs(mean_seg) + self.eps
            rel_dev = abs(xi - mean_seg) / denom

            # duración actual del segmento en segundos
            current_duration_sec = (i - seg_start) / self.fs

            if (
                rel_dev > self.rel_threshold
                and current_duration_sec >= self.min_duration_sec
            ):
                # cerramos segmento en i-1
                seg_end = i - 1
                t_start = seg_start / self.fs
                t_end = seg_end / self.fs
                segments.append(
                    Segment(
                        start_idx=seg_start,
                        end_idx=seg_end,
                        t_start=t_start,
                        t_end=t_end,
                    )
                )
                # iniciamos nuevo segmento en i
                seg_start = i
                seg_sum = xi
                seg_count = 1
            else:
                # seguimos acumulando en el segmento actual
                seg_sum += xi
                seg_count += 1

        # cerrar el último segmento hasta el final
        seg_end = n - 1
        t_start = seg_start / self.fs
        t_end = seg_end / self.fs
        segments.append(
            Segment(
                start_idx=seg_start,
                end_idx=seg_end,
                t_start=t_start,
                t_end=t_end,
            )
        )

        return segments

    # ------------------------------------------------------------------
    # Modo STREAMING: muestra a muestra (o bloque a bloque)
    # ------------------------------------------------------------------
    def process_sample(self, x_i: float, idx: int) -> List[Segment]:
        """
        Procesa una sola muestra en modo streaming.

        Args
        ----
        x_i : float
            Muestra actual (ya filtrada); se aplicará abs() si use_abs=True.
        idx : int
            Índice global de la muestra dentro de la señal.

        Returns
        -------
        List[Segment]
            Lista de segmentos que se hayan cerrado en esta llamada.
            Lo más normal es que devuelva una lista vacía o como mucho
            un único segmento.
        """
        x_val = abs(float(x_i)) if self.use_abs else float(x_i)
        closed_segments: List[Segment] = []

        if self._current_start_idx is None:
            # Primer sample de la serie
            self._current_start_idx = idx
            self._current_sum = x_val
            self._current_count = 1
            return closed_segments

        # media del segmento actual hasta idx-1
        mean_seg = self._current_sum / self._current_count if self._current_count > 0 else 0.0
        denom = abs(mean_seg) + self.eps
        rel_dev = abs(x_val - mean_seg) / denom

        current_duration_sec = (idx - self._current_start_idx) / self.fs

        if (
            rel_dev > self.rel_threshold
            and current_duration_sec >= self.min_duration_sec
        ):
            # Cerrar segmento anterior en idx-1
            seg_end = idx - 1
            t_start = self._current_start_idx / self.fs
            t_end = seg_end / self.fs
            closed_segments.append(
                Segment(
                    start_idx=self._current_start_idx,
                    end_idx=seg_end,
                    t_start=t_start,
                    t_end=t_end,
                )
            )

            # Iniciar nuevo segmento en idx
            self._current_start_idx = idx
            self._current_sum = x_val
            self._current_count = 1
        else:
            # Continuar segmento actual
            self._current_sum += x_val
            self._current_count += 1

        return closed_segments

    def flush(self, last_idx: int) -> Optional[Segment]:
        """
        Cierra el último segmento abierto en modo streaming cuando
        se ha terminado la señal.

        Args
        ----
        last_idx : int
            Índice de la última muestra válida (incluida).

        Returns
        -------
        Segment or None
            El último segmento, o None si no había segmento abierto.
        """
        if self._current_start_idx is None:
            return None

        seg_end = last_idx
        t_start = self._current_start_idx / self.fs
        t_end = seg_end / self.fs

        seg = Segment(
            start_idx=self._current_start_idx,
            end_idx=seg_end,
            t_start=t_start,
            t_end=t_end,
        )

        # reset estado tras cerrar
        self._reset_state()
        return seg


# Pequeña prueba rápida
if __name__ == "__main__":
    import matplotlib.pyplot as plt

    fs = 250.0
    t = np.arange(0, 20, 1/fs)  # 20 s

    # Señal sintética con cambio brusco de amplitud a los 10 s
    x = 10e-6 * np.sin(2 * np.pi * 10 * t)
    x[t >= 10] *= 4.0  # más grande a partir de 10 s

    segm = EEGSegmenter(fs=fs, rel_threshold=1.0, min_duration_sec=2.0)
    segments = segm.segment_array(x)

    print("Segmentos detectados:")
    for s in segments:
        print(f"  {s}")

    # Plot opcional para ver la segmentación
    plt.plot(t, x)
    for s in segments:
        plt.axvspan(s.t_start, s.t_end, alpha=0.2)
    plt.xlabel("Tiempo [s]")
    plt.ylabel("Amplitud")
    plt.show()
