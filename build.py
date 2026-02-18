import PyInstaller.__main__
import os
import shutil

import time

def clean_dir(path):
    if os.path.exists(path):
        try:
            shutil.rmtree(path)
        except OSError as e:
            print(f"Warning: Could not fully clean {path}. Retrying with ignore_errors...")
            time.sleep(1)
            try:
                shutil.rmtree(path, ignore_errors=True)
            except OSError as e2:
                print(f"Error: Could not clean {path}: {e2}. Proceeding anyway...")

clean_dir("dist_new") # Clean new dist
clean_dir("build_new") # Clean new workpath

# Define assets
# We need to make sure 'src' is importable or hidden imports are handled.
# faster-whisper and ctranslate2 have binary dependencies.

PyInstaller.__main__.run([
    'src/main.py',
    '--name=WhisperTyper',
    '--onefile',
    '--noconsole',
    '--clean',
    '--distpath=dist_new', # Use new dist path
    '--workpath=build_new', # Use new work path
    # Robust Hidden Imports
    '--hidden-import=pynput.keyboard._win32',
    '--hidden-import=pynput.mouse._win32',
    '--hidden-import=faster_whisper',
    '--hidden-import=pynvml',
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

print("Build complete. Check /dist_new folder.")
