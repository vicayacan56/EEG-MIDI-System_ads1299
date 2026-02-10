"""
Main Entry Point - Orquestador del sistema DSP
Integra lectura de datos, procesamiento y monitoreo en tiempo real.
"""

import time
import sys
import logging
from data_receiver import DataReceiver
from signal_processor import SignalProcessor, RealtimeMonitor
from data_receiver import NUM_CHANNELS

# Configuración de logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EEGMIDISystem:
    """Controlador principal del sistema EEG MIDI."""
    
    def __init__(self, port: str = "COM3", baudrate: int = 115200):
        """
        Inicializa el sistema.
        
        Args:
            port: Puerto COM del Arduino
            baudrate: Velocidad de comunicación
        """
        self.receiver = DataReceiver(port=port, baudrate=baudrate)
        self.processor = SignalProcessor()
        self.monitor = RealtimeMonitor(self.processor)
        
        self.running = False
        self.frame_count = 0
        self.error_count = 0
    
    def start(self):
        """Inicia el sistema."""
        logger.info("Iniciando EEG MIDI System...")
        
        if not self.receiver.connect():
            logger.error("No se pudo conectar al Arduino")
            return False
        
        self.running = True
        logger.info("✓ Sistema iniciado. Presiona Ctrl+C para detener.")
        
        return True
    
    def stop(self):
        """Detiene el sistema."""
        self.running = False
        self.receiver.disconnect()
        logger.info("Sistema detenido")
        logger.info(f"Frames procesados: {self.frame_count}, Errores: {self.error_count}")
    
    def run(self, update_interval: int = 1):
        """
        Ejecuta el loop principal de procesamiento.
        
        Args:
            update_interval: Intervalo de actualización de monitoreo en segundos
        """
        if not self.start():
            return
        
        last_update = time.time()
        
        try:
            while self.running:
                # Leer frame del Arduino
                frame = self.receiver.read_frame()
                
                if frame:
                    sample_idx, voltages = frame
                    
                    # Procesar datos
                    self.processor.add_sample(voltages)
                    self.frame_count += 1
                    
                    # Mostrar monitoreo periódicamente
                    current_time = time.time()
                    if current_time - last_update >= update_interval:
                        self.monitor.print_status()
                        logger.info(f"Frames: {self.frame_count} | Errores: {self.error_count}")
                        last_update = current_time
                else:
                    self.error_count += 1
                    time.sleep(0.001)  # Pequeña pausa si hay error
        
        except KeyboardInterrupt:
            logger.info("\nInterrupción del usuario (Ctrl+C)")
        except Exception as e:
            logger.error(f"Error en loop principal: {e}", exc_info=True)
        finally:
            self.stop()
    
    def run_demo(self):
        """Ejecuta una demostración con datos sintéticos."""
        logger.info("Ejecutando DEMO con datos sintéticos...")
        
        import numpy as np
        
        # Simular 5 segundos de datos
        num_frames = 250 * 5
        
        for frame_idx in range(num_frames):
            # Generar señal sintética: mezcla de bandas EEG
            t = frame_idx / 250.0
            
            # Delta (1-4 Hz), Theta (4-8 Hz), Alpha (8-13 Hz)
            synthetic = [
                0.05 * np.sin(2 * np.pi * 2 * t) +      # Delta
                0.08 * np.sin(2 * np.pi * 6 * t) +      # Theta
                0.1 * np.sin(2 * np.pi * 10 * t) +      # Alpha
                np.random.normal(0, 0.02)               # Ruido
                for _ in range(NUM_CHANNELS)
            ]
            
            self.processor.add_sample(synthetic)
            self.frame_count += 1
            
            # Mostrar monitoreo cada segundo
            if frame_idx % 250 == 0:
                self.monitor.print_status()
                logger.info(f"Demo frame: {frame_idx}/{num_frames}")
        
        logger.info("Demo completada")


def main():
    """Punto de entrada principal."""
    import argparse
    
    parser = argparse.ArgumentParser(description='EEG MIDI DSP Processor')
    parser.add_argument('--port', default='COM3', help='Puerto COM (default: COM3)')
    parser.add_argument('--baudrate', type=int, default=115200, help='Baudrate (default: 115200)')
    parser.add_argument('--demo', action='store_true', help='Ejecutar con datos sintéticos')
    
    args = parser.parse_args()
    
    system = EEGMIDISystem(port=args.port, baudrate=args.baudrate)
    
    if args.demo:
        system.run_demo()
    else:
        system.run(update_interval=1)


if __name__ == "__main__":
    main()
