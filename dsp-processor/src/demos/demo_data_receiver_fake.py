import struct
from src.data_receiver import DataReceiver, FRAME_SIZE, NUM_CHANNELS, LSB


class FakeSerial:
    """
    Puerto serie falso que devuelve un payload fijo cuando se llama a read().
    Sirve para probar DataReceiver sin Arduino real.
    """
    def __init__(self, payload: bytes):
        self.payload = payload
        self.offset = 0

    def read(self, n: int) -> bytes:
        # Devuelve como máximo n bytes a partir de la posición actual
        if self.offset >= len(self.payload):
            return b""
        chunk = self.payload[self.offset:self.offset + n]
        self.offset += len(chunk)
        return chunk

    @property
    def is_open(self) -> bool:
        return True

    def close(self):
        pass  # no hace falta para el fake


def build_fake_frame(sample_idx: int, raw_channels: list[int]) -> bytes:
    """
    Construye un frame binario con el mismo formato que espera DataReceiver:
    - uint32 little-endian: sample_idx
    - NUM_CHANNELS * int32 little-endian: canales
    """
    assert len(raw_channels) == NUM_CHANNELS, "raw_channels debe tener NUM_CHANNELS elementos"

    frame = struct.pack("<I", sample_idx)               # sample_idx (4 bytes)
    frame += struct.pack(f"<{NUM_CHANNELS}i", *raw_channels)  # canales int32
    assert len(frame) == FRAME_SIZE, f"Frame size {len(frame)} != FRAME_SIZE {FRAME_SIZE}"
    return frame


def main():
    # 1) Definimos un índice de muestra y 4 valores crudos (int32 simulados)
    sample_idx = 42
    raw_channels = [100, -200, 300, -400]  # 4 canales

    # 2) Construimos el frame binario
    frame_data = build_fake_frame(sample_idx, raw_channels)

    # 3) Creamos un DataReceiver y le inyectamos el "serial" falso
    receiver = DataReceiver(port="FAKE", baudrate=115200)
    receiver.serial_conn = FakeSerial(frame_data)

    # 4) Llamamos a read_frame() como si leyera del Arduino
    result = receiver.read_frame()
    if result is None:
        print("❌ No se pudo parsear el frame")
        return
                                                                                                                    
    idx, voltages = result



    print("=== RESULTADO DEMO DATA RECEIVER ===")
    print(f"sample_idx leído: {idx}")
    print(f"sample_idx esperado: {sample_idx}\n")

    print("Raw channels simulados:", raw_channels)
    print("Voltajes calculados (V):")
    for ch, (raw, v) in enumerate(zip(raw_channels, voltages), start=1):
        expected_v = raw * LSB
        print(f"  CH{ch}: raw={raw:6d} -> {v:.9f} V (esperado ~ {expected_v:.9f} V)")


if __name__ == "__main__":
    main()
