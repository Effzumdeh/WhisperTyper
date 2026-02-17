
import sys
print("Starting imports...")
try:
    print("Importing pydantic...")
    import pydantic
    print(f"pydantic version: {pydantic.__version__}")
except Exception as e:
    print(f"pydantic failed: {e}")

try:
    print("Importing PySide6...")
    from PySide6.QtWidgets import QApplication
    print("PySide6 imported")
except Exception as e:
    print(f"PySide6 failed: {e}")

try:
    print("Importing sounddevice...")
    import sounddevice
    print("sounddevice imported")
except Exception as e:
    print(f"sounddevice failed: {e}")

try:
    print("Importing faster_whisper...")
    from faster_whisper import WhisperModel
    print("faster_whisper imported")
except Exception as e:
    print(f"faster_whisper failed: {e}")
    import traceback
    traceback.print_exc()

print("Imports done.")
