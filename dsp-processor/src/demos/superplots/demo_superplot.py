# demo_superplot.py
import time
import numpy as np
import matplotlib.pyplot as plt

from eeg_signal_processor import EEGSignalProcessor


# ------------------------------------------------------------
# Simulación de EEG multicanal realista y variable en el tiempo
# ------------------------------------------------------------
def simulate_eeg_chunk_multi(
    t_start: float,
    chunk_size: int,
    fs: float,
    num_channels: int = 4,
) -> np.ndarray:
    """
    Genera un trozo de EEG sintético multicanal de tamaño
    (chunk_size, num_channels). Devuelve valores en voltios.
    """
    t = t_start + np.arange(chunk_size) / fs
    data = np.zeros((chunk_size, num_channels), dtype=float)

    # CH1: "anestesia": delta + alpha modulada + gamma al despertar
    base_noise = 5e-6 * np.random.randn(chunk_size)
    delta = 20e-6 * np.sin(2 * np.pi * 2 * t)
    alpha_env = 0.5 * (1 + np.sin(2 * np.pi * 0.05 * t))  # 0..1
    alpha = alpha_env * 15e-6 * np.sin(2 * np.pi * 10 * t)
    gamma_env = (t > 30).astype(float)                    # a partir de 30 s
    gamma = gamma_env * 8e-6 * np.sin(2 * np.pi * 35 * t)
    data[:, 0] = base_noise + delta + alpha + gamma

    # CH2: más lento, dominado por delta + theta
    noise2 = 4e-6 * np.random.randn(chunk_size)
    theta = 10e-6 * np.sin(2 * np.pi * 6 * t)
    data[:, 1] = noise2 + 25e-6 * np.sin(2 * np.pi * 1.5 * t) + theta

    # CH3: bursts de beta (20 Hz) intermitentes (EMG / arousal)
    noise3 = 6e-6 * np.random.randn(chunk_size)
    burst_env = ((np.sin(2 * np.pi * 0.02 * t) > 0.7)).astype(float)  # ráfagas
    beta = burst_env * 15e-6 * np.sin(2 * np.pi * 20 * t)
    data[:, 2] = noise3 + beta

    # CH4: canal "ruidoso": mezcla de todo + un poco de 50 Hz residual
    noise4 = 8e-6 * np.random.randn(chunk_size)
    mix = (
        10e-6 * np.sin(2 * np.pi * 3 * t)
        + 6e-6 * np.sin(2 * np.pi * 9 * t)
        + 5e-6 * np.sin(2 * np.pi * 18 * t)
    )
    hum50 = 2e-6 * np.sin(2 * np.pi * 50 * t)
    data[:, 3] = noise4 + mix + hum50

    return data


