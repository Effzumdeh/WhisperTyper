
import subprocess
import sys

print("Running src/main.py and capturing stderr to error_log.txt...")
with open("error_log.txt", "w") as f:
    result = subprocess.run([sys.executable, "src/main.py"], stdout=f, stderr=f)
    print(f"Process finished with code {result.returncode}")
