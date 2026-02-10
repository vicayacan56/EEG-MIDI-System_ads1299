# main_eeg_to_midi.py
# --------------------
#
# Demo de orquestador: EDF -> MIDI
#
# - Carga un EDF real (tarea mental) con MNE.
# - Filtra los canales EEG seleccionados.
# - Por cada canal:
#     * crea un único MusicSegment que abarca toda la duración,
#     * lo divide en N compases (bars),
#     * calcula estabilidad espectral y amplitud por slot,
#     * genera notas y escribe un archivo .mid en la carpeta de salida.
#
# Uso (por ejemplo):
#   python main_eeg_to_midi.py ruta_al_edf.edf output_midis
#
from __future__ import annotations

import os
import argparse

import numpy as np
import mne
from scipy import signal

from dsp_core import DSPCore
from eeg_to_bars import generate_bars_for_segment
from music_segment import MusicSegmentBuilder
from music_bar import BarGenerator
from music_note import NoteGenerator
from midi_writer import write_midi_from_notes
from music_utils import note_name_to_midi
from eeg_segmenter import Segment

from scale_registry import list_families, list_scales, build_scale_config


# ---------------------------------------------------------------------
# Carga de EDF del dataset de tarea mental (tal como lo tenías)
# ---------------------------------------------------------------------
def load_math_task_eeg(
    path_edf: str,
    channels_to_use=None,
):
    print(f"[INFO] Cargando EDF: {path_edf}")
    raw = mne.io.read_raw_edf(path_edf, preload=True)
    fs = float(raw.info["sfreq"])
    print(f"[INFO] Frecuencia de muestreo EDF: {fs:.2f} Hz")

    if channels_to_use is None:
        channels_to_use = ["EEG Fp1", "EEG Fp2", "EEG C3", "EEG O1"]

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

    print(f"[INFO] EEG cargado: {eeg_v.shape[0]} muestras, {eeg_v.shape[1]} canales.")
    print(f"[INFO] Canales seleccionados: {selected}")

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
# Filtro offline (HP 0.5 Hz, LP 50 Hz, Notch 60 Hz)
# ---------------------------------------------------------------------
def filter_eeg_channel(x: np.ndarray, fs: float) -> np.ndarray:
    """
    Replica el filtrado de EEGSignalProcessor:
      - HP 0.5 Hz
      - LP 50 Hz
      - Notch 60 Hz
    aplicado offline a un canal 1D.
    """
    x = np.asarray(x, dtype=float)
    if x.size < 10:
        return x.copy()

    # High-pass
    hp_b, hp_a = signal.butter(2, 0.5, fs=fs, btype="high", output="ba")
    # Low-pass
    lp_b, lp_a = signal.butter(2, 50.0, fs=fs, btype="low", output="ba")
    

    y = signal.filtfilt(hp_b, hp_a, x)
    y = signal.filtfilt(lp_b, lp_a, y)
    
    return y


# ---------------------------------------------------------------------
# Orquestador por canal
# ---------------------------------------------------------------------
def process_channel_to_midi(
    x_chan: np.ndarray,
    fs: float,
    channel_name: str,
    output_dir: str,
    n_bars: int = 16,
    family: str = "Diatonic",
    scale_name: str = "Major (Ionian)",
    root_note: str = "C4",
    main_note_name: str = "C4",
    bpm: float = 120.0,
):
    """
    Procesa un canal de EEG completo y genera un archivo MIDI.

    Pasos:
        1) Filtrado offline del canal.
        2) Creación de un único Segment (toda la duración del canal).
        3) Cálculo de features globales con DSPCore.
        4) Construcción de un MusicSegment (sin segmentación por estado).
        5) División del segmento en n_bars compases usando generate_bars_for_segment.
        6) Generación de NoteEvents con NoteGenerator.
        7) Escritura de MIDI en output_dir.
    """
    x_chan = np.asarray(x_chan, dtype=float)
    n_samples = x_chan.size
    duration = n_samples / fs

    if n_samples < 10:
        print(f"[AVISO] Canal {channel_name} demasiado corto, se omite.")
        return

    print(f"[INFO] Procesando canal {channel_name}: {n_samples} muestras, {duration:.2f} s")

    # 1) Filtrado
    x_filt = filter_eeg_channel(x_chan, fs)

    # 2) Segmento único (índices 0..n_samples-1)
    seg = Segment(
        start_idx=0,
        end_idx=n_samples - 1,
        t_start=0.0,
        t_end=(n_samples - 1) / fs,
    )

    # 3) DSPCore: features globales
    dsp = DSPCore(fs=fs, window_sec=4.0)
    eeg_feats = dsp.compute_features(x_filt, psd_method="multitaper")

    # 4) Selección escala por (familia, escala, root_note)
    scale = build_scale_config(
        family=family,
        scale_name=scale_name,
        root_note=root_note,
    )

    # main note elegida por el usuario (no depende de peak_freq)
    user_main_midi = note_name_to_midi(main_note_name)

    seg_builder = MusicSegmentBuilder(fs=fs)
    music_seg = seg_builder.build_segment(
        segment=seg,
        eeg_features=eeg_feats,
        user_scale=scale,
        user_main_note_midi=user_main_midi,
    )

    # 5) Generar Bars (acordes + note_positions)
    bar_gen = BarGenerator()
    bars = generate_bars_for_segment(
        dsp=dsp,
        bar_gen=bar_gen,
        music_segment=music_seg,
        x_segment=x_filt,
        n_bars=n_bars,
        stability_fmin=0.5,
        stability_fmax=40.0,
    )

    print(f"[INFO] Canal {channel_name}: generados {len(bars)} compases.")

    # 6) Generar notas
    note_gen = NoteGenerator()
    notes = note_gen.generate_notes_for_segment(music_seg, bars)

    print(f"[INFO] Canal {channel_name}: generadas {len(notes)} notas.")

    # 7) Escribir MIDI
    os.makedirs(output_dir, exist_ok=True)
    midi_filename = f"eeg_math_task_{channel_name}.mid"
    midi_path = os.path.join(output_dir, midi_filename)

    write_midi_from_notes(
        notes,
        midi_path,
        bpm=bpm,
        ticks_per_beat=480,
    )

    print(f"[OK] MIDI escrito: {midi_path}")


