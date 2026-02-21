# Usage & Features

## Global Hotkey
The default hotkey to start and stop dictation is **Ctrl+Alt+Shift+S**. You can use this from any application in Windows. WhisperTyper will capture your voice, transcribe it, and simulate keyboard inputs to type the text wherever your text cursor is currently focused.

## Selecting Models
You can hot-swap Whisper models without restarting the application:
1. Right-click the WhisperTyper tray icon.
2. Open **Settings**.
3. Select your desired Whisper model size (e.g., `tiny`, `base`, `small`, `medium`, `large-v3`). 
Larger models are more accurate but require more VRAM and computing power.

## Smart Rewriting (Ollama Integration)
WhisperTyper can refine your transcribed text using a local Large Language Model (LLM) before injecting it.
1. Download and install [Ollama](https://ollama.com/).
2. Pull a local model via terminal (e.g., `ollama run mistral` or `ollama run llama3`).
3. In WhisperTyper **Settings**, enable the LLM feature and select your desired model.
4. Choose a **Rewrite Style** (e.g., Fix Grammar, Translate to English, Professional Tone).

## Debug Mode
If you encounter issues such as hardware acceleration failing or audio not being captured:
- You can enable specific logging by running the app via the command line.
- Check the fallback features. You can force **CPU Mode** in Settings if your GPU is not supported or experiencing instability.
