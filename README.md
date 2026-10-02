# voicectl

Fast, local, offline voice-control system designed for Arch Linux, Hyprland, and Intel Core Ultra 7 (Lunar Lake) NPU acceleration via OpenVINO.

---

## Features

- **Intel Lunar Lake NPU Acceleration**: Whisper speech recognition runs on the integrated Intel NPU via OpenVINO GenAI, delivering end-to-end command latencies around **140–200 ms** with virtually zero CPU usage during inference.
- **Automatic CPU Fallback**: Automatically switches to CPU inference if NPU hardware/driver is unavailable.
- **Silero VAD (ONNX)**: Lightweight Voice Activity Detection runs in **<0.3 ms** per chunk with ring-buffered pre-roll, preventing syllable clipping and reducing idle CPU usage to ~4%.
- **Wayland Native Input Injection**: Uses `wtype` over the Wayland virtual-keyboard protocol (`zwp_virtual_keyboard_v1`) without requiring `/dev/uinput` root permissions or X11 tools.
- **Safe & Allowlisted**: No arbitrary shell command execution (`shell=True` is prohibited). All actions (keys, audio volume, media, Hyprland dispatchers) are explicitly mapped and allowlisted.
- **PipeWire & WirePlumber Integration**: Volume control via `wpctl` with customizable volume steps and max volume ceiling limit (default 100%).
- **MPRIS Media Player Control**: Seamless integration with `playerctl` for play, pause, play-pause, next track, and previous track.
- **Systemd User Service**: Starts automatically in the user graphical session, logs to journalctl, and maintains IPC over a local UNIX socket.
- **Hyprland Keybindings**: Instant mode switching via Hyprland bindings (`SUPER + ALT + V`, `SUPER + ALT + P`, `SUPER + ALT + O`).

---

## Operating Modes

1. **Presentation Mode (`presentation`)**:
   - **No wake word required**.
   - Optimized for standing away from the laptop during presentations (LibreOffice Impress, Chromium/Firefox web slides, PDF viewers).
   - Conservative matching: strict full-utterance matching prevents accidental triggering from conversational speech (e.g. *"on the next slide..."* will **not** trigger).
   - Available commands: Next slide, previous slide, start presentation, exit presentation, black screen, white screen, volume up/down, mute, pause/play.

2. **Normal Mode (`normal`)**:
   - For desktop and media control.
   - Supports natural speech phrasing (e.g., *"turn the volume up"*, *"make it a little louder"*, *"pause the music"*).
   - Optional configurable wake word (e.g., *"computer volume up"*).

3. **Off Mode (`off`)**:
   - Daemon remains active but audio input is ignored without running speech recognition.

---

## CLI Usage

```bash
# Manage daemon service
voicectl start              # Start systemd user service
voicectl stop               # Stop systemd user service
voicectl status             # Display live service, NPU, mic, and latency status

# Change operating modes
voicectl mode presentation  # Switch to presentation mode (no wake word)
voicectl mode normal        # Switch to normal desktop mode
voicectl mode off           # Mute/disable voice control

# Diagnostics & Testing
voicectl devices            # List available audio input devices
voicectl test-mic           # Record 2s sample and test mic input level
voicectl test-asr           # Test speech recognition on microphone or audio file
voicectl test-command "next slide"  # Test command normalization, matching, and action

# Foreground debugging
voicectl run                # Run daemon directly in the terminal
```

---

## Hyprland Keybindings

The following global shortcuts are configured in `~/.config/hypr/dms/binds-user.lua`:

| Shortcut | Action | Description |
|---|---|---|
| `SUPER + ALT + P` | `voicectl mode presentation` | Enable Presentation Mode |
| `SUPER + ALT + V` | `voicectl mode normal` | Enable Normal Mode |
| `SUPER + ALT + O` | `voicectl mode off` | Disable Voice Control |

---

## Quickshell / DankMaterialShell (DMS) Widget

A native plugin is installed at `~/.config/DankMaterialShell/plugins/voicectl/`:

- **Status Bar Indicator**: Visible on your DankBar (right widgets, next to `hdrToggle`).
  - `PRESENT` (Slideshow icon): Presentation mode active (wake word not needed).
  - `VOICE` (Microphone icon): Normal mode active.
  - `OFF` (Muted microphone icon): Voice control disabled.
- **Mouse Interactions**:
  - **Left Click**: Cycles through operating modes (`Presentation` ↔ `Normal` ↔ `Off`).
  - **Right Click**: Opens interactive popout showing live NPU device status, last recognized command, recognition latency, and one-click mode switches.
- **Control Center**: Integrated tile in the DMS Control Center.
- **DMS Settings**: Configure label display and background polling interval under DMS Settings -> Plugins.

---

## Default Voice Commands

