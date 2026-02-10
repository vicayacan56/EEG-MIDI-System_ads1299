# src/plot_utils.py

import numpy as np
import matplotlib.pyplot as plt
from typing import Sequence, List


def plot_time_series_multichannel(
    data: np.ndarray,
    fs: float,
    title: str = "Time series (all channels)",
    ch_labels: List[str] | None = None
) -> None:
    """
    Pinta las 4 señales en el dominio del tiempo (una por subgráfico).

    data: array (N_muestras, N_canales)
    fs: frecuencia de muestreo
    """
    data = np.asarray(data)
    n_samples, n_channels = data.shape
    t = np.arange(n_samples) / fs

    if ch_labels is None:
        ch_labels = [f"CH{i+1}" for i in range(n_channels)]

    fig, axes = plt.subplots(n_channels, 1, sharex=True, figsize=(8, 6))
    fig.suptitle(title)

    if n_channels == 1:
        axes = [axes]

    for ch in range(n_channels):
        axes[ch].plot(t, data[:, ch])
        axes[ch].set_ylabel(ch_labels[ch])
        axes[ch].grid(True)

    axes[-1].set_xlabel("Time (s)")
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])


def plot_psd_multichannel(
    freqs_list: List[Sequence[float]],
    pxx_list: List[Sequence[float]],
    title: str = "Power Spectral Density (all channels)",
    ch_labels: List[str] | None = None
) -> None:
    """
    Pinta la PSD de varios canales (uno por subgráfico).

    freqs_list: lista de vectores de frecuencias (uno por canal)
    pxx_list: lista de PSDs (uno por canal)
    """
    n_channels = len(freqs_list)

    if ch_labels is None:
        ch_labels = [f"CH{i+1}" for i in range(n_channels)]

    fig, axes = plt.subplots(n_channels, 1, sharex=True, figsize=(8, 6))
    fig.suptitle(title)

    if n_channels == 1:
        axes = [axes]

    for ch in range(n_channels):
        freqs = np.asarray(freqs_list[ch])
        pxx = np.asarray(pxx_list[ch])

        axes[ch].semilogy(freqs, pxx)
        axes[ch].set_ylabel(ch_labels[ch])
        axes[ch].grid(True, which="both", ls="--")

    axes[-1].set_xlabel("Frequency (Hz)")
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])

def plot_band_evolution(alpha_hist, beta_hist, fs, title="Alpha/Beta evolution"):
    """
    Pinta la evolución temporal de las bandas alpha y beta.
    alpha_hist y beta_hist son listas de listas:
        alpha_hist[ch][t]
        beta_hist[ch][t]
    """
    import numpy as np
    import matplotlib.pyplot as plt

    alpha_hist = np.asarray(alpha_hist)  # shape: (num_channels, T)
    beta_hist = np.asarray(beta_hist)

    num_channels, T = alpha_hist.shape
    t = np.arange(T) / fs

    fig, axes = plt.subplots(num_channels, 1, sharex=True, figsize=(8, 6))
    fig.suptitle(title)

    if num_channels == 1:
        axes = [axes]

    for ch in range(num_channels):
        axes[ch].plot(t, alpha_hist[ch], label="Alpha (8–13 Hz)")
        axes[ch].plot(t, beta_hist[ch], label="Beta (13–30 Hz)")
        axes[ch].set_ylabel(f"CH{ch+1}")
        axes[ch].grid(True)
        axes[ch].legend()

    axes[-1].set_xlabel("Time (s)")
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])



def show_all():
    """Muestra todas las figuras pendientes."""
    plt.show()
