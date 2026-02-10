import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

from signal_processor import SignalProcessor

FS = 250
ANIM_INTERVAL = 0.05  # s entre frames (50 ms)
WINDOW_SEC = 4.0      # ventana visible en el eje tiempo


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


class TimeSeriesDemo:
    def __init__(self):
        self.processor = SignalProcessor()
        self.fs = self.processor.fs
        self.num_channels = self.processor.num_channels

        self.current_time = 0.0

        self.window_samples = int(WINDOW_SEC * self.fs)

        # Figura: 4 subplots (uno por canal)
        self.fig, self.axes = plt.subplots(self.num_channels, 1, figsize=(10, 7), sharex=True)
        if self.num_channels == 1:
            self.axes = [self.axes]

        self.lines = []
        for ch, ax in enumerate(self.axes):
            (line,) = ax.plot([], [], lw=1)
            self.lines.append(line)
            ax.set_ylabel(f"CH{ch+1} (V)")
            ax.grid(True)

        self.axes[-1].set_xlabel("Time (s)")
        self.fig.suptitle("EEG Time Series - Real-time (4 canales)")

    def init_anim(self):
        for line in self.lines:
            line.set_data([], [])
        return self.lines

    def update_anim(self, frame_idx):
        # 1) Generar muestras nuevas para este frame
        n_new = max(1, int(self.fs * ANIM_INTERVAL))
        for _ in range(n_new):
            t = self.current_time
            voltages = synthetic_sample(t)
            self.processor.add_sample(voltages)
            self.current_time += 1.0 / self.fs

        buffers = self.processor.buffers
        n_available = len(buffers[0])
        if n_available < 10:
            return self.lines

        # 2) Construir ventana de tiempo
        n = min(n_available, self.window_samples)
        data = np.column_stack([
            np.array(buffers[ch])[-n:] for ch in range(self.num_channels)
        ])
        t_vec = np.arange(-n, 0) / self.fs  # [-WINDOW_SEC, 0)

        # 3) Actualizar líneas
        for ch in range(self.num_channels):
            self.lines[ch].set_data(t_vec, data[:, ch])
            ax = self.axes[ch]
            ax.set_xlim(t_vec[0], t_vec[-1])

            ymin = data[:, ch].min()
            ymax = data[:, ch].max()
            if ymin == ymax:
                ymin -= 1e-6
                ymax += 1e-6
            margin = 0.2 * (ymax - ymin)
            ax.set_ylim(ymin - margin, ymax + margin)

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
    demo = TimeSeriesDemo()
    demo.run()
