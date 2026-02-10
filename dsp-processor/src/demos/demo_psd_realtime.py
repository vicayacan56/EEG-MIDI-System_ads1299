import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

from signal_processor import SignalProcessor

FS = 250
ANIM_INTERVAL = 0.1   # s entre frames (100 ms)


def synthetic_sample(t: float):
    ch1 = 0.0001 * np.sin(2 * np.pi * 2 * t) + np.random.normal(0, 0.00002)
    ch2 = 0.0001 * np.sin(2 * np.pi * 6 * t)  + np.random.normal(0, 0.00002)
    ch3 = 0.0001 * np.sin(2 * np.pi * 20 * t) + np.random.normal(0, 0.00002)
    ch4 = np.random.normal(0, 0.00002)
    return [ch1, ch2, ch3, ch4]


class PSDDemo:
    def __init__(self):
        self.processor = SignalProcessor()
        self.fs = self.processor.fs
        self.num_channels = self.processor.num_channels

        self.current_time = 0.0

        # Figura: 4 subplots (uno por canal)
        self.fig, self.axes = plt.subplots(self.num_channels, 1, figsize=(10, 7), sharex=True)
        if self.num_channels == 1:
            self.axes = [self.axes]

        self.lines = []
        for ch, ax in enumerate(self.axes):
            (line,) = ax.semilogy([], [], lw=1)
            self.lines.append(line)
            ax.set_ylabel(f"CH{ch+1}")
            ax.grid(True, which="both", ls="--")
            ax.set_xlim(0, 50)  # solo 0–50 Hz

        self.axes[-1].set_xlabel("Frequency (Hz)")
        self.fig.suptitle("EEG PSD - Real-time (4 canales)")

    def init_anim(self):
        for line in self.lines:
            line.set_data([], [])
        return self.lines

    def update_anim(self, frame_idx):
        # 1) Generar muestras nuevas
        n_new = max(1, int(self.fs * ANIM_INTERVAL))
        for _ in range(n_new):
            t = self.current_time
            voltages = synthetic_sample(t)
            self.processor.add_sample(voltages)
            self.current_time += 1.0 / self.fs

        buffers = self.processor.buffers
        n_available = len(buffers[0])
        if n_available < 64:
            # Aún no hay suficientes muestras para PSD estable
            return self.lines

        # 2) Calcular PSD por canal
        for ch in range(self.num_channels):
            freqs, pxx = self.processor.get_power_spectrum(ch)
            if freqs is None:
                continue

            self.lines[ch].set_data(freqs, pxx)

            ax = self.axes[ch]
            ax.set_xlim(0, 50)

            pxx_pos = pxx[pxx > 0]
            if pxx_pos.size > 0:
                ymin = pxx_pos.min()
                ymax = pxx_pos.max()
                if ymin == ymax:
                    ymin *= 0.5
                    ymax *= 1.5
                ax.set_ylim(ymin, ymax)

        return self.lines

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
    demo = PSDDemo()
    demo.run()
