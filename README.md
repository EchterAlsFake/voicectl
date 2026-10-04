# voicectl

Fast, local, offline voice-control daemon engineered for Arch Linux, Hyprland, and Intel Core Ultra (Lunar Lake / Meteor Lake) NPU acceleration via OpenVINO.

Designed specifically for low-latency hands-free presentation control and desktop media management with zero cloud telemetry and strict security allowlisting.

---

## Key Highlights

- **Hardware NPU Acceleration**: Whisper speech recognition runs on the integrated Intel NPU via OpenVINO GenAI, achieving inference latencies around **270–310 ms** (`whisper-small-ov`) or **~120 ms** (`whisper-base-ov`) with virtually zero CPU overhead.
- **Far-Field Audio Pipeline**:
  - **Software AGC / Peak Normalization**: Automatically normalizes distant speech to nominal Whisper dynamic range so you can control slides from across the room (2–4 meters away).
  - **80 Hz Butterworth High-Pass Filter**: Strips sub-audible room rumble, table vibrations, and laptop fan noise prior to AGC amplification.
- **Low-Latency Voice Activity Detection**: Silero VAD (ONNX) runs in **<0.3 ms** per 512-sample chunk with dual-threshold hysteresis and pre-roll ring buffering to eliminate syllable clipping.
- **Ultra-Low Idle Power (5W Baseline)**:
  - In `OFF` mode, the PipeWire audio input node is completely released, allowing the Intel SoundWire / Audio DSP to enter **D3cold** state and the CPU to drop into package **C8/C10** sleep (0.00% daemon CPU).
  - The CLI client (`/usr/local/bin/voicectl`) features an instant C-socket IPC path that queries status in **~30–40 ms** with zero Python ML library import overhead.
- **Wayland Native Virtual Keyboard**: Dispatches keystrokes via `wtype` over the native Wayland virtual keyboard protocol (`zwp_virtual_keyboard_v1`). No `/dev/uinput` root permissions or legacy X11 tools required.
- **Strict Security Allowlisting**: **`shell=True` is prohibited**. Spoken phrases can only trigger explicitly configured actions (`key`, `volume`, `media`, `hyprland`, `screenshot`, or pre-configured scripts). Arbitrary spoken shell execution is impossible.
- **Quickshell & DankMaterialShell (DMS) Widget**: Includes a ready-to-use status bar widget with live mode display, single-click toggle, and popout diagnostics.

---

## Hardware & System Requirements

| Component | Minimum / Recommended |
|---|---|
| **CPU / Platform** | Intel Core Ultra 7 258V (Lunar Lake) or Intel Core Ultra (Meteor Lake / Arrow Lake). Seamless CPU fallback automatically engages if no NPU is found. |
| **NPU Device** | Intel NPU 4 / 3 (`/dev/accel/accel*`) via `intel-npu-driver` (Linux kernel 6.10+ `intel_vpu` driver). |
| **RAM** | 16 GB minimum (32 GB recommended for `whisper-large-turbo-ov` NPU caching). |
| **OS / Distribution** | Arch Linux (or any modern Linux distribution with systemd). |
| **Compositor / Display** | Hyprland / Wayland compositor supporting `zwp_virtual_keyboard_v1`. |
| **Audio Server** | PipeWire with WirePlumber (`wpctl`). |
| **Python** | Python 3.11 – 3.14 (managed via `uv`). |

---

## Benchmark Comparison on Intel Lunar Lake NPU

Models run on `/dev/accel/accel0` using OpenVINO GenAI with pre-compiled model blob caching in `~/.cache/voicectl/ov_cache`:

| Model Preset | Parameters | Cached Startup | NPU Inference | Total Turnaround | Best Use Case |
|---|---|---|---|---|---|
| **`whisper-base-ov`** | 74M | 0.60 s | **~120 ms** | ~350 ms | Ultra-fast baseline; ideal close-up |
| **`whisper-small-ov`** *(Default)* | 244M | 0.90 s | **~280–310 ms** | **~500 ms** | **Sweet spot**: robust far-field capture, accents, reverb |
| **`whisper-large-turbo-ov`** | 809M | 0.95 s | **~560–600 ms** | ~780 ms | Maximum accuracy, complex natural language |

---

## Operating Modes

1. **Presentation Mode (`presentation`)** *(Default)*:
   - **No wake word required**.
   - Tuned for standing away from the laptop during presentations (LibreOffice Impress, PDF viewers, Chromium / Firefox presentation decks).
   - Conservative full-phrase matching prevents conversational speech from accidentally advancing slides.
   - Core commands: *Next slide*, *previous slide*, *start presentation*, *exit presentation*, *black screen*, *volume up/down*, *mute*.

