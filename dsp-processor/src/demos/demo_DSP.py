import numpy as np
from signal_processor import SignalProcessor, RealtimeMonitor

# 1) Crear procesador (4 canales, 250 Hz)
processor = SignalProcessor()
monitor = RealtimeMonitor(processor)
# 2) Generar 1 segundo de datos sintéticos
#   - CH1: senoidal 10 Hz (banda alpha)
#   - CH2: senoidal 6 Hz (theta)
#   - CH3: senoidal 20 Hz (beta)
#   - CH4: solo ruido
fs = processor.fs
num_samples = 4*fs  # 1 segundo
for n in range(num_samples):
    t = n / fs

    ch1 = 0.0001 * np.sin(2 * np.pi * 10 * t) + np.random.normal(0, 0.00002)
    ch2 = 0.0001 * np.sin(2 * np.pi * 6 * t)  + np.random.normal(0, 0.00002)
    ch3 = 0.0001 * np.sin(2 * np.pi * 20 * t) + np.random.normal(0, 0.00002)
    ch4 = np.random.normal(0, 0.00002)

    processor.add_sample([ch1, ch2, ch3, ch4])
# 3) Mostrar estado actual

monitor.print_status()