# ------------------------------------------------------------
# Demo de super-plot en tiempo real
# ------------------------------------------------------------
def main():
    fs = 250
    num_channels = 4

    proc = EEGSignalProcessor(
        fs=fs,
        num_channels=num_channels,
        buffer_sec=64.0,     # buffer circular de 64 s
        psd_window_sec=4.0,  # ventana de 4 s para PSD/espectrograma
        window_type="hann",
        welch_overlap=0.5,
    )

    chunk_sec = 0.1
    chunk_size = int(chunk_sec * fs)
    t_global = 0.0
    window_sec = 4.0

    # ----------- FIGURA (nuevo layout con 4 filas) ----------- #
    plt.ion()
    fig, axes = plt.subplot_mosaic(
        """
        TP
        .A
        .R
        SS
        """,
        figsize=(14, 9),
        gridspec_kw={"height_ratios": [1.0, 0.55, 0.55, 1.4]},
    )
    ax_time = axes["T"]
    ax_psd = axes["P"]
    ax_bands_abs = axes["A"]
    ax_bands_rel = axes["R"]
    ax_spec = axes["S"]

    colors = ["C0", "C1", "C2", "C3"]

    # ======================
    # 1) EEG en el tiempo
    # ======================
    time_lines = []
    for ch in range(num_channels):
        line, = ax_time.plot([], [], lw=1, color=colors[ch], label=f"Ch {ch+1}")
        time_lines.append(line)

    ax_time.set_title("EEG filtrado (últimos 4 s)")
    ax_time.set_xlabel("Tiempo relativo (s)")
    ax_time.set_ylabel("Amplitud (µV)")
    ax_time.set_xlim(0, window_sec)
    ax_time.legend(loc="upper right", fontsize=8)

    # Texto de RMS de los 4 canales un poco más abajo
    rms_text = ax_time.text(
        0.5,
        -0.38,   # antes -0.25 -> lo bajamos más
        "",
        transform=ax_time.transAxes,
        va="top",
        ha="center",
        fontsize=9,
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.7),
        clip_on=False,
    )

    # ======================
    # 2) PSD multitaper
    # ======================
    psd_lines = []
    for ch in range(num_channels):
        line, = ax_psd.plot([], [], lw=1, color=colors[ch], label=f"Ch {ch+1}")
        psd_lines.append(line)

    ax_psd.set_title("PSD (multitaper)")
    ax_psd.set_xlabel("Frecuencia (Hz)")
    ax_psd.set_ylabel("PSD (dB µV²/Hz)")
    ax_psd.set_xlim(0, 15)  # zoom 0–25 Hz
    ax_psd.grid(True, which="both", linestyle="--", alpha=0.4)
    ax_psd.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.25),
        ncol=num_channels,
        fontsize=8,
    )

    # Texto en PSD con peak de todas las bandas
    feat_text = ax_psd.text(
        0.70,
        0.95,
        "",
        transform=ax_psd.transAxes,
        va="top",
        ha="left",
        fontsize=9,
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.7),
        clip_on=False,
    )

    # ======================
    # 3) Bandas absolutas y relativas (Ch1)
    # ======================
    band_color_map = {
        "delta": "tab:blue",
        "theta": "tab:cyan",
        "alpha": "tab:green",
        "beta": "tab:red",
        "gamma": "tab:purple",
    }

    # --- Potencia absoluta ---
    band_lines_abs = {}
    for band_name, col in band_color_map.items():
        line, = ax_bands_abs.plot([], [], label=band_name.capitalize(), color=col)
        band_lines_abs[band_name] = line

    ax_bands_abs.set_title("Potencia absoluta por banda (Ch1)")
    ax_bands_abs.set_xlabel("Tiempo (s)")
    ax_bands_abs.set_ylabel("Potencia absoluta (µV²)")
    ax_bands_abs.grid(True, linestyle="--", alpha=0.4)
    ax_bands_abs.legend(loc="upper right", fontsize=8)

    # --- Potencia relativa ---
    band_lines_rel = {}
    for band_name, col in band_color_map.items():
        line, = ax_bands_rel.plot(
            [], [],
            label=band_name.capitalize(),
            color=col,
        )
        band_lines_rel[band_name] = line

    ax_bands_rel.set_title("Potencia relativa por banda (Ch1)")
    ax_bands_rel.set_xlabel("Tiempo (s)")
    ax_bands_rel.set_ylabel("Potencia relativa (fracción)")
    ax_bands_rel.grid(True, linestyle="--", alpha=0.4)
    ax_bands_rel.set_ylim(0, 1.0)
    ax_bands_rel.legend(loc="upper right", fontsize=8)

    # Historial bandas
    band_time = []
    band_abs_hist = {name: [] for name in band_color_map.keys()}
    band_rel_hist = {name: [] for name in band_color_map.keys()}
    band_window_vis = 60.0  # historia visible (s)

    # Texto con valores actuales abs+rel en panel relativo
    band_text = ax_bands_rel.text(
        -0.40,
        0.95,
        "",
        transform=ax_bands_rel.transAxes,
        va="top",
        ha="left",
        fontsize=9,
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.65),
        clip_on=False,
    )

    # ======================
    # 4) Espectrograma combinado
    # ======================
    ax_spec.set_title("Espectrograma EEG combinado (Ch1–Ch4, MT, últimos 12 s)")
    ax_spec.set_xlabel("Tiempo (s)")
    ax_spec.set_ylabel("Frecuencia (Hz)")
    ax_spec.set_ylim(0, 40)

    spec_im = None
    spec_cbar = None
    window_vis_spec = 12.0  # segundos visibles en espectrograma

    fig.tight_layout()

    # ----------- bucle "tiempo real" ----------- #
    try:
        while True:
            # 1) Generar nuevo trozo de EEG
            eeg_chunk = simulate_eeg_chunk_multi(
                t_global,
                chunk_size,
                fs,
                num_channels=num_channels,
            )
            t_global += chunk_sec

            for i in range(chunk_size):
                proc.add_sample(eeg_chunk[i, :].tolist())

            # 2) Señal en el tiempo
            offset_uv = 60.0
            y_min_glob, y_max_glob = np.inf, -np.inf

            for ch in range(num_channels):
                x_filt_ch = proc.apply_filter(channel_idx=ch, window_sec=window_sec)
                if x_filt_ch.size == 0:
                    continue

                t_rel = np.linspace(
                    max(0.0, t_global - window_sec),
                    t_global,
                    x_filt_ch.size,
                )
                y_uv = x_filt_ch * 1e6 + ch * offset_uv
                time_lines[ch].set_data(t_rel - t_rel[0], y_uv)

                y_min_glob = min(y_min_glob, y_uv.min())
                y_max_glob = max(y_max_glob, y_uv.max())

            if y_min_glob < y_max_glob:
                ax_time.set_ylim(y_min_glob - 10, y_max_glob + 10)

            # 3) PSD multitaper + RMS + bandas CH1
            global_psd_min, global_psd_max = np.inf, -np.inf
            feats_ch0 = None
            freqs_ch0 = None
            pxx_ch0 = None
            rms_values = [None] * num_channels

            for ch in range(num_channels):
                feats = proc.compute_features(
                    channel_idx=ch,
                    window_sec=window_sec,
                    psd_method="multitaper",
                )
                if not feats:
                    continue

                freqs = feats["freqs"]
                pxx = feats["psd"]
                eps = 1e-12
                ref = 1e-12

                psd_db = 10 * np.log10((pxx + eps) / ref)

                psd_lines[ch].set_data(freqs, psd_db)
                global_psd_min = min(global_psd_min, psd_db.min())
                global_psd_max = max(global_psd_max, psd_db.max())

                rms_values[ch] = feats.get("rms", 0.0)

                if ch == 0:
                    feats_ch0 = feats
                    freqs_ch0 = freqs
                    pxx_ch0 = pxx

            if global_psd_min < global_psd_max:
                ax_psd.set_xlim(0, 25)
                ax_psd.set_ylim(global_psd_min - 5, global_psd_max + 5)

            # RMS debajo del EEG filtrado
            rms_lines_txt = []
            for ch, rms in enumerate(rms_values):
                if rms is not None:
                    rms_lines_txt.append(f"Ch{ch+1} RMS: {rms*1e6:.2f} µV")
            rms_text.set_text("   ".join(rms_lines_txt))

            # Bandas (CH1) para historia, bandas y texto
            if feats_ch0 is not None:
                band_abs = feats_ch0.get("bandpower_abs", {})
                band_rel = feats_ch0.get("bandpower_rel", {})

                # Guardar historia
                t_center = t_global - window_sec / 2.0
                band_time.append(t_center)
                for name in band_abs_hist.keys():
                    power_v2 = band_abs.get(name, 0.0)
                    band_abs_hist[name].append(power_v2 / 1e-12)  # a µV²
                    band_rel_hist[name].append(band_rel.get(name, 0.0))

                # Actualizar texto de bandas (en panel relativo)
                band_text_lines = []
                for name in ["delta", "theta", "alpha", "beta", "gamma"]:
                    abs_uv2 = band_abs.get(name, 0.0) / 1e-12
                    rel_val = band_rel.get(name, 0.0)
                    band_text_lines.append(
                        f"{name.capitalize()}: {abs_uv2:.2f} µV², {rel_val:.2f} rel"
                    )
                band_text.set_text("\n".join(band_text_lines))

                # ==== Picos por banda en PSD (CH1) ====
                peak_lines = []
                if freqs_ch0 is not None and pxx_ch0 is not None:
                    freqs = freqs_ch0
                    pxx = pxx_ch0
                    for name, (f_low, f_high) in proc.dsp.bands.items():
                        mask = (freqs >= f_low) & (freqs <= f_high)
                        if not np.any(mask):
                            continue
                        idx = np.argmax(pxx[mask])
                        f_peak = freqs[mask][idx]
                        peak_lines.append(f"{name.capitalize()} peak: {f_peak:.1f} Hz")
                feat_text.set_text("\n".join(peak_lines))

                # ==== Actualizar gráficos de bandas ====
                times_arr = np.array(band_time)
                mask_hist = times_arr >= (t_global - band_window_vis)
                if np.any(mask_hist):
                    times_plot = times_arr[mask_hist]

                    # Absolutas
                    band_min, band_max = np.inf, -np.inf
                    for name in band_abs_hist.keys():
                        vals_abs = np.array(band_abs_hist[name])[mask_hist]
                        band_lines_abs[name].set_data(times_plot, vals_abs)
                        if vals_abs.size > 0:
                            band_min = min(band_min, vals_abs.min())
                            band_max = max(band_max, vals_abs.max())

                    ax_bands_abs.set_xlim(
                        max(0.0, t_global - band_window_vis), t_global
                    )
                    if band_min < band_max:
                        ax_bands_abs.set_ylim(band_min * 0.9, band_max * 1.1)

                    # Relativas
                    for name in band_rel_hist.keys():
                        vals_rel = np.array(band_rel_hist[name])[mask_hist]
                        band_lines_rel[name].set_data(times_plot, vals_rel)

                    ax_bands_rel.set_xlim(
                        max(0.0, t_global - band_window_vis), t_global
                    )
                    ax_bands_rel.set_ylim(0.0, 1.0)

            # 4) Espectrograma combinado multitaper
            times = None
            freqs_spec = None
            Sxx_list = []

            for ch in range(num_channels):
                x_filt_full = proc.apply_filter(channel_idx=ch, window_sec=None)
                if x_filt_full.size == 0:
                    continue

                t_tmp, f_tmp, Sxx_tmp = proc.dsp.compute_spectrogram(
                    x_filt_full,
                    method="multitaper",
                    window_sec=4.0,
                    step_sec=None,
                    log_scale=False,
                )
                if t_tmp is None or f_tmp is None or Sxx_tmp is None:
                    continue

                if times is None:
                    times = t_tmp
                    freqs_spec = f_tmp
                else:
                    if not np.allclose(times, t_tmp) or not np.allclose(freqs_spec, f_tmp):
                        continue

                Sxx_list.append(Sxx_tmp)

            if times is not None and freqs_spec is not None and len(Sxx_list) > 0:
                Sxx_stack = np.stack(Sxx_list, axis=0)
                Sxx_mean = Sxx_stack.mean(axis=0)

                t_max = times.max()
                t_min = max(times.min(), t_max - window_vis_spec)
                mask = times >= t_min
                times_win = times[mask]
                Sxx_win = Sxx_mean[mask, :]

                eps = 1e-12
                ref = 1e-12
                Sxx_db = 10 * np.log10((Sxx_win + eps) / ref)

                ax_spec.cla()
                ax_spec.set_title(
                    f"Espectrograma EEG combinado (Ch1–Ch4, MT, últimos {window_vis_spec:.0f} s)"
                )
                ax_spec.set_xlabel("Tiempo (s)")
                ax_spec.set_ylabel("Frecuencia (Hz)")

                spec_im = ax_spec.pcolormesh(
                    times_win,
                    freqs_spec,
                    Sxx_db.T,
                    shading="gouraud",
                    cmap="inferno",
                )
                ax_spec.set_ylim(0, 40)
                ax_spec.set_xlim(times_win.min(), times_win.max())

                if spec_cbar is None:
                    spec_cbar = fig.colorbar(
                        spec_im,
                        ax=ax_spec,
                        label="PSD (dB µV²/Hz)",
                    )
                else:
                    spec_cbar.update_normal(spec_im)

            # refrescar figura
            fig.canvas.draw()
            fig.canvas.flush_events()
            time.sleep(chunk_sec * 0.9)

    except KeyboardInterrupt:
        print("Detenido por el usuario.")


if __name__ == "__main__":
    main()
