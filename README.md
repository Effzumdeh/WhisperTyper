
> [!NOTE]
> This software project was completely written with Agentic AI Tool **Google Antigravity** and the **Gemini 3 Pro (high)** model for **educational purposes only** and is **not actively maintained**.

# WhisperTyper

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![PySide6](https://img.shields.io/badge/GUI-PySide6-green.svg)
![License](https://img.shields.io/badge/license-MIT-orange.svg)
![Privacy](https://img.shields.io/badge/privacy-offline-red.svg)

**A local, privacy-first voice-to-text tool for Windows that runs completely offline. No API keys, no cloud data.**

WhisperTyper brings the power of OpenAI's Whisper model directly to your desktop, allowing you to dictate text into *any* application with global hotkey support.

---

## ✨ Key Features

*   **🔒 Privacy First:** Runs locally using `faster-whisper` and local LLMs (Ollama). Your voice/text data never leaves your machine.
*   **🤖 Smart AI Rewriting (Ollama):** Seamlessly pass your transcribed text through a local LLM to fix grammar, translate languages, or change the tone before it's typed.
*   **👁️ Live Preview:** Real-time transcription feedback in the overlay as you speak. See exactly what the AI hears before it types.
*   **🖥️ Smart Overlay:** Non-intrusive, always-on-top overlay that provides visual feedback without stealing focus.
*   **🚀 Hardware Aware:** Automatically detects NVIDIA GPUs (CUDA) and supports **AMD HIP** acceleration. Falls back to CPU transparently if needed.
*   **🎙️ Modern Audio:** Advanced filtering for Windows audio devices (prioritizes WASAPI, removes duplicates).
*   **⚡ Fast & Fluid:** Global Hotkey (`Ctrl+Alt+Shift+S`) to toggle recording instantly. Supports **Hot-Swapping** models without restarting.
*   **🛠️ User Friendly:** System Tray integration, Smart Language Detection, and Hallucination Filtering.
*   **🔄 Factory Reset:** Easily restore default settings via the Settings dialog.
*   **🧠 Smart Hardware Detection:** Prioritizes NVIDIA GPUs (CUDA), supports experimental AMD HIP, and transparently falls back to CPU for reliable performance on any machine.

---

## 📥 Installation

### For Users
1.  Download the latest release (`.exe` or `.zip`) from the [Releases](#) page.
2.  Run `WhisperTyper.exe`.
3.  The app runs in the system tray. Use **Ctrl+Alt+Shift+S** to start dictating!

### For Developers

**Prerequisites:** Python 3.10+

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/yourusername/whisper-typer.git
    cd whisper-typer
    ```

2.  **Install dependencies:**
    This project uses `uv` for fast dependency management, but supports standard pip.
    ```bash
    # Option A: Using uv (Recommended)
    uv sync
    
    # Option B: Standard pip
    pip install -r requirements.txt
    ```

3.  **Run the application:**
    ```bash
    uv run src/main.py
    # or
    python src/main.py
    ```

---

## 🏗️ Architecture

WhisperTyper follows a strictly modular **Controller-Service** architecture to ensure stability and responsiveness. It uses **Qt Signals & Slots** to safely bridge the gap between background worker threads (Audio Capture, Inference) and the main UI thread, ensuring the interface never freezes.

```mermaid
graph TD
    User[User Voice] --> |Audio Stream| Audio[Audio Service]
    
    subgraph Core [Core Logic]
        Audio --> |Raw Data| Inference[Inference Service]
        Inference --> |Data| Whisper[Faster-Whisper Model]
        Whisper --> |Text| Inference
        Inference --> |Text| LLM[LLM Client (Ollama)]
        LLM --> |Refined Text| Injector[Text Injector]
    end
    
    Injector --> |Key Events| ActiveApp[Active Application]
    
    subgraph UI [User Interface]
        Tray[Tray Icon] --> |Control| Controller[App Controller]
        Controller --> |Status| Overlay[Visual Overlay]
    end
    
    Controller --> Audio
    Controller --> Inference
    
    subgraph Utils [Utilities]
        Config[Config Manager]
        Hardware[Hardware Manager]
    end
    
    Controller -.-> Config
    Inference -.-> Hardware
```

---

## 🔧 Troubleshooting

*   **Microphone Permissions:** Ensure WhisperTyper has permission to access your microphone in **Windows Settings > Privacy > Microphone**.
*   **Antivirus:** Some antivirus software may flag the text injection (keyboard simulation) as suspicious. Add an exception if necessary.
*   **Smart AI Rewriting (Local LLM):** Ensure that you have downloaded and installed [Ollama](https://ollama.com/) and that the service is running locally. You must download a model (like `llama3` or `mistral`) via your terminal (`ollama run llama3`) before the application can select it in Settings.
*   **Hardware Acceleration:**
    *   **NVIDIA (CUDA):** Automatically detected and used (Best Performance).
    *   **AMD (HIP):** Experimental support available via Settings. Requires [AMD HIP SDK](https://www.amd.com/en/developer/resources/rocm-hub/hip-sdk.html).
    *   **Force CPU Mode:** If you experience instability or high GPU usage with Live Preview, you can force CPU mode in Settings (only visible if a GPU is detected).
    *   **Live Preview:** This feature requires significant resources. If you are on a CPU-only machine, it will be marked as "High CPU Usage" in settings.

---

## 📜 License

Distributed under the MIT License. See `LICENSE` for more information.
