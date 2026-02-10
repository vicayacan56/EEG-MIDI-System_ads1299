# src/demo_realtime_dashboard.py

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

from signal_processor import SignalProcessor

# ---------------- CONFIGURACIÓN GLOBAL ----------------

FS = 250
ANIM_INTERVAL = 0.05      # s entre frames (~50 ms)
WINDOW_SEC = 4.0          # segundos visibles en el time series
BAND_HISTORY_SEC = 10.0   # segundos visibles en la evolución de bandas


def synthetic_sample(t: float):
    """
    Genera una muestra sintética de 4 canales:
      CH1: 10 Hz (alpha)
      CH2: 6 Hz (theta)
      CH3: 20 Hz (beta)
      CH4: ruido
    """
    ch1 = 0.0001 * np.sin(2 * np.pi * 10 * t) + np.random.normal(0, 0.00002)
    ch2 = 0.0001 * np.sin(2 * np.pi * 6 * t)  + np.random.normal(0, 0.00002)
    ch3 = 0.0001 * np.sin(2 * np.pi * 20 * t) + np.random.normal(0, 0.00002)
    ch4 = np.random.normal(0, 0.00002)
    return [ch1, ch2, ch3, ch4]


class RealtimeDashboard:
    def __init__(self):
        # ---------- Procesador de señal compartido ----------
        self.processor = SignalProcessor()
        self.fs = self.processor.fs
        self.num_channels = self.processor.num_channels

        # Tiempo “simulado” y muestras
        self.current_time = 0.0

        # Ventana para el time series
        self.window_samples = int(WINDOW_SEC * self.fs)

        # Historial de bandas
        self.band_time  = [[] for _ in range(self.num_channels)]
        self.band_alpha = [[] for _ in range(self.num_channels)]
        self.band_beta  = [[] for _ in range(self.num_channels)]

        # ---------- Tema estilo VS Code ----------
        # Colores base
        bg_window = "#1e1e1e"   # fondo ventana VS Code
        bg_axes   = "#252526"   # paneles
        fg_main   = "#d4d4d4"   # texto principal
        grid_col  = "#3c3c3c"

        plt.rcParams.update({
            "figure.facecolor":  bg_window,
            "axes.facecolor":    bg_axes,
            "axes.edgecolor":    fg_main,
            "axes.labelcolor":   fg_main,
            "xtick.color":       fg_main,
            "ytick.color":       fg_main,
            "grid.color":        grid_col,
            "grid.alpha":        0.6,
            "axes.titlesize":    11,
            "axes.labelsize":    10,
            "xtick.labelsize":   9,
            "ytick.labelsize":   9,
            "legend.fontsize":   8,
        })

        # Colores “neón” suaves por canal (time + PSD)
        self.channel_colors = [
            "#4FC3F7",  # azul-cyan
            "#FFB74D",  # naranja suave
            "#81C784",  # verde
            "#E57373",  # rojo
        ]

        # Bandas
        self.alpha_color = "#BA68C8"  # morado
        self.beta_color  = "#FFD54F"  # amarillo

        # ---------- Figura tipo dashboard: 4 filas × 3 columnas ----------
        self.fig, axes = plt.subplots(
            self.num_channels, 3,
            figsize=(15, 8),
            constrained_layout=True   # mejor que tight_layout en dashboards
        )
        if self.num_channels == 1:
            axes = np.array([axes])

        self.ax_time = axes[:, 0]
        self.ax_psd  = axes[:, 1]
        self.ax_band = axes[:, 2]

        self.lines_time  = []
        self.lines_psd   = []
        self.lines_alpha = []
        self.lines_beta  = []

        # ---------- TIME SERIES ----------
        for ch in range(self.num_channels):
            ax = self.ax_time[ch]
            color = self.channel_colors[ch % len(self.channel_colors)]
            (line,) = ax.plot([], [], lw=1.4, color=color)
            self.lines_time.append(line)
            ax.set_ylabel(f"CH{ch+1}\n(V)")
            ax.grid(True, linestyle="--", linewidth=0.6)
        self.ax_time[-1].set_xlabel("Time (s)")

        # ---------- PSD ----------
        for ch in range(self.num_channels):
            ax = self.ax_psd[ch]
            color = self.channel_colors[ch % len(self.channel_colors)]
            (line,) = ax.semilogy([], [], lw=1.4, color=color)
            self.lines_psd.append(line)
            ax.set_ylabel(f"CH{ch+1}")
            ax.grid(True, which="both", ls="--", linewidth=0.6)
            ax.set_xlim(0, 50)  # 0–50 Hz
        self.ax_psd[-1].set_xlabel("Frequency (Hz)")

        # ---------- BANDAS ----------
        for ch in range(self.num_channels):
            ax = self.ax_band[ch]
            (line_alpha,) = ax.plot(
                [], [], label="Alpha (8–13 Hz)",
                color=self.alpha_color, lw=1.5
            )
            (line_beta,) = ax.plot(
                [], [], label="Beta (13–30 Hz)",
                color=self.beta_color, lw=1.5, linestyle="--"
            )
            self.lines_alpha.append(line_alpha)
            self.lines_beta.append(line_beta)
            ax.set_ylabel(f"CH{ch+1}")
            ax.grid(True, linestyle="--", linewidth=0.6)
            ax.legend(loc="upper right", framealpha=0.35, facecolor=bg_axes)
        self.ax_band[-1].set_xlabel("Time (s)")

        self.fig.suptitle(
            "EEG Real-time Dashboard - Time / PSD / Bands",
            fontsize=14, fontweight="bold", color=fg_main
        )

        self.anim = None


    # ---------- Animación: inicialización ----------

    def init_anim(self):
        for line in self.lines_time:
            line.set_data([], [])
        for line in self.lines_psd:
            line.set_data([], [])
        for line in self.lines_alpha + self.lines_beta:
            line.set_data([], [])
        return self.lines_time + self.lines_psd + self.lines_alpha + self.lines_beta

    # ---------- Animación: actualización ----------

    def update_anim(self, frame_idx):
        # 1) Generar nuevas muestras
        n_new = max(1, int(self.fs * ANIM_INTERVAL))
        for _ in range(n_new):
            t = self.current_time
            voltages = synthetic_sample(t)
            self.processor.add_sample(voltages)
            self.current_time += 1.0 / self.fs

        buffers = self.processor.buffers
        n_available = len(buffers[0])
        if n_available < 10:
            return self.lines_time + self.lines_psd + self.lines_alpha + self.lines_beta

        # ===================== TIME SERIES =====================
        n = min(n_available, self.window_samples)
        data = np.column_stack([
            np.array(buffers[ch])[-n:] for ch in range(self.num_channels)
        ])
        t_vec = np.arange(-n, 0) / self.fs  # [-WINDOW_SEC, 0)

        for ch in range(self.num_channels):
            self.lines_time[ch].set_data(t_vec, data[:, ch])
            ax = self.ax_time[ch]
            ax.set_xlim(t_vec[0], t_vec[-1])

            ymin = data[:, ch].min()
            ymax = data[:, ch].max()
            if ymin == ymax:
                ymin -= 1e-6
                ymax += 1e-6
            margin = 0.2 * (ymax - ymin)
            ax.set_ylim(ymin - margin, ymax + margin)

        # ===================== PSD =====================
        for ch in range(self.num_channels):
            freqs, pxx = self.processor.get_power_spectrum(ch)
            if freqs is None:
                continue

            self.lines_psd[ch].set_data(freqs, pxx)

            ax = self.ax_psd[ch]
            ax.set_xlim(0, 50)
            pxx_pos = pxx[pxx > 0]
            if pxx_pos.size > 0:
                ymin = pxx_pos.min()
                ymax = pxx_pos.max()
                if ymin == ymax:
                    ymin *= 0.5
                    ymax *= 1.5
                ax.set_ylim(ymin, ymax)

        # ===================== BANDAS (Alpha / Beta) =====================
        current_time = self.current_time

        for ch in range(self.num_channels):
            bands = self.processor.get_band_power(ch)
            alpha = bands.get("alpha", 0.0)
            beta  = bands.get("beta", 0.0)

            self.band_time[ch].append(current_time)
            self.band_alpha[ch].append(alpha)
            self.band_beta[ch].append(beta)

            t_hist = np.array(self.band_time[ch])
            alpha_hist = np.array(self.band_alpha[ch])
            beta_hist  = np.array(self.band_beta[ch])

            mask = t_hist >= (current_time - BAND_HISTORY_SEC)
            t_hist = t_hist[mask]
            alpha_hist = alpha_hist[mask]
            beta_hist  = beta_hist[mask]

            self.band_time[ch]  = list(t_hist)
            self.band_alpha[ch] = list(alpha_hist)
            self.band_beta[ch]  = list(beta_hist)

            if t_hist.size < 2:
                continue

            self.lines_alpha[ch].set_data(t_hist, alpha_hist)
            self.lines_beta[ch].set_data(t_hist, beta_hist)

            axb = self.ax_band[ch]
            axb.set_xlim(t_hist[0], t_hist[-1])

            ymin_b = min(alpha_hist.min(), beta_hist.min())
            ymax_b = max(alpha_hist.max(), beta_hist.max())
            if ymin_b == ymax_b:
                ymin_b -= 1e-12
                ymax_b += 1e-12
            margin_b = 0.2 * (ymax_b - ymin_b)
            axb.set_ylim(ymin_b - margin_b, ymax_b + margin_b)

        return self.lines_time + self.lines_psd + self.lines_alpha + self.lines_beta

    # ---------- Ejecución ----------

    def run(self):
        self.anim = FuncAnimation(
            self.fig,
            self.update_anim,
            init_func=self.init_anim,
            interval=int(ANIM_INTERVAL * 1000),
            blit=False,
            cache_frame_data=False,
        )
        plt.show()


if __name__ == "__main__":
    dashboard = RealtimeDashboard()
    dashboard.run()
