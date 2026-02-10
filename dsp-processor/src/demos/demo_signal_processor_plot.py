# src/demo_signal_processor_plot.py

import numpy as np
from signal_processor import SignalProcessor
from plot_utils import plot_time_series_multichannel, plot_psd_multichannel,plot_band_evolution, show_all


def main():
    processor = SignalProcessor()
    fs = processor.fs
    num_channels = processor.num_channels

    # Generar 4 s de datos sintéticos:
    #   CH1: 10 Hz (alpha)
    #   CH2: 6 Hz (theta)
    #   CH3: 20 Hz (beta)
    #   CH4: ruido
    num_samples = 4 * fs
     # Históricos para bandas
    alpha_hist = [[] for _ in range(num_channels)]
    beta_hist  = [[] for _ in range(num_channels)]

    for n in range(num_samples):
        t = n / fs

        ch1 = 0.0001 * np.sin(2 * np.pi * 10 * t) + np.random.normal(0, 0.00002)
        ch2 = 0.0001 * np.sin(2 * np.pi * 6 * t)  + np.random.normal(0, 0.00002)
        ch3 = 0.0001 * np.sin(2 * np.pi * 20 * t) + np.random.normal(0, 0.00002)
        ch4 = np.random.normal(0, 0.00002)

        processor.add_sample([ch1, ch2, ch3, ch4])

        # Registrar evolución de bandas
        for ch in range(num_channels):
            bands = processor.get_band_power(ch)    
            alpha_hist[ch].append(bands.get("alpha", 0))
            beta_hist[ch].append(bands.get("beta", 0))

    # ---------- Señales en el tiempo (crudas) ----------
    # Construimos un array (N_muestras, N_canales) a partir de los deques
    data_time = np.column_stack([
        np.array(processor.buffers[ch]) for ch in range(num_channels)
    ])

    plot_time_series_multichannel(
        data_time,
        fs,
        title="Time series - raw (4 channels)"
    )

    # ---------- PSD por canal ----------
    freqs_list = []
    pxx_list = []

    for ch in range(num_channels):
        freqs, pxx = processor.get_power_spectrum(ch)
        if freqs is None:
            # Si por lo que sea no hay suficientes muestras, metemos vectores vacíos
            freqs = np.array([])
            pxx = np.array([])
        freqs_list.append(freqs)
        pxx_list.append(pxx)

    plot_psd_multichannel(
        freqs_list,
        pxx_list,
        title="Welch PSD - 4 channels"
    )
    # ---------- Evolución Alpha/Beta ----------
    plot_band_evolution(
        alpha_hist,
        beta_hist,
        fs,
        title="Evolution of Alpha/Beta Bands (4 channels)"
    )

    show_all()


if __name__ == "__main__":
    main()
