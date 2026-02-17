import numpy as np
import sounddevice as sd
import logging
import threading

logger = logging.getLogger(__name__)

def play_tone(frequency: float = 440.0, duration: float = 0.1, amplitude: float = 0.2):
    """
    Generates and plays a sine wave tone in a non-blocking thread.
    """
    def _play():
        try:
            samplerate = 44100
            t = np.linspace(0, duration, int(samplerate * duration), False)
            tone = amplitude * np.sin(2 * np.pi * frequency * t)
            
            # Apply fade in/out to avoid clicking
            fade_len = int(0.01 * samplerate) # 10ms
            if len(tone) > 2 * fade_len:
                tone[:fade_len] *= np.linspace(0, 1, fade_len)
                tone[-fade_len:] *= np.linspace(1, 0, fade_len)
            
            sd.play(tone.astype(np.float32), samplerate)
            sd.wait()
        except Exception as e:
            logger.error(f"Failed to play sound: {e}")

    threading.Thread(target=_play, daemon=True).start()

def play_start_sound():
    play_tone(800.0, 0.15)

def play_stop_sound():
    play_tone(400.0, 0.15)

def play_error_sound():
    # Double beep
    def _double():
        play_tone(150.0, 0.15)
        sd.sleep(200)
        play_tone(150.0, 0.15)
    threading.Thread(target=_double, daemon=True).start()

def play_cancel_sound():
    play_tone(300.0, 0.1)
