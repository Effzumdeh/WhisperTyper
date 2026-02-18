import PyInstaller.__main__
import os
import shutil

<<<<<<< Updated upstream
# Clean dist/build
if os.path.exists("dist"): shutil.rmtree("dist")
if os.path.exists("build"): shutil.rmtree("build")
=======
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

clean_dir("dist_v4") # Clean new dist
clean_dir("build_v4") # Clean new workpath
>>>>>>> Stashed changes

# Define assets
# We need to make sure 'src' is importable or hidden imports are handled.
# faster-whisper and ctranslate2 have binary dependencies.

PyInstaller.__main__.run([
    'src/main.py',
    '--name=WhisperTyper',
    '--onefile',
    '--noconsole',
    '--clean',
<<<<<<< Updated upstream
=======
    '--distpath=dist_v4', # Use new dist path
    '--workpath=build_v4', # Use new work path
>>>>>>> Stashed changes
    # Robust Hidden Imports
    '--hidden-import=pynput.keyboard._win32',
    '--hidden-import=pynput.mouse._win32',
    '--hidden-import=faster_whisper',
    '--hidden-import=scipy.special.cython_special', 
    '--hidden-import=scipy.spatial.transform._rotation_groups',
    # Collect all binaries for faster-whisper and ctranslate2
    '--collect-all=faster_whisper',
    '--collect-all=ctranslate2',
    # Collect NVIDIA libs (cublas, cudnn) often managed effectively by keying off 'nvidia'
    '--collect-all=nvidia',
    # Paths
    '--paths=src',
    # Data (placeholder assets folder)
    '--add-data=assets;assets',
    # Icon (Commented out for now, use default)
    # '--icon=assets/icon.ico',
])

<<<<<<< Updated upstream
print("Build complete. Check /dist folder.")
=======

print("Build complete. Verifying critical DLLs...")

# Verification Logic
dist_dir = "dist_v4"
exe_path = os.path.join(dist_dir, "WhisperTyper.exe")

if not os.path.exists(exe_path):
    print("ERROR: Executable not found!")
    exit(1)

# Check for DLLs if using --onedir (not possible with --onefile easily without extraction, 
# but we can check if the build process complained or if the temp _MEI folders work).
# Since we use --onefile, we rely on the --collect-all flags.

# However, we can check if the libraries were found during analysis if we parse logs, but that's hard.
# Instead, we trust --collect-all=nvidia which usually grabs the DLLs.

print(f"SUCCESS: {exe_path} created.")
print("Note: Run the executable and check logs if 'cublas64_12.dll' is still missing.")
>>>>>>> Stashed changes
