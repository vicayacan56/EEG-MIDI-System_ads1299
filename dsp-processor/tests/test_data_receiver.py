"""
Unit tests para el módulo data_receiver
"""

import unittest
import struct
from src.data_receiver import DataReceiver, FRAME_SIZE


class TestDataReceiver(unittest.TestCase):
    """Tests para parsing de frames binarios."""
    
    def test_frame_size(self):
        """Verifica que el tamaño del frame sea correcto."""
        self.assertEqual(FRAME_SIZE, 20)  # 4 + 4*4
    
    def test_parse_frame_structure(self):
        """Prueba el parseo de estructura de frame."""
        # Crear frame sintético
        sample_idx = 42
        channels = [100, -200, 300, -400]
        
        # Empaquetar (little-endian)
        frame_data = struct.pack('<I', sample_idx)  # idx
        frame_data += struct.pack('<4i', *channels)  # canales
        
        self.assertEqual(len(frame_data), FRAME_SIZE)
    
    def test_conversion_to_voltage(self):
        """Prueba la conversión de raw a voltaje."""
        from src.data_receiver import LSB
        
        raw_value = 1000
        expected_voltage = raw_value * LSB
        
        self.assertAlmostEqual(expected_voltage, 2.235e-5, places=10)


class TestSignalProcessor(unittest.TestCase):
    """Tests para procesamiento de señal."""
    
    def test_processor_initialization(self):
        """Verifica inicialización del procesador."""
        from src.signal_processor import SignalProcessor
        
        processor = SignalProcessor()
        self.assertEqual(processor.num_channels, 4)
        self.assertEqual(processor.fs, 250)


if __name__ == '__main__':
    unittest.main()
