# src/eeg_signal_processor.py

"""
EEGSignalProcessor
------------------
Versión del procesador de señal que:
  - Gestiona buffers y filtros por canal (como el SignalProcessor original)
  - Usa DSPCore para PSD, bandpower y features avanzadas.
"""

import numpy as np
from collections import deque
from scipy import signal
import logging

from dsp_core import DSPCore

logger = logging.getLogger(__name__)

SAMPLING_RATE = 250
NUM_CHANNELS = 4


class EEGSignalProcessor:
    """Procesa señales EEG en tiempo real usando DSPCore internamente."""

    def __init__(
        self,
        fs: int = SAMPLING_RATE,
        num_channels: int = NUM_CHANNELS,
        buffer_sec: float = 4.0,
        psd_window_sec: float = 4.0,
        window_type: str = "hann",
        welch_overlap: float = 0.5,
    ):
        self.fs = fs
        self.num_channels = num_channels

        # Buffer circular grande para cada canal
        self.buffer_size = int(buffer_sec * fs)
        self.buffers = [deque(maxlen=self.buffer_size) for _ in range(num_channels)]

        # Filtros (igual que en el procesador original)
        self._design_filters()

        # Núcleo DSP para análisis espectral
        self.dsp = DSPCore(
            fs=self.fs,
            window_sec=psd_window_sec,
            window_type=window_type,
            welch_overlap=welch_overlap,
        )

        logger.info(
            f"EEGSignalProcessor iniciado: fs={self.fs}Hz, "
            f"buffer={buffer_sec}s, psd_window={psd_window_sec}s"
        )

    # ------------------- filtros -------------------
    def _design_filters(self):
        self.hp_coeff = signal.butter(2, 0.5, fs=self.fs, btype="high", output="ba")
        self.lp_coeff = signal.butter(2, 50, fs=self.fs, btype="low", output="ba")
        self.notch_coeff = signal.iirnotch(60, Q=30, fs=self.fs)
        logger.info("Filtros: HP(0.5Hz) - LP(50Hz) - Notch(60Hz)")

    # ------------------- buffer -------------------
    def add_sample(self, voltages: list[float]):
        if len(voltages) != self.num_channels:
            logger.warning(f"Número incorrecto de canales: {len(voltages)}")
            return
        for ch, v in enumerate(voltages):
            self.buffers[ch].append(v)

    def _get_channel_array(self, channel_idx: int, window_sec: float | None = None):
        data = np.array(self.buffers[channel_idx], dtype=float)
        if window_sec is not None:
            n = int(window_sec * self.fs)
            if data.size > n:
                data = data[-n:]
        return data

    # ------------------- filtrado -------------------
    def apply_filter(
        self, channel_idx: int, window_sec: float | None = None
    ) -> np.ndarray:
        x = self._get_channel_array(channel_idx, window_sec)
        if x.size < 10:
            return np.array([])
        y = signal.filtfilt(self.hp_coeff[0], self.hp_coeff[1], x)
        y = signal.filtfilt(self.lp_coeff[0], self.lp_coeff[1], y)
        y = signal.filtfilt(self.notch_coeff[0], self.notch_coeff[1], y)
        return y

    # ------------------- PSD / bandas / features -------------------
    def get_power_spectrum(
        self,
        channel_idx: int,
        window_sec: float | None = None,
        method: str = "multitaper",
    ):
        x_filt = self.apply_filter(channel_idx, window_sec)
        if x_filt.size < 4:
            return None, None
        freqs, pxx = self.dsp.compute_psd(x_filt, method=method)
        return freqs, pxx

    def get_band_power(self, channel_idx: int, window_sec: float | None = None):
        freqs, pxx = self.get_power_spectrum(channel_idx, window_sec)
        if freqs is None:
            return {}
        return self.dsp.compute_bandpower(freqs, pxx, relative=False)

    def get_rms_amplitude(self, channel_idx: int, window_sec: float | None = None):
        x = self._get_channel_array(channel_idx, window_sec)
        if x.size == 0:
            return 0.0
        return float(np.sqrt(np.mean(x ** 2)))

    def compute_features(
        self,
        channel_idx: int,
        window_sec: float | None = None,
        psd_method: str = "multitaper",
    ):
        x_filt = self.apply_filter(channel_idx, window_sec)
        if x_filt.size < 4:
            return {}
        return self.dsp.compute_features(x_filt, psd_method)
    
    def get_spectrogram(
        self,
        channel_idx: int,
        window_sec: float | None = None,
        step_sec: float | None = None,
        method: str = "multitaper",
    ):
        """
        Devuelve el espectrograma de un canal ya filtrado:

        times : (n_windows,)  en segundos
        freqs : (n_freqs,)    en Hz
        Sxx   : (n_windows, n_freqs) densidad de potencia
        """
        x_filt = self.apply_filter(channel_idx, window_sec=None)
        if x_filt.size < 4:
            return None, None, None

        return self.dsp.compute_spectrogram(
            x_filt,
            method=method,
            window_sec=window_sec,
            step_sec=step_sec,
        )


# Pequeña prueba sintética
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    proc = EEGSignalProcessor(fs=250, num_channels=4, buffer_sec=4.0, psd_window_sec=4.0)

    # 4 s de datos sintéticos alpha en CH1
    for n in range(1000):
        t = n / 250.0
        ch1 = 0.0001 * np.sin(2 * np.pi * 10 * t)
        proc.add_sample([ch1, 0.0, 0.0, 0.0])

    feats = proc.compute_features(0)
    print("RMS:", feats.get("rms"))
    print("Bandpower alpha:", feats.get("bandpower_abs", {}).get("alpha"))
    print("Relative_Bandpower beta:", feats.get("bandpower_rel", {}).get("beta"))
    print("Peak alpha freq:", feats.get("peak_alpha"))
