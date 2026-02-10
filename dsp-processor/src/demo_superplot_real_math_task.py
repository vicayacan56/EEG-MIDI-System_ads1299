# demo_superplot_real_math_task.py
#
# Visualización tipo "super-plot" usando datos REALES
# del dataset EEG mental arithmetic (tarea mental),
# canales: ["Fp1", "Fp2", "C3", "O1"].

import time
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import mne

from eeg_signal_processor import EEGSignalProcessor

# ---------------------------------------------------------------------
# Colormap personalizado para el espectrograma
# ---------------------------------------------------------------------
SPEC_CMAP = mcolors.LinearSegmentedColormap.from_list(
    "spec_cmap",
    [
        (0.00, "#7B7BC3"),  # azul oscuro
        (0.25, "#0040ff"),  # azul
        (0.50, "#00c060"),  # verde intenso
        (0.75, "#ffd000"),  # amarillo
        (0.85, "#ff0000"),  # rojo intenso
        (1.00, "#000000"),  # máximo (color especial)
    ],
)

# ---------------------------------------------------------------------
# Carga de EDF del dataset de tarea mental
# ---------------------------------------------------------------------
def load_math_task_eeg(
    path_edf: str,
    channels_to_use=None,
):
    print(f"Cargando EDF: {path_edf}")
    raw = mne.io.read_raw_edf(path_edf, preload=True)
    fs = float(raw.info["sfreq"])
    print(f"Frecuencia de muestreo EDF: {fs} Hz")

    if channels_to_use is None:
        channels_to_use = ["Fp1", "Fp2", "C3", "O1"]

    available = raw.ch_names
    selected = [c for c in channels_to_use if c in available]
    if len(selected) < 1:
        raise ValueError(
            f"Ninguno de los canales solicitados {channels_to_use} está en el EDF. "
            f"Canales disponibles: {available}"
        )
    if len(selected) < len(channels_to_use):
        print(
            f"[AVISO] No se han encontrado todos los canales solicitados. "
            f"Usando solo: {selected}"
        )

    raw.pick_channels(selected)
    data, times = raw[:]
    eeg_v = data.T  # (n_samples, n_channels) en voltios

    print(f"EEG cargado: {eeg_v.shape[0]} muestras, {eeg_v.shape[1]} canales.")
    print(f"Canales seleccionados: {selected}")

    return eeg_v, fs, selected


def chunk_generator_from_array(eeg_v: np.ndarray, chunk_size: int):
    """Generador de bloques (chunk_size, n_channels) a partir del array completo."""
    n_samples = eeg_v.shape[0]
    pos = 0
    while pos < n_samples:
        end = min(pos + chunk_size, n_samples)
        chunk = eeg_v[pos:end, :]
        if chunk.shape[0] == 0:
            break
        yield chunk
        pos = end


