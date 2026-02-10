"""
Data Receiver Module - Lee datos del buffer binario del Arduino
Parsea el protocolo little-endian y convierte a voltaje.
"""

import struct
import serial
from typing import Tuple, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuración del protocolo
NUM_CHANNELS = 4
FRAME_SIZE = 4 + (4 * NUM_CHANNELS)  # 20 bytes
LSB = 2.235e-8  # Voltios por LSB


class DataReceiver:
    """Lee frames binarios del Arduino y los convierte a voltaje."""
    
    def __init__(self, port: str = "COM3", baudrate: int = 115200, timeout: float = 1.0):
        """
        Inicializa la conexión serial con el Arduino.
        
        Args:
            port: Puerto COM (ej: "COM3", "/dev/ttyUSB0")
            baudrate: Velocidad en bps (115200 recomendado)
            timeout: Timeout de lectura en segundos
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial_conn = None
        self.sample_count = 0
        
    def connect(self) -> bool:
        """Establece conexión con el Arduino."""
        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout
            )
            logger.info(f"✓ Conectado a {self.port} @ {self.baudrate} bps")
            return True
        except serial.SerialException as e:
            logger.error(f"✗ Error de conexión: {e}")
            return False
    
    def disconnect(self):
        """Cierra la conexión serial."""
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            logger.info("Desconectado del Arduino")
    
    def read_frame(self) -> Optional[Tuple[int, list]]:
        """
        Lee un frame completo del buffer.
        
        Returns:
            Tupla (sample_idx, voltages) donde voltages es lista de 8 float
            None si hay error o timeout
        """
        if not self.serial_conn or not self.serial_conn.is_open:
            logger.error("Puerto serial no conectado")
            return None
        
        try:
            # Leer exactamente FRAME_SIZE bytes
            frame_data = self.serial_conn.read(FRAME_SIZE)
            
            if len(frame_data) != FRAME_SIZE:
                logger.warning(f"Frame incompleto: {len(frame_data)}/{FRAME_SIZE} bytes")
                return None
            
            # Parsear sample_idx (primeros 4 bytes, little-endian)
            sample_idx = struct.unpack('<I', frame_data[0:4])[0]
            
            # Parsear canales (siguientes 4*4 bytes, little-endian, int32)
            raw_channels = struct.unpack('<4i', frame_data[4:20])
            
            # Convertir a voltaje
            voltages = [raw * LSB for raw in raw_channels]
            
            self.sample_count += 1
            
            return sample_idx, voltages
            
        except struct.error as e:
            logger.error(f"Error al parsear frame: {e}")
            return None
        except Exception as e:
            logger.error(f"Error inesperado en read_frame: {e}")
            return None
    
    def read_multiple_frames(self, num_frames: int) -> list:
        """
        Lee múltiples frames consecutivos.
        
        Args:
            num_frames: Número de frames a leer
            
        Returns:
            Lista de tuplas (sample_idx, voltages)
        """
        frames = []
        for _ in range(num_frames):
            frame = self.read_frame()
            if frame:
                frames.append(frame)
        return frames


if __name__ == "__main__":
    # Prueba básica
    receiver = DataReceiver(port="COM3")
    
    if receiver.connect():
        logger.info("Leyendo 10 frames de prueba...")
        for i in range(10):
            result = receiver.read_frame()
            if result:
                idx, voltages = result
                logger.info(f"Frame {i}: idx={idx}, CH1={voltages[0]:.6f}V")
        receiver.disconnect()