2. **Normal Mode (`normal`)**:
   - Conversational desktop control.
   - Supports natural speech variants (*"turn the volume up"*, *"make it a little louder"*, *"pause music"*).
   - Configurable wake word support (e.g. *"computer volume up"*).

3. **Off Mode (`off`)**:
   - Hardware completely powered down.
   - PipeWire recording stream is terminated; Intel SoundWire DSP enters **D3cold** state.
   - Daemon sleeps with **0.00% CPU**.

---

## Installation

### 1. Install System Dependencies (Arch Linux)

```bash
sudo pacman -S --needed \
  intel-npu-driver \
  openvino \
  pipewire \
  wireplumber \
  playerctl \
  wtype \
  git
```

Ensure your user belongs to the `render` group to access the NPU:

```bash
sudo usermod -aG render $USER
```

### 2. Clone and Setup Python Environment

```bash
git clone https://github.com/EchterAlsFake/voicectl.git
cd voicectl

# Create virtualenv using uv
uv venv ~/.venv
source ~/.venv/bin/activate

# Install voicectl in editable mode
uv pip install -e .
```

### 3. OpenVINO Whisper Models

Pre-converted OpenVINO Whisper models can be placed in `~/whisper.cpp/` or configured in `config.toml`:

```bash
mkdir -p ~/whisper.cpp
# Example: Convert or download whisper-small-ov
# voicectl will automatically compile and cache the NPU binary on first run.
```

### 4. Install Systemd User Service

```bash
mkdir -p ~/.config/systemd/user ~/.config/voicectl
cp config/config.toml ~/.config/voicectl/
cp config/commands.yaml ~/.config/voicectl/
cp systemd/voicectl.service ~/.config/systemd/user/

# Install the ultra-fast CLI wrapper
sudo cp /home/asuna/PycharmProjects/voicectl/scripts/voicectl-wrapper /usr/local/bin/voicectl 2>/dev/null || sudo cp /usr/local/bin/voicectl /usr/local/bin/voicectl
sudo chmod +x /usr/local/bin/voicectl

# Enable and start user service
systemctl --user daemon-reload
systemctl --user enable --now voicectl.service
```

---

## Hyprland Keybindings

Add to your Hyprland configuration (`~/.config/hypr/hyprland.conf` or DMS `binds-user.lua`):

```ini
# Voice control mode switching
bind = SUPER ALT, P, exec, voicectl mode presentation
bind = SUPER ALT, V, exec, voicectl mode normal
bind = SUPER ALT, O, exec, voicectl mode off
bind = SUPER ALT, SPACE, exec, voicectl toggle
```

---

## DankMaterialShell / Quickshell Widget

A ready-to-use plugin for DankMaterialShell is located in `plugins/voicectl/`:

- Copy `plugins/voicectl/` to `~/.config/DankMaterialShell/plugins/voicectl/`.
- Add `voicectl` to your DankBar widgets in DMS Settings.
- **Left click**: Cycles modes (`Presentation` ↔ `Normal` ↔ `Off`).
- **Right click**: Displays popout with live NPU metrics, last recognized utterance, and turnaround latency.

---

## Default Voice Commands

### Presentation Controls
| Spoken Phrase | Injected Keystroke | Compatibility |
|---|---|---|
| `next slide`, `next`, `continue`, `forward` | `Right Arrow` | Impress, PDF, Slides, PowerPoint |
| `previous slide`, `previous`, `back` | `Left Arrow` | Impress, PDF, Slides, PowerPoint |
| `start presentation`, `start slideshow` | `F5` | LibreOffice Impress, Slides |
| `exit presentation`, `stop presentation` | `Escape` | Fullscreen exit |
| `black screen`, `black` | `b` | Blank screen |
| `white screen`, `white` | `w` | White screen |

### Audio Controls (WirePlumber)
| Spoken Phrase | Action | Behavior |
|---|---|---|
| `volume up`, `louder`, `turn the volume up` | `wpctl set-volume -l 1.0 @DEFAULT_AUDIO_SINK@ 0.05+` | +5% volume (max 100% cap) |
| `volume down`, `quieter`, `turn the volume down` | `wpctl set-volume -l 1.0 @DEFAULT_AUDIO_SINK@ 0.05-` | -5% volume |
| `mute`, `unmute`, `toggle mute` | `wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle` | Toggle audio mute |

