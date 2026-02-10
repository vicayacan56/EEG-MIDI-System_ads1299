import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

from signal_processor import SignalProcessor

FS = 250
ANIM_INTERVAL = 0.1      # s entre frames
BAND_HISTORY_SEC = 10.0  # segundos de historia visibles


def synthetic_sample(t: float):
    ch1 = 0.0001 * np.sin(2 * np.pi * 10 * t) + np.random.normal(0, 0.00002)
    ch2 = 0.0001 * np.sin(2 * np.pi * 6 * t)  + np.random.normal(0, 0.00002)
    ch3 = 0.0001 * np.sin(2 * np.pi * 20 * t) + np.random.normal(0, 0.00002)
    ch4 = np.random.normal(0, 0.00002)
    return [ch1, ch2, ch3, ch4]


class BandsDemo:
    def __init__(self):
        self.processor = SignalProcessor()
        self.fs = self.processor.fs
        self.num_channels = self.processor.num_channels

        self.current_time = 0.0

        # Historial de bandas
        self.band_time = [[] for _ in range(self.num_channels)]
        self.band_alpha = [[] for _ in range(self.num_channels)]
        self.band_beta = [[] for _ in range(self.num_channels)]

        # Figura: 4 subplots (uno por canal)
        self.fig, self.axes = plt.subplots(self.num_channels, 1, figsize=(10, 7), sharex=True)
        if self.num_channels == 1:
            self.axes = [self.axes]

        self.lines_alpha = []
        self.lines_beta = []

        for ch, ax in enumerate(self.axes):
            (line_alpha,) = ax.plot([], [], label="Alpha (8–13 Hz)")
            (line_beta,) = ax.plot([], [], label="Beta (13–30 Hz)")
            self.lines_alpha.append(line_alpha)
            self.lines_beta.append(line_beta)
            ax.set_ylabel(f"CH{ch+1}")
            ax.grid(True)
            ax.legend(loc="upper right")

        self.axes[-1].set_xlabel("Time (s)")
        self.fig.suptitle("EEG Band Power - Real-time (Alpha/Beta)", fontsize=14)

    def init_anim(self):
        for line in self.lines_alpha + self.lines_beta:
            line.set_data([], [])
        return self.lines_alpha + self.lines_beta

    def update_anim(self, frame_idx):
        # 1) Generar muestras nuevas
        n_new = max(1, int(self.fs * ANIM_INTERVAL))
        for _ in range(n_new):
            t = self.current_time
            voltages = synthetic_sample(t)
            self.processor.add_sample(voltages)
            self.current_time += 1.0 / self.fs

        # 2) Calcular bandas y actualizar historiales
        current_time = self.current_time

        for ch in range(self.num_channels):
            bands = self.processor.get_band_power(ch)
            alpha = bands.get("alpha", 0.0)
            beta = bands.get("beta", 0.0)

            self.band_time[ch].append(current_time)
            self.band_alpha[ch].append(alpha)
            self.band_beta[ch].append(beta)

            t_hist = np.array(self.band_time[ch])
            alpha_hist = np.array(self.band_alpha[ch])
            beta_hist = np.array(self.band_beta[ch])

            # Recortar historia a los últimos BAND_HISTORY_SEC segundos
            mask = t_hist >= (current_time - BAND_HISTORY_SEC)
            t_hist = t_hist[mask]
            alpha_hist = alpha_hist[mask]
            beta_hist = beta_hist[mask]

            self.band_time[ch] = list(t_hist)
            self.band_alpha[ch] = list(alpha_hist)
            self.band_beta[ch] = list(beta_hist)

            if t_hist.size < 2:
                continue

            self.lines_alpha[ch].set_data(t_hist, alpha_hist)
            self.lines_beta[ch].set_data(t_hist, beta_hist)

            ax = self.axes[ch]
            ax.set_xlim(t_hist[0], t_hist[-1])

            ymin = min(alpha_hist.min(), beta_hist.min())
            ymax = max(alpha_hist.max(), beta_hist.max())
            if ymin == ymax:
                ymin -= 1e-12
                ymax += 1e-12
            margin = 0.2 * (ymax - ymin)
            ax.set_ylim(ymin - margin, ymax + margin)

        return self.lines_alpha + self.lines_beta

    def run(self):
        anim = FuncAnimation(
            self.fig,
            self.update_anim,
            init_func=self.init_anim,
            interval=int(ANIM_INTERVAL * 1000),
            blit=False,
            cache_frame_data=False,
        )
        plt.show()


if __name__ == "__main__":
    demo = BandsDemo()
    demo.run()
