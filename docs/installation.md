# Installation

## For End-Users

1. Download the latest release (`.exe` or `.zip`) from the [GitHub Releases](https://github.com/Effzumdeh/WhisperTyper/releases) page.
2. Extract the files if necessary and run `WhisperTyper.exe`.
3. The app will appear in your system tray. 
4. Use **Ctrl+Alt+Shift+S** to start dictating!

## For Developers

**Prerequisites:** Python 3.10+

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Effzumdeh/WhisperTyper.git
   cd WhisperTyper
   ```

2. **Install dependencies:**
   This project uses `uv` for fast dependency management, but also supports standard `pip`.
   
   **Using uv (Recommended):**
   ```bash
   uv sync
   ```
   
   **Using standard pip:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application:**
   ```bash
   uv run src/main.py
   # or
   python src/main.py
   ```