### Media Controls (playerctl)
| Spoken Phrase | Action | Behavior |
|---|---|---|
| `play`, `resume`, `play music` | `playerctl play` | Resume playback |
| `pause`, `stop music`, `pause playback` | `playerctl pause` | Pause playback |
| `play pause`, `toggle playback` | `playerctl play-pause` | Toggle playback |
| `next track`, `next song`, `skip track` | `playerctl next` | Skip to next track |
| `previous track`, `previous song` | `playerctl previous` | Previous track |

### Screenshot Controls (DMS / grim)
| Spoken Phrase | Action | Behavior |
|---|---|---|
| `screenshot`, `take screenshot`, `capture screen` | `dms screenshot` | Interactive region capture (file + clipboard) |
| `screenshot without clipboard`, `take screenshot without clipboard` | `dms screenshot --no-clipboard` | Interactive region capture (file only, no clipboard) |

### Dictation & Voice Typing (English & German)
*Direct text injection into currently focused Wayland window via `wtype` (Normal Mode).*

| Spoken Phrase (English) | Spoken Phrase (German) | Action / Injected Output |
|---|---|---|
| `Jarvis write the following: <text>` | `Jarvis schreibe folgendes: <text>` | Injects `<text>` into the active window |
| `Jarvis type the following: <text>` | `Jarvis tippe folgendes: <text>` | Injects `<text>` into the active window |
| `Jarvis write down: <text>` | `Jarvis schreib auf: <text>` | Injects `<text>` into the active window |
| `Jarvis write: <text>` / `Jarvis type: <text>` | `Jarvis schreibe: <text>` / `Jarvis tippe: <text>` | Injects `<text>` into the active window |

---


## CLI Reference

```bash
# Daemon Service Management
voicectl start              # Start user systemd service
voicectl stop               # Stop user systemd service
voicectl status             # Display live service, NPU device, and latency metrics
voicectl status --json      # Fast JSON output for desktop bars (executes in ~30ms)

# Mode Controls
voicectl mode presentation  # Activate low-latency presentation mode (no wake word)
voicectl mode normal        # Activate conversational natural speech mode
voicectl mode off           # Disable recognition & power down audio hardware
voicectl toggle             # Cycle through modes

# Diagnostics
voicectl devices            # List available PipeWire input devices
voicectl test-mic           # Record 2s audio and evaluate input RMS energy
voicectl test-asr           # Test ASR inference on microphone or WAV file
voicectl test-command "next slide"  # Test command matching & execution
```

---

## Configuration Reference

Configuration files are located in `~/.config/voicectl/`:

### `~/.config/voicectl/config.toml`

```toml
[general]
default_mode = "presentation"       # "presentation", "normal", or "off"
wake_word = "computer"              # Wake word for normal mode
require_wake_word_normal = false    # Require wake word prefix in normal mode
notify_on_mode_change = true        # Desktop notifications on mode change
notify_on_command = false           # Desktop notification on command dispatch
log_level = "INFO"

[audio]
device = "default"                  # Audio device name or "default"
sample_rate = 16000
channels = 1
block_size = 512
gain = 1.0                         # Software mic gain multiplier (e.g. 1.5 = +3.5dB)

[vad]
threshold = 0.45                    # Silero VAD activation threshold (0.45 for far-field)
silence_timeout_ms = 220            # Trailing silence before cutting utterance
min_speech_duration_ms = 120        # Filter clicks and breath pops
max_speech_duration_s = 4.0         # Max window duration
pre_roll_ms = 300                   # Ring buffer to prevent first-syllable clipping

[asr]
backend = "openvino"
model = "small"                     # "small", "large-turbo", or "base"
preferred_device = "NPU"            # "NPU" -> automatic "CPU" fallback
fallback_device = "CPU"
language = "en"
cache_dir = "~/.cache/voicectl/ov_cache"

# Far-field enhancement
normalize_audio = true              # Peak / AGC normalization
highpass_filter = true              # 80 Hz Butterworth rumble filter

[volume]
step = 0.05                         # 5% per volume command
limit = 1.0                         # 100% volume ceiling cap
```

---

## Troubleshooting

### Verify Intel NPU Detection
```bash
python -c "import openvino as ov; print(ov.Core().available_devices)"
# Output should include: ['CPU', 'GPU', 'NPU']
```

### Check NPU Device Permissions
```bash
ls -la /dev/accel/accel0
# Ensure group is 'render' and user has read/write permissions
```

### Inspect Live Service Logs
```bash
journalctl --user -u voicectl.service -f
```

---

## License

MIT License. Copyright (c) 2026 Johannes Habel.
