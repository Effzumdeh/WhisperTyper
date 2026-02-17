
import os
import tempfile

lock_file = os.path.join(tempfile.gettempdir(), 'whispertyper.lock')
if os.path.exists(lock_file):
    try:
        os.remove(lock_file)
        print(f"Removed lock file: {lock_file}")
    except Exception as e:
        print(f"Failed to remove lock file: {e}")
else:
    print("No lock file found.")
