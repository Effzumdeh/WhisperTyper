# Manual Test Plan: WhisperTyper

## 1. Normal Dictation Flow
- **Goal**: Verify basic recording and transcription.
- **Pre-requisites**: App running, Microphone connected.
- **Steps**:
    1. Open "Notepad".
    2. Hold `Ctrl+Alt+S` (or configured hotkey).
    3. Listen for "High Beep" (Start).
    4. Speak a sentence (e.g., "Hello world, this is a test.").
    5. Release Hotkey.
    6. Listen for "Low Beep" (Stop).
    7. Wait for "Spinner" on overlay.
    8. Verify text "Hello world, this is a test" appears in Notepad.

## 2. Panic Button
- **Goal**: Verify cancellation logic.
- **Steps**:
    1. Hold Hotkey.
    2. Speak.
    3. While holding, press `ESC`.
    4. Listen for "Cancel Beep".
    5. Release Hotkey.
    6. Verify **NO text** is pasted.
    7. Verify Overlay returns to "Ready" immediately.

## 3. Focus Stealing Check
- **Goal**: Ensure Overlay doesn't crash user workflow.
- **Steps**:
    1. Open a browser and click on the address bar.
    2. Invoke WhisperTyper (Start Recording).
    3. Ensure the blinking cursor in the address bar **remains active** (does not disappear).
    4. Type on keyboard while recording (should still work in browser).

## 4. Clipboard Hygiene
- **Goal**: Ensure user's clipboard is not lost.
- **Steps**:
    1. Copy the word "IMPORTANT_DATA" to clipboard.
    2. Perform a Dictation (Test Case 1).
    3. After text is injected, press `Ctrl+V`.
    4. Verify "IMPORTANT_DATA" is pasted, NOT the dictated text.

## 5. Hot/Unplug Microphone
- **Goal**: Verify resilience.
- **Steps**:
    1. Unplug microphone.
    2. Try to record.
    3. Verify App doesn't crash (might show error or do nothing).
    4. Re-plug microphone.
    5. Try to record again.
    6. Verify it works (if hot-plug logic is active) or requires restart? 
       *(Note: Current implementation `sd.query_devices` is at startup, but `AudioService` creates stream on `start_stream`. It should pick up if default device changes or might need restart depending on OS).*
