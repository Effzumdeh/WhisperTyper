# WhisperTyper

**A local, privacy-first voice-to-text tool for Windows that runs completely offline. No API keys, no cloud data.**

WhisperTyper brings the power of OpenAI's Whisper model directly to your desktop, allowing you to dictate text into *any* application with global hotkey support.

## Privacy-First Philosophy
Your voice and text data never leaves your machine. WhisperTyper is built from the ground up to ensure complete offline functionality using local LLMs and local transcription.

## Key Features

* **Local Whisper**: Runs `faster-whisper` entirely on your hardware for blistering fast and accurate transcriptions.
* **Smart Rewriting via Ollama**: Pass your transcribed text through a local LLM to fix grammar, translate languages, or change the tone before it's typed.
* **Hardware Fallbacks**: Automatically detects NVIDIA GPUs (CUDA) and supports AMD HIP acceleration. Falls back to CPU transparently if needed.
* **Live Preview**: Real-time transcription feedback in a clean, unobtrusive overlay as you speak.
* **Global Hotkey & Fast Toggle**: Use `Ctrl+Alt+Shift+S` to start or stop recording instantly, without switching windows.
