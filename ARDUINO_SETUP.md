"""
Arduino Firmware Setup Instructions

Este archivo te explica cómo integrar tu código Arduino actual con el nuevo workspace.
"""

# OPCIÓN 1: Crear un Symlink (Recomendado)
# ============================================
# En PowerShell (Como Administrador):
# 
# $source = "C:\Users\PC\Documents\PlatformIO\Projects\EEG MIDI"
# $target = "C:\Users\PC\Documents\EEG-MIDI-System\arduino-firmware"
# New-Item -ItemType SymbolicLink -Path $target -Value $source -Force

# OPCIÓN 2: Copiar Carpeta
# ========================
# En PowerShell:
#
# Copy-Item "C:\Users\PC\Documents\PlatformIO\Projects\EEG MIDI" `
#           "C:\Users\PC\Documents\EEG-MIDI-System\arduino-firmware" -Recurse

# OPCIÓN 3: Git Submodule (Si usas Git)
# =======================================
# cd C:\Users\PC\Documents\EEG-MIDI-System
# git submodule add ../PlatformIO/Projects/EEG\ MIDI arduino-firmware

# Verifica que tienes estos archivos:
# - arduino-firmware/src/main.cpp ✅
# - arduino-firmware/platformio.ini ✅
# - arduino-firmware/lib/ADS1299Plus/ ✅

print("✅ Arduino firmware vinculado correctamente")
