# src/dsp_core.py

"""
DSP Core Module
---------------
Funciones de análisis espectral (ventanas, PSD, bandpower, features)
para un solo canal. No gestiona buffers ni múltiples canales; eso
lo hace EEGSignalProcessor.
"""

import numpy as np
from scipy import signal
from scipy.signal import windows
import logging

logger = logging.getLogger(__name__)




class DSPCore:
    """
    Núcleo DSP para análisis de un canal:
      - ventana (Hann, Hamming, Blackman, etc.)
      - PSD (periodograma o Welch)
      - potencia en bandas
      - features de alto nivel
    """

    def __init__(
        self,
        fs: float,
        window_sec: float = 4.0,
        window_type: str = "hann",
        welch_overlap: float = 0.5,
        bands: dict | None = None,
        mt_nw: float = 2.5, # Parámetro time-bandwidth para multitaper
        mt_n_tapers: int | None = None, # nº de tapers para multitaper
        outlier_zscore: float = 5.0,   # umbral robusto (MAD) para outliers
        interpolate_outliers: bool = True,
        clipping_fraction_threshold: float = 0.01,  # fracción de muestras iguales en extremo

    ):
        """
        Args:
            fs: frecuencia de muestreo (Hz)
            window_sec: duración de la ventana principal de análisis (s)
            window_type: tipo de ventana ("hann", "hamming", "blackman", etc.)
            welch_overlap: fracción de solapamiento en Welch (0.0 ~ 0.9 típicamente)
            bands: diccionario de bandas de frecuencia en Hz.
                   Por defecto: delta, theta, alpha, beta, gamma.
        """
        self.fs = float(fs)
        self.window_sec = float(window_sec)
        self.window_type = window_type.lower()
        self.welch_overlap = float(welch_overlap)

        # nº de muestras de la ventana principal (por ejemplo 4 s * fs)
        self.window_samples = max(1, int(round(self.fs * self.window_sec)))

        # Definición de bandas EEG por defecto
        if bands is None:
            bands = {
                "delta": (0.5, 4),
                "theta": (4, 8),
                "alpha": (8, 13),
                "beta":  (13, 30),
                "gamma": (30, 50),
            }
        self.bands = bands
        # --- parámetros multitaper ---
        self.mt_nw = float(mt_nw)
        # Kmax ≈ 2*NW - 1 si no se especifica
        if mt_n_tapers is None:
            self.mt_n_tapers = max(1, int(2 * self.mt_nw - 1))
        else:
            self.mt_n_tapers = int(mt_n_tapers)
        
          # --- parámetros de preprocesado avanzado ---
        self.outlier_zscore = float(outlier_zscore)
        self.interpolate_outliers = bool(interpolate_outliers)
        self.clipping_fraction_threshold = float(clipping_fraction_threshold)

        # estados útiles para debug/monitorización
        self.last_clipping_detected: bool = False
        self.last_outlier_ratio: float = 0.0


    # ------------------------------------------------------------------
    # Utilidades de ventana
    # ------------------------------------------------------------------
    def get_freq_bin_size(self, n_samples: int | None = None) -> float:
        """
        Devuelve el tamaño de bin de frecuencia Δf = fs / N
        para N muestras (o para la ventana principal si N es None).
        """
        if n_samples is None:
            n_samples = self.window_samples
        n_samples = max(1, int(n_samples))
        return self.fs / n_samples

    def _make_window(self, n: int) -> np.ndarray:
        """
        Crea una ventana de longitud n del tipo configurado.
        """
        if n <= 1:
            return np.ones(n, dtype=float)
        return signal.get_window(self.window_type, n, fftbins=True)
    # ------------------------------------------------------------------
    # Detección de clipping
    # ------------------------------------------------------------------
    def _detect_clipping(self, x: np.ndarray) -> bool:
        """
        Detecta posible clipping (saturación) mirando cuántas muestras
        están exactamente en el máximo o mínimo valor medido.
        No depende de la escala concreta del ADC; es una heurística.
        """
        if x.size < 4:
            return False

        max_val = np.max(x)
        min_val = np.min(x)

        # tolerancia pequeña para flotantes
        atol = 1e-9
        n_max = np.sum(np.isclose(x, max_val, atol=atol))
        n_min = np.sum(np.isclose(x, min_val, atol=atol))
        frac = (n_max + n_min) / x.size

        clipped = frac >= self.clipping_fraction_threshold
        if clipped:
            logger.warning(
                f"[DSPCore] Posible clipping detectado: "
                f"{frac:.3%} de muestras en min/max "
                f"(min={min_val:.3e}, max={max_val:.3e})"
            )
        return clipped

    # ------------------------------------------------------------------
    # Preprocesado con detrend + outliers + clipping
    # ------------------------------------------------------------------
    def preprocess(
        self,
        x: np.ndarray,
        detrend: bool = True,
        remove_outliers: bool = True,
        
    ) -> np.ndarray:
        """
        Preprocesado antes de la FFT/PSD:
          - conversión a float
          - detrend opcional (elimina DC / drift lineal)
          - detección de clipping (heurística)
          - detección de outliers (robusta con MAD)
          - interpolación/clip suave de los outliers
        """
        x = np.asarray(x, dtype=float)
        if x.size == 0:
            self.last_clipping_detected = False
            self.last_outlier_ratio = 0.0
            return x

        y = x.copy()
        if detrend and y.size >= 4:
            y = signal.detrend(y, type="linear") # 1) detrend


        self.last_clipping_detected = self._detect_clipping(y)  # 2) detección de clipping (solo informativa)


        self.last_outlier_ratio = 0.0 # 3) detección + corrección de outliers
        if remove_outliers and y.size >= 5:
            median = np.median(y)
            abs_dev = np.abs(y - median)
            mad = np.median(abs_dev)

            if mad > 0:
                # z-score robusto
                z = 0.6745 * (y - median) / mad
                mask_out = np.abs(z) > self.outlier_zscore
                n_out = int(np.sum(mask_out))
                if n_out > 0:
                    self.last_outlier_ratio = n_out / y.size
                    logger.debug(
                        f"[DSPCore] Outliers detectados: {n_out}/{y.size} "
                        f"({self.last_outlier_ratio:.3%})"
                    )

                    if self.interpolate_outliers and np.sum(~mask_out) >= 2:
                        # interpolación lineal sobre índices buenos
                        idx = np.arange(y.size)
                        y[mask_out] = np.interp(
                            idx[mask_out],
                            idx[~mask_out],
                            y[~mask_out],
                        )
                    else:
                        # clip suave al umbral robusto
                        y_clipped = np.clip(z, -self.outlier_zscore, self.outlier_zscore)
                        y = median + (y_clipped * mad / 0.6745)
        return y

    # ------------------------------------------------------------------
    # PSD / ESPECTRO
    # ------------------------------------------------------------------
    def compute_psd(
        self,
        x: np.ndarray,
        method: str = "multitaper",
        nperseg: int | None = None,
        noverlap: int | None = None,
        apply_window: bool = True,
        preprocess: bool = True,
    ) -> tuple[np.ndarray | None, np.ndarray | None]:
        """
        Calcula la PSD de una señal de un canal usando periodograma o Welch o Multitaper. (Multitaper por defecto)
        """
        if preprocess:
            x = self.preprocess(x)

        
        n = x.size
        if n < 4:
            return None, None

        method = method.lower()

        if method == "periodogram":
            win = self._make_window(n) if apply_window else "boxcar"
            freqs, pxx = signal.periodogram(
                x,
                fs=self.fs,
                window=win,
                scaling="density",
            )
            return freqs, pxx

        elif method == "welch":
            if nperseg is None:
                nperseg = min(self.window_samples, n)
            else:
                nperseg = min(int(nperseg), n)

            if nperseg < 4:
                return None, None

            if noverlap is None:
                noverlap = int(nperseg * self.welch_overlap)
            noverlap = max(0, min(int(noverlap), nperseg - 1))

            win = self.window_type if apply_window else "boxcar"

            freqs, pxx = signal.welch(
                x,
                fs=self.fs,
                window=win,
                nperseg=nperseg,
                noverlap=noverlap,
                scaling="density",
            )
            return freqs, pxx
        
        elif method == "multitaper":
            return self._compute_psd_multitaper(x)

        else:
            raise NotImplementedError(f"Método PSD no soportado: {method}")
        
    def _compute_psd_multitaper(self, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """
        PSD multitaper usando DPSS (Slepian) tapers.

        Aproximación inspirada en Thomson/Babadi & Brown,
        Babadi B, Brown EN. A review of multitaper spectral analysis. 
        IEEE Trans Biomed Eng. 2014;61:1555–64. https:// doi. org/ 10. 
        1109/ TBME. 2014. 23119 96.
        
        Suficiente para obtener un espectro suave y con poca fuga.
        """
        x = np.asarray(x, dtype=float)
        n = x.size
        if n < 4:
            return None, None

        # Usamos toda la ventana disponible (o lo que haya en x)
        n_win = min(self.window_samples, n)

        if n_win < 4:
            return None, None

        # recortamos al final de la señal (ventana deslizante “al vuelo”)
        x_seg = x[-n_win:]

        # DPSS tapers KxN
        tapers = windows.dpss(
            n_win,
            self.mt_nw,
            Kmax=self.mt_n_tapers,
            sym=False,
        )  # shape (K, n_win)

        # FFT real (solo frecuencias positivas)
        # dt = 1/fs para normalizar a densidad de potencia
        dt = 1.0 / self.fs
        freqs = np.fft.rfftfreq(n_win, d=dt)

        # acumulador de potencia
        psd_acc = np.zeros_like(freqs, dtype=float) 

        for k in range(self.mt_n_tapers):
            taper = tapers[k]
            x_tap = x_seg * taper
            Xf = np.fft.rfft(x_tap)
            # estimador de densidad de potencia (Watts/Hz ~ V^2/Hz)
            psd_k = (dt / n_win) * np.abs(Xf) ** 2
            psd_acc += psd_k

        pxx = psd_acc / self.mt_n_tapers
        return freqs, pxx

    # ------------------------------------------------------------------
    # POTENCIA EN BANDAS
    # ------------------------------------------------------------------
    def compute_bandpower(
        self,
        freqs: np.ndarray,
        pxx: np.ndarray,
        relative: bool = False,
    ) -> dict:
        """
        Calcula potencia en bandas a partir de (freqs, pxx).
        """
        if freqs is None or pxx is None:
            return {}
        freqs = np.asarray(freqs)
        pxx = np.asarray(pxx)
        if freqs.size == 0 or pxx.size == 0:
            return {}

        band_power = {}
        total_power = np.trapezoid(pxx, freqs)

        for band_name, (f_low, f_high) in self.bands.items():
            mask = (freqs >= f_low) & (freqs <= f_high)
            if not np.any(mask):
                band_power[band_name] = 0.0
                continue

            power = np.trapezoid(pxx[mask], freqs[mask])
            if relative and total_power > 0:
                power = power / total_power
            band_power[band_name] = float(power)

        return band_power

    # ------------------------------------------------------------------
    # FEATURES DE ALTO NIVEL
    # ------------------------------------------------------------------
    def compute_features(
        
        self,
        x: np.ndarray,
        psd_method: str = "multitaper",
        nperseg: int | None = None,
        noverlap: int | None = None,
        
    ) -> dict:
        """
        Calcula un conjunto de características espectrales de alto nivel
        a partir de una ventana 1D x.
        """
        x = np.asarray(x, dtype=float)
        if x.size < 4:
            return {}

        x_prep = self.preprocess(x)
        rms = float(np.sqrt(np.mean(x_prep ** 2)))
        total_time_power = rms**2  # V²

        freqs, pxx = self.compute_psd(
            x,
            method=psd_method,
            nperseg=nperseg,
            noverlap=noverlap,
            preprocess=False,
        )
        if freqs is None:
            return {}
        # --- Potencia absoluta ---
        band_abs = self.compute_bandpower(freqs, pxx, relative=False)
        # --- Potencia relativa ---
        band_rel = {}
        total_psd_power_raw = sum(band_abs.values())
        if total_psd_power_raw > 0:
            for name, val in band_abs.items():
                band_rel[name] = float(val / total_psd_power_raw)
        else:
            for name in band_abs.keys():
                band_rel[name] = 0.0
            
        # Ajuste de escala: forzamos que sum(band_abs) ≈ potencia total en tiempo
        total_psd_power = sum(band_abs.values())
        if total_psd_power > 0:
           scale = total_time_power / total_psd_power
           for k in band_abs:
                band_abs[k] *= scale


        # --- Picos espectrales ---
        idx_peak = int(np.argmax(pxx))
        peak_freq = float(freqs[idx_peak])

        def _peak_in_band(f_low, f_high):
            mask = (freqs >= f_low) & (freqs <= f_high)
            if not np.any(mask):
                return None
            sub_idx = np.argmax(pxx[mask])
            return float(freqs[mask][sub_idx])

        delta_band = self.bands.get("delta", (0.5, 4))
        theta_band = self.bands.get("theta", (4, 8))
        alpha_band = self.bands.get("alpha", (8, 13))
        beta_band = self.bands.get("beta", (13, 30))
        gamma_band = self.bands.get("gamma", (30, 50))
        
        

        peak_alpha = _peak_in_band(*alpha_band)
        peak_beta = _peak_in_band(*beta_band)
        peak_delta = _peak_in_band(*delta_band)
        peak_theta = _peak_in_band(*theta_band)
        peak_gamma = _peak_in_band(*gamma_band)

        return { 
            "rms": rms,
            "freqs": freqs,
            "psd": pxx,
            "bandpower_abs": band_abs,
            "bandpower_rel": band_rel,
            "peak_freq": peak_freq,
            "peak_alpha": peak_alpha,
            "peak_delta": peak_delta,
            "peak_theta": peak_theta,
            "peak_gamma": peak_gamma,
            "peak_beta": peak_beta,
        }
        # ------------------------------------------------------------------
    # ESPECTROGRAMA (time-frequency)
    # ------------------------------------------------------------------
    def compute_spectrogram(
        self,
        x: np.ndarray,
        method: str = "multitaper",
        window_sec: float | None = None,
        step_sec: float | None = None,
        apply_window: bool = True,
        log_scale: bool = True,
        preprocess: bool = True, 
    ) -> tuple[np.ndarray | None, np.ndarray | None, np.ndarray | None]:
        """
        Calcula un espectrograma (time-frequency) a partir de una señal 1D.

        Devuelve:
            times : array (n_windows,)  -> tiempo (s) del centro de cada ventana
            freqs : array (n_freqs,)    -> frecuencias (Hz)
            Sxx   : array (n_windows,n_freqs) -> PSD en cada ventana (densidad)

        method:
            - "periodogram": ventana clásica (Hann/Blackman, etc.)
            - "multitaper" : multitaper con DPSS
            - "welch"      : opcional, Welch por ventana (sin solape interno)
        """
        x = np.asarray(x, dtype=float)
        n_total = x.size
        if n_total < 4:
            return None, None, None

        # Preprocesado global (detrend + outliers, etc.) si necesario.
        if preprocess:
            x = self.preprocess(x)
        

        # Ventana de análisis (por defecto, la del propio DSPCore)
        if window_sec is None:
            window_sec = self.window_sec
        win_samples = int(round(window_sec * self.fs))
        win_samples = max(1, min(win_samples, n_total))
        if win_samples < 4:
            return None, None, None

        # Paso entre ventanas (step). Si no se especifica, usamos el solapamiento
        # tipo Welch: step = win * (1 - welch_overlap)
        if step_sec is None:
            step_samples = int(round(win_samples * (1.0 - self.welch_overlap)))
        else:
            step_samples = int(round(step_sec * self.fs))
        step_samples = max(1, step_samples)

        # Índices de inicio para cada ventana deslizante
        starts = list(range(0, n_total - win_samples + 1, step_samples))
        if len(starts) == 0:
            return None, None, None

        method = method.lower()
        freqs = None
        Sxx_list = []
        times = []

        for start in starts:
            seg = x[start:start + win_samples]

            if method == "periodogram":
                # ventana Blackman / Hann, etc. según self.window_type
                if apply_window:
                    win = self._make_window(win_samples)
                else:
                    win = "hann"
                f_tmp, pxx = signal.periodogram(
                    seg,
                    fs=self.fs,
                    window=win,
                    scaling="density",
                )

            elif method == "multitaper":
                # usamos la implementación interna multitaper
                f_tmp, pxx = self._compute_psd_multitaper(seg)

            elif method == "welch":
                # Welch sin solape interno (solape ya lo hacemos fuera)
                if apply_window:
                    win = self.window_type
                else:
                    win = "hann"
                f_tmp, pxx = signal.welch(
                    seg,
                    fs=self.fs,
                    window=win,
                    nperseg=win_samples,
                    noverlap=0,
                    scaling="density",
                )
            else:
                raise NotImplementedError(f"Spectrogram method no soportado: {method}")

            if freqs is None:
                freqs = f_tmp   
            else:
                # Por seguridad, comprobamos que las frecuencias coinciden
                if f_tmp.shape != freqs.shape or not np.allclose(f_tmp, freqs):
                    raise RuntimeError("Las frecuencias PSD varían entre ventanas.")

            Sxx_list.append(pxx)
            # tiempo central de la ventana
            center_sample = start + win_samples / 2.0
            times.append(center_sample / self.fs)

        Sxx = np.vstack(Sxx_list)  # shape (n_windows, n_freqs)
        if log_scale:
            eps = 1e-12
            Sxx = 10 * np.log10(Sxx + eps)
        times = np.asarray(times, dtype=float)

        return times, freqs, Sxx
    # ------------------------------------------------------------------
    # MÉTRICA DE ESTABILIDAD ESPECTRAL
    # ------------------------------------------------------------------
    def compute_spectral_stability(
        self,
        x: np.ndarray,
        fmin: float = 0.5,
        fmax: float = 40.0,
        psd_method: str = "multitaper",
    ) -> float:
        """
        Calcula una métrica ESCALAR de 'estabilidad espectral' en [0,1]
        a partir de una ventana 1D x.

        Definición (propuesta):
            1) Calculamos la PSD en [fmin,fmax].
            2) Normalizamos el espectro como una distribución de probabilidad.
            3) Calculamos la entropía de Shannon H.
            4) La normalizamos por H_max = log(N).
            5) Definimos estabilidad = 1 - H_norm.

        Interpretación:
            - estabilidad ~ 1.0 -> espectro muy concentrado (baja entropía),
                                   típico de ritmos bien definidos.
            - estabilidad ~ 0.0 -> espectro muy repartido/plano (alta entropía),
                                   típico de actividad caótica o ruido.
        """
        x = np.asarray(x, dtype=float)
        if x.size < 4:
            return float("nan")

        # 1) PSD en el rango deseado
        freqs, pxx = self.compute_psd(
            x,
            method=psd_method,
            preprocess=True,
        )
        if freqs is None or pxx is None:
            return float("nan")

        freqs = np.asarray(freqs)
        pxx = np.asarray(pxx)

        # 2) Nos quedamos solo con [fmin, fmax]
        mask = (freqs >= fmin) & (freqs <= fmax)
        if not np.any(mask):
            return float("nan")

        p = pxx[mask].astype(float)

        # Evitar ceros exactos (para log)
        p = np.maximum(p, 1e-20)

        # Normalizar a probabilidad
        p_sum = np.sum(p)
        if p_sum <= 0:
            return float("nan")
        p /= p_sum

        # 3) Entropía de Shannon
        H = -np.sum(p * np.log(p))  # log natural

        # 4) Entropía máxima para N bins
        N = p.size
        H_max = np.log(N) if N > 0 else 0.0
        if H_max <= 0:
            return float("nan")

        H_norm = H / H_max  # 0..1

        # 5) Estabilidad = 1 - entropía_normalizada
        stability = 1.0 - float(H_norm)
        return stability