### Presentation Controls
| Spoken Phrase | Injected Key / Action | Compatible Applications |
|---|---|---|
| `next slide`, `next`, `continue`, `go forward` | `Right Arrow` | Impress, PDF, Slides, PowerPoint |
| `previous slide`, `previous`, `back`, `go back` | `Left Arrow` | Impress, PDF, Slides, PowerPoint |
| `start presentation`, `start slideshow` | `F5` | LibreOffice Impress, PowerPoint |
| `exit presentation`, `stop presentation` | `Escape` | Fullscreen presentation exit |
| `black screen`, `black` | `b` | Blank screen in presentation apps |
| `white screen`, `white` | `w` | White screen in presentation apps |

### Audio Controls (WirePlumber)
| Spoken Phrase | Action | Behavior |
|---|---|---|
| `volume up`, `louder`, `turn the volume up` | `wpctl set-volume -l 1.0 @DEFAULT_AUDIO_SINK@ 0.05+` | +5% volume (capped at 100%) |
| `volume down`, `quieter`, `turn the volume down` | `wpctl set-volume -l 1.0 @DEFAULT_AUDIO_SINK@ 0.05-` | -5% volume |
| `mute`, `unmute`, `toggle mute` | `wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle` | Toggle audio mute |

### Media Controls (playerctl)
| Spoken Phrase | Action | Behavior |
|---|---|---|
| `play`, `resume`, `play music` | `playerctl play` | Resume playback |
| `pause`, `stop music`, `pause playback` | `playerctl pause` | Pause playback |
| `play pause`, `toggle playback` | `playerctl play-pause` | Toggle playback |
| `next track`, `next song`, `skip track` | `playerctl next` | Skip to next track |
| `previous track`, `previous song` | `playerctl previous` | Return to previous track |

---

## Configuration

Configuration files are located in `~/.config/voicectl/`:

### 1. `~/.config/voicectl/config.toml`

```toml
[general]
default_mode = "presentation"       # "presentation", "normal", or "off"
wake_word = "computer"              # Wake word for normal mode
require_wake_word_normal = false    # Require wake word prefix in normal mode
notify_on_mode_change = true        # Desktop notification on mode change
notify_on_command = false           # Desktop notification on each command
log_level = "INFO"

[audio]
device = "default"                  # Audio device (default PipeWire mic)
sample_rate = 16000
channels = 1
block_size = 512

[vad]
threshold = 0.45                    # Silero VAD probability threshold (0.45 for far-field sensitivity)
silence_timeout_ms = 220            # Silence duration before ending utterance
min_speech_duration_ms = 120        # Minimum duration to filter clicks/pops
max_speech_duration_s = 4.0         # Maximum utterance duration
pre_roll_ms = 300                   # Pre-roll ring buffer duration (preserves initial phonemes)

[asr]
backend = "openvino"
# Model presets:
#   "small"       - 244M params, ~270-310ms NPU latency (Default & recommended: robust far-field accuracy + speed)
#   "large-turbo" - 809M params, ~560-600ms NPU latency (Maximum comprehension, handles conversational complex commands)
#   "base"        - 74M params, ~120ms NPU latency (Ultra-fast baseline)
model = "small"

preferred_device = "NPU"            # "NPU", "CPU", or "GPU"
fallback_device = "CPU"
language = "en"
cache_dir = "~/.cache/voicectl/ov_cache"

# Far-field enhancement: Software AGC / Peak normalization & 80Hz rumble filter
normalize_audio = true              # Software AGC scales distant speech to nominal Whisper level
highpass_filter = true              # 80 Hz Butterworth filter strips room/fan rumble before AGC

[volume]
step = 0.05                         # 5% per volume command
limit = 1.0                         # 100% volume ceiling cap
```

### 2. `~/.config/voicectl/commands.yaml`

Easily add custom aliases or actions:

```yaml
commands:
  my_custom_command:
    description: "My custom action"
    action:
      type: key          # "key", "volume", "media", "hyprland", or "script"
      key: Page_Down
    phrases:
      - "page down"
      - "scroll down"
    profiles:
      - presentation
      - normal
```

---

## Troubleshooting & Diagnostics

### Check Service Status
```bash
voicectl status
```

### Inspect Live Logs
```bash
journalctl --user -u voicectl -f
```

### Verify Intel NPU Detection
```bash
python -c "import openvino as ov; print(ov.Core().available_devices)"
# Expected output: ['CPU', 'GPU', 'NPU']
```

### Check Intel NPU Kernel Module
```bash
ls -la /dev/accel/accel0
dmesg | grep -i intel_vpu
```

### Test Microphone Audio Levels
```bash
voicectl test-mic
```

### Test ASR Offline Performance
```bash
voicectl test-asr
```