# ---------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Demo orquestador EDF -> carpeta de MIDIs (por canal)."
    )
    parser.add_argument("edf_path", type=str, help="Ruta al archivo EDF de EEG.")
    parser.add_argument(
        "output_dir",
        type=str,
        help="Carpeta de salida para los archivos .mid.",
    )
    parser.add_argument(
        "--channels",
        type=str,
        nargs="*",
        default=["EEG Fp1", "EEG Fp2", "EEG C3", "EEG O1"],
        help="Lista de canales a usar (por defecto: EEG Fp1 EEG Fp2 EEG C3 EEG O1).",
    )
    parser.add_argument(
        "--bars",
        type=int,
        default=16,
        help="Número de compases (bars) en el segmento entero (por canal).",
    )

    # -------- NUEVO: selección de escala por familia/escala/root --------
    parser.add_argument(
        "--family",
        type=str,
        default="World",
        help=f"Familia de escalas. Opciones: {list_families()}",
    )
    parser.add_argument(
        "--scale_name",
        type=str,
        default="Spanish Gypsy (Phrygian Dominant)",
        help="Nombre de la escala dentro de la familia (ver --family).",
    )
    parser.add_argument(
        "--root",
        type=str,
        default="C4",
        help="Root note (tónica) de la escala, ej: C4, D#3, Bb3.",
    )

    parser.add_argument(
        "--main_note",
        type=str,
        default="C4",
        help="Nota principal del segmento (ej. 'C4', 'G3', 'A4').",
    )
    parser.add_argument(
        "--bpm",
        type=float,
        default=120.0,
        help="Tempo del MIDI (beats per minute).",
    )

    args = parser.parse_args()

    edf_path = args.edf_path
    output_dir = args.output_dir
    channels_to_use = args.channels
    n_bars = args.bars

    family = args.family
    scale_name = args.scale_name
    root_note = args.root

    main_note_name = args.main_note
    bpm = args.bpm

    # 0) Validación rápida de familia/escala para dar error bonito antes de procesar
    try:
        _ = list_scales(family)  # valida familia
        if scale_name not in _:
            raise ValueError(
                f"Escala '{scale_name}' no existe en familia '{family}'. "
                f"Opciones: {list_scales(family)}"
            )
    except Exception as e:
        raise SystemExit(f"[ERROR] Selección de escala inválida: {e}")

    # 1) Cargar EEG
    eeg_v, fs, selected_channels = load_math_task_eeg(
        edf_path,
        channels_to_use=channels_to_use,
    )

    # 2) Procesar cada canal seleccionado
    n_samples, n_channels = eeg_v.shape
    for ch_idx, ch_name in enumerate(selected_channels):
        x_chan = eeg_v[:, ch_idx]
        process_channel_to_midi(
            x_chan=x_chan,
            fs=fs,
            channel_name=ch_name,
            output_dir=output_dir,
            n_bars=n_bars,
            family=family,
            scale_name=scale_name,
            root_note=root_note,
            main_note_name=main_note_name,
            bpm=bpm,
        )


if __name__ == "__main__":
    main()
