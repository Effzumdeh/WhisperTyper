import PyInstaller.__main__
import os
import shutil

# Clean dist/build
if os.path.exists("dist"): shutil.rmtree("dist")
if os.path.exists("build"): shutil.rmtree("build")

# Define assets
# We need to make sure 'src' is importable or hidden imports are handled.
# faster-whisper and ctranslate2 have binary dependencies.

PyInstaller.__main__.run([
    'src/main.py',
    '--name=WhisperTyper',
    '--onefile',
    '--noconsole',
    '--clean',
    # Robust Hidden Imports
    '--hidden-import=pynput.keyboard._win32',
    '--hidden-import=pynput.mouse._win32',
    '--hidden-import=faster_whisper',
    '--hidden-import=scipy.special.cython_special', 
    '--hidden-import=scipy.spatial.transform._rotation_groups',
    # Collect all binaries for faster-whisper
    '--collect-all=faster_whisper',
    # Paths
    '--paths=src',
    # Data (placeholder assets folder)
    '--add-data=assets;assets',
    # Icon (Commented out for now, use default)
    # '--icon=assets/icon.ico',
])

print("Build complete. Check /dist folder.")
