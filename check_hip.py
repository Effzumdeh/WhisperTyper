import os
import sys
from pathlib import Path

def check_hip():
    print("--- AMD HIP SDK Usage Diagnostic ---")
    print(f"Platform: {sys.platform}")
    
    # 1. Check Env Vars
    print("\n[Environment Variables]")
    candidates = ["HIP_PATH", "AMD_HIP_PATH", "ROCM_PATH", "HIP_ROCCLR_HOME"]
    found = False
    for env in candidates:
        val = os.environ.get(env)
        if val:
            print(f"  {env} = {val} {'(Found!)' if os.path.isdir(val) else '(Path does not exist!)'}")
            found = True
        else:
            print(f"  {env} = [Not Set]")
            
    if not found:
        print("  (!) No standard HIP environment variables found.")
        
    # 2. Check Default Path
    print("\n[Default Install Paths]")
    default_root = Path(r"C:\Program Files\AMD\ROCm")
    if default_root.exists():
        print(f"  Found ROCm root at: {default_root}")
        try:
            versions = [p for p in default_root.iterdir() if p.is_dir()]
            for v in versions:
                 bin_path = v / "bin"
                 print(f"    - Version: {v.name} -> Bin exists? {bin_path.exists()}")
        except Exception as e:
            print(f"    Error reading versions: {e}")
    else:
        print(f"  (!) Default path not found: {default_root}")
        
    print("\n[Summary]")
    if found or default_root.exists():
        print("PASS: HIP SDK components appear to be present.")
        print("If WhisperTyper still says 'No ROCm/HIP SDK Found', restart the app.")
    else:
        print("FAIL: Could not detect AMD HIP SDK.")
        print("Please verify you have installed the 'AMD HIP SDK' from:")
        print("https://www.amd.com/en/developer/resources/rocm-hub/hip-sdk.html")

if __name__ == "__main__":
    check_hip()
    input("\nPress Enter to exit...")