# ---------------------------------------------------------------------
# Demo de super-plot en "tiempo real" con datos reales
# ---------------------------------------------------------------------
def main():
    # ===== 1) Configuración básica y carga del EDF real =====
    EDF_PATH = r"C:\Users\PC\Documents\EEG-MIDI-System\dsp-processor\mathrecordingeeg\Subject01_1.edf"  # <-- AJUSTA ESTO
    channels = ["EEG Fp1", "EEG Fp2", "EEG C3", "EEG O1"]

    eeg_v, fs_real, selected_channels = load_math_task_eeg(
        EDF_PATH,
        channels_to_use=channels,
    )

    num_channels = eeg_v.shape[1]

    # Tiempo de “simulación en streaming”
    chunk_sec = 0.1                   # cada cuánto actualizamos la figura (100 ms)
    chunk_size = int(fs_real * chunk_sec)

    # Ventana principal de análisis (EEG tiempo + PSD + bandas)
    window_sec = 4.0                  # -> resolución frecuencial ~ 1 / 4 = 0.25 Hz

    proc = EEGSignalProcessor(
        fs=int(fs_real),
        num_channels=num_channels,
        buffer_sec=64.0,
        psd_window_sec=window_sec,
        window_type="hann",
        welch_overlap=0.5,
    )

    chunk_gen = chunk_generator_from_array(eeg_v, chunk_size)
    t_global = 0.0

    # ===== 2) FIGURA: 2x2 + subgrid para bandas =====
    plt.ion()
    fig = plt.figure(figsize=(13, 8))

    gs_main = fig.add_gridspec(
        2,
        2,
        height_ratios=[1.0, 1.2],
        width_ratios=[1.0, 1.1],
    )

    # Columna izquierda: arriba 4 subplots de EEG, abajo espectrograma cuadrado
    gs_eeg = gs_main[0, 0].subgridspec(4, 1, hspace=0.05)
    ax_time_list = [fig.add_subplot(gs_eeg[i, 0]) for i in range(4)]
    ax_spec = fig.add_subplot(gs_main[1, 0])

    # Columna derecha: PSD + subgrid bandas abs/rel
    ax_psd = fig.add_subplot(gs_main[0, 1])
    gs_bands = gs_main[1, 1].subgridspec(2, 1, height_ratios=[1.0, 1.0])
    ax_bands_abs = fig.add_subplot(gs_bands[0, 0])
    ax_bands_rel = fig.add_subplot(gs_bands[1, 0])

    # Espectrograma lo intentamos cuadrado
    try:
        ax_spec.set_box_aspect(1.0)
    except Exception:
        pass
    ax_spec.set_anchor("W")

    colors = ["C0", "C1", "C2", "C3"]

    # =========================
    # 1) EEG en el tiempo (4 ejes)
    # =========================
    time_lines = []
    FIXED_EEG_YLIM_UV = 50.0  # rango fijo ±120 µV (puedes tocar esto)
    for ch in range(num_channels):
        ax = ax_time_list[ch]
        label = selected_channels[ch] if ch < len(selected_channels) else f"Ch {ch+1}"
        line, = ax.plot([], [], lw=1, color=colors[ch])
        time_lines.append(line)

        if ch == 0:
            ax.set_title("EEG REAL filtrado (últimos 4 s)")

        # Solo el último eje con etiqueta de X
        if ch == num_channels - 1:
            ax.set_xlabel("Tiempo relativo (s)")
        else:
            ax.set_xticklabels([])

        ax.set_ylabel(f"{label}\n(µV)")
        ax.grid(True, linestyle="--", alpha=0.2)

        # Límites de eje fijos
        ax.set_xlim(0, window_sec)
        ax.set_ylim(-FIXED_EEG_YLIM_UV, FIXED_EEG_YLIM_UV)

    # Texto RMS debajo del último eje de EEG
    ax_bottom = ax_time_list[-1]
    rms_text = ax_bottom.text(
        0.5,
        -0.85,
        "",
        transform=ax_bottom.transAxes,
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
        label = selected_channels[ch] if ch < len(selected_channels) else f"Ch {ch+1}"
        line, = ax_psd.plot([], [], lw=1, color=colors[ch], label=label)
        psd_lines.append(line)

    ax_psd.set_title("PSD (multitaper) – EEG real")
    ax_psd.set_xlabel("Frecuencia (Hz)")
    ax_psd.set_ylabel("PSD (dB µV²/Hz)")
    ax_psd.set_xlim(0, 45)
    ax_psd.grid(True, which="both", linestyle="--", alpha=0.4)
    ax_psd.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.15),
        ncol=num_channels,
        fontsize=8,
    )

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

    # Y-lims de PSD fijos después del primer cálculo
    psd_ylim = None

    # ======================
    # 3) Bandas (Ch1)
    # ======================
    band_color_map = {
        "delta": "tab:blue",
        "theta": "tab:cyan",
        "alpha": "tab:green",
        "beta": "tab:red",
        "gamma": "tab:purple",
    }

    band_lines_abs = {}
    for band_name, col in band_color_map.items():
        line, = ax_bands_abs.plot([], [], label=band_name.capitalize(), color=col)
        band_lines_abs[band_name] = line

    ax_bands_abs.set_title("Potencia absoluta por banda (Ch1 real)")
    ax_bands_abs.set_xlabel("")
    ax_bands_abs.set_ylabel("Potencia absoluta (µV²)")
    ax_bands_abs.grid(True, linestyle="--", alpha=0.4)
    ax_bands_abs.legend(loc="upper right", fontsize=8)
    ax_bands_abs.set_ylim(0, 50)


    band_lines_rel = {}
    for band_name, col in band_color_map.items():
        line, = ax_bands_rel.plot([], [], label=band_name.capitalize(), color=col)
        band_lines_rel[band_name] = line

    ax_bands_rel.set_title("Potencia relativa por banda (Ch1 real)")
    ax_bands_rel.set_xlabel("Tiempo (s)")
    ax_bands_rel.set_ylabel("Potencia relativa (fracción)")
    ax_bands_rel.grid(True, linestyle="--", alpha=0.4)
    ax_bands_rel.set_ylim(0, 1.0)
    ax_bands_rel.legend(loc="upper right", fontsize=8)

    band_time = []
    band_abs_hist = {name: [] for name in band_color_map.keys()}
    band_rel_hist = {name: [] for name in band_color_map.keys()}
    band_window_vis = 60.0

    # Texto con valores ABSOLUTOS
    band_text_abs = ax_bands_abs.text(
        0.02,
        0.98,
        "",
        transform=ax_bands_abs.transAxes,
        va="top",
        ha="left",
        fontsize=9,
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.65),
        clip_on=False,
    )

    # Texto con valores RELATIVOS
    band_text_rel = ax_bands_rel.text(
        0.02,
        0.98,
        "",
        transform=ax_bands_rel.transAxes,
        va="top",
        ha="left",
        fontsize=9,
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.65),
        clip_on=False,
    )

    # Y-lims fijos para bandas absolutas (se fijan tras el primer buen rango)
    bands_abs_ylim = None

    # ======================
    # 4) Espectrograma combinado
    # ======================
    ax_spec.set_title(
        "Espectrograma EEG combinado (Ch1–Ch4, MT, últimos 6 s)",
        pad=10,
    )
    ax_spec.set_xlabel("Tiempo (s)")
    ax_spec.set_ylabel("Frecuencia (Hz)")
    ax_spec.set_ylim(0, 40)

    spec_im = None
    spec_cbar = None
    window_vis_spec = 12.0
    spec_update_every = 5   # recalcular espectrograma cada 5 iteraciones
    loop_idx = 0

    # Layout SOLO una vez
    fig.tight_layout()

    # ====================== 3) Bucle ==========================
    try:
        while True:
            try:
                eeg_chunk = next(chunk_gen)
            except StopIteration:
                print("Fin del EEG real.")
                break

            n_samples_chunk = eeg_chunk.shape[0]
            t_global += n_samples_chunk / fs_real
            loop_idx += 1

            # Introducir muestras en el procesador
            for i in range(n_samples_chunk):
                proc.add_sample(eeg_chunk[i, :].tolist())

            # --- 1) EEG en el tiempo y filtrado por canal (VENTANA) ---
            x_filt_win_list = []
            for ch in range(num_channels):
                ax = ax_time_list[ch]
                x_filt_ch = proc.apply_filter(channel_idx=ch, window_sec=window_sec)
                x_filt_win_list.append(x_filt_ch)

                if x_filt_ch.size == 0:
                    continue

                t_rel = np.linspace(
                    max(0.0, t_global - window_sec),
                    t_global,
                    x_filt_ch.size,
                )
                y_uv = x_filt_ch * 1e6  # sin offset

                time_lines[ch].set_data(t_rel - t_rel[0], y_uv)
                # límites YA fijos, no se tocan: ax.set_xlim/ylim arriba

            # --- 2) PSD multitaper + RMS + bandas (usando x_filt_win_list) ---
            feats_list = [None] * num_channels
            rms_values = [None] * num_channels
            all_psd_values_db = []
            feats_ch0 = None

            for ch in range(num_channels):
                x_win = x_filt_win_list[ch]
                if x_win is None or x_win.size < 4:
                    continue

                feats = proc.dsp.compute_features(
                    x_win,
                    psd_method="multitaper",
                )
                if not feats:
                    continue

                feats_list[ch] = feats
                freqs = feats["freqs"]
                pxx = feats["psd"]  # V²/Hz

                eps = 1e-24
                pxx_uV = pxx * 1e12
                psd_db = 10 * np.log10(pxx_uV + eps)

                psd_lines[ch].set_data(freqs, psd_db)
                all_psd_values_db.append(psd_db)

                rms_values[ch] = feats.get("rms", 0.0)

                if ch == 0:
                    feats_ch0 = feats

            if all_psd_values_db:
                all_psd_values_db = np.concatenate(all_psd_values_db)
                p5, p95 = np.percentile(all_psd_values_db, [5, 95])
                span = max(p95 - p5, 10.0)
                margin = 0.25 * span
                y_min = p5 - margin
                y_max = p95 + margin

                if psd_ylim is None:
                    psd_ylim = (y_min, y_max)  # fijamos una sola vez

                ax_psd.set_xlim(0, 45)
                ax_psd.set_ylim(*psd_ylim)

            # RMS debajo de los EEG
            rms_lines_txt = []
            for ch, rms in enumerate(rms_values):
                if rms is not None:
                    ch_label = (
                        selected_channels[ch]
                        if ch < len(selected_channels)
                        else f"Ch{ch+1}"
                    )
                    rms_lines_txt.append(f"{ch_label}: {rms*1e6:.2f} µV")
            rms_text.set_text("   ".join(rms_lines_txt))

            # --- 3) Bandas y texto de bandas (solo Ch1) ---
            if feats_ch0 is not None:
                band_abs = feats_ch0.get("bandpower_abs", {})
                band_rel = feats_ch0.get("bandpower_rel", {})

                # Historial
                t_center = t_global - window_sec / 2.0
                band_time.append(t_center)
                for name in band_abs_hist.keys():
                    power_v2 = band_abs.get(name, 0.0)
                    band_abs_hist[name].append(power_v2 / 1e-12)  # µV²
                    band_rel_hist[name].append(band_rel.get(name, 0.0))

                # Textos de bandas: ABS y REL
                lines_abs = []
                lines_rel = []
                for name in ["delta", "theta", "alpha", "beta", "gamma"]:
                    abs_uv2 = band_abs.get(name, 0.0) / 1e-12
                    rel_val = band_rel.get(name, 0.0)
                    lines_abs.append(f"{name.capitalize()}: {abs_uv2:.2f} µV²")
                    lines_rel.append(f"{name.capitalize()}: {rel_val:.2f} rel")

                band_text_abs.set_text("\n".join(lines_abs))
                band_text_rel.set_text("\n".join(lines_rel))

                # Picos por banda (Ch1) para el panel PSD
                peak_lines = []
                for name, (f_low, f_high) in proc.dsp.bands.items():
                    peak_key = f"peak_{name}"
                    f_peak = feats_ch0.get(peak_key, None)
                    if f_peak is None:
                        freqs = feats_ch0["freqs"]
                        pxx = feats_ch0["psd"]
                        mask = (freqs >= f_low) & (freqs <= f_high)
                        if np.any(mask):
                            idx = np.argmax(pxx[mask])
                            f_peak = freqs[mask][idx]
                    if f_peak is not None:
                        peak_lines.append(f"{name.capitalize()} peak: {f_peak:.1f} Hz")
                feat_text.set_text("\n".join(peak_lines))

                # Actualizar curvas de bandas en el tiempo
                times_arr = np.array(band_time)
                mask_hist = times_arr >= (t_global - band_window_vis)
                if np.any(mask_hist):
                    times_plot = times_arr[mask_hist]

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
                         ax_bands_abs.set_ylim(0, 50)

                    for name in band_rel_hist.keys():
                        vals_rel = np.array(band_rel_hist[name])[mask_hist]
                        band_lines_rel[name].set_data(times_plot, vals_rel)
                    ax_bands_rel.set_xlim(
                        max(0.0, t_global - band_window_vis), t_global
                    )
                    ax_bands_rel.set_ylim(0.0, 1.0)

            # --- 4) Espectrograma combinado (cada N iteraciones) ---
            if loop_idx % spec_update_every == 0:
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
                        window_sec=window_sec,
                        step_sec=None,
                        log_scale=False,
                    )
                    if t_tmp is None or f_tmp is None or Sxx_tmp is None:
                        continue

                    if times is None:
                        times = t_tmp
                        freqs_spec = f_tmp
                    else:
                        if not np.allclose(times, t_tmp) or not np.allclose(
                            freqs_spec, f_tmp
                        ):
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

                    Sxx_uV = Sxx_win * 1e12
                    eps = 1e-24
                    Sxx_db = 10 * np.log10(Sxx_uV + eps)

                    ax_spec.cla()
                    ax_spec.set_title(
                        f"Espectrograma EEG combinado (Ch1–Ch4, MT, últimos {window_vis_spec:.0f} s)",
                        pad=10,
                    )
                    ax_spec.set_xlabel("Tiempo (s)")
                    ax_spec.set_ylabel("Frecuencia (Hz)")
                    ax_spec.set_ylim(0, 40)
                    ax_spec.set_anchor("W")
                    try:
                        ax_spec.set_box_aspect(1.0)
                    except Exception:
                        pass

                    spec_im = ax_spec.pcolormesh(
                        times_win,
                        freqs_spec,
                        Sxx_db.T,
                        shading="gouraud",
                        cmap=SPEC_CMAP,
                        vmin=-90,
                        vmax=-10,
                    )
                    ax_spec.set_xlim(times_win.min(), times_win.max())

                    if spec_cbar is None:
                        spec_cbar = fig.colorbar(
                            spec_im,
                            ax=ax_spec,
                            label="PSD (dB µV²/Hz)",
                        )
                    else:
                        spec_cbar.update_normal(spec_im)

            # Nada de tight_layout() aquí: ya está hecho antes
            fig.canvas.draw()
            fig.canvas.flush_events()

            # Control de “fluidez”: si quieres más fps, baja chunk_sec
            time.sleep(chunk_sec * 0.9)

    except KeyboardInterrupt:
        print("Detenido por el usuario.")


if __name__ == "__main__":
    main()
