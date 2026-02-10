#!/usr/bin/env python3
"""Mouse Movement Recorder - Standalone Client (Windows)

Records mouse movements at 60Hz for research data collection.
Zero external dependencies - uses Windows APIs directly.

Usage:
    python recorder.py

Or double-click run.bat
"""

import ctypes
from ctypes import wintypes
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# ============================================================
# CONFIGURATION (Fixed - do not modify)
# ============================================================
SAMPLE_RATE_HZ = 60
SAMPLE_INTERVAL_SEC = 1.0 / SAMPLE_RATE_HZ  # ~0.0167s = 16.67ms
MAX_LOG_FILE_BYTES = 1 * 1024 * 1024  # 1MB per file

# Paths relative to script location
SCRIPT_DIR = Path(__file__).parent
RECORDINGS_DIR = SCRIPT_DIR / "recordings"
USER_CONFIG_FILE = SCRIPT_DIR / "user.json"


# ============================================================
# ROLLING FILE WRITER
# ============================================================
class RollingWriter:
    """Simple rolling file writer for mouse events."""

    def __init__(self, session_dir: Path):
        self.session_dir = session_dir
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.current_file = None
        self.current_file_num = 0
        self.current_file_size = 0
        self._open_new_file()

    def _open_new_file(self):
        if self.current_file:
            self.current_file.close()
        self.current_file_num += 1
        filename = f"log_{self.current_file_num:05d}.csv"
        filepath = self.session_dir / filename
        self.current_file = open(filepath, "w", buffering=1)
        self.current_file_size = 0
        # Update .current marker
        current_marker = self.session_dir / ".current"
        with open(current_marker, "w") as f:
            f.write(filename)

    def write_event(self, timestamp: float, dx: int, dy: int, state: str):
        line = f"{timestamp:.6f},MOUSE,{dx},{dy},{state}\n"
        self.current_file.write(line)
        self.current_file_size += len(line)
        if self.current_file_size >= MAX_LOG_FILE_BYTES:
            self._open_new_file()

    def close(self):
        if self.current_file:
            self.current_file.close()
            self.current_file = None


# ============================================================
# USER MANAGEMENT
# ============================================================
def load_user_config() -> dict:
    """Load user config from user.json or return empty dict."""
    if USER_CONFIG_FILE.exists():
        try:
            with open(USER_CONFIG_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def save_user_config(config: dict) -> None:
    """Save user config to user.json."""
    with open(USER_CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def get_or_create_username(config: dict) -> str:
    """Get username from config or prompt user to create it."""
    username = config.get("username", "").strip()
    if username:
        return username

    # Prompt for username
    print()
    print("=" * 50)
    print("FIRST TIME SETUP")
    print("=" * 50)
    print()
    username = input("Enter your username (e.g., john_doe): ").strip()

    while not username or not username.replace("_", "").replace("-", "").isalnum():
        print("Invalid username. Use only letters, numbers, underscores, hyphens.")
        username = input("Enter your username: ").strip()

    config["username"] = username
    save_user_config(config)
    print(f"\nSaved username to {USER_CONFIG_FILE.name}")
    return username


def get_or_update_dpi(config: dict) -> int:
    """Get DPI from config or prompt user. Allow editing on each run."""
    current_dpi = config.get("dpi", None)

    print()
    if current_dpi:
        # Show current DPI, allow editing
        dpi_input = input(f"Mouse DPI [{current_dpi}]: ").strip()
        if dpi_input == "":
            return current_dpi
    else:
        # First time - require input
        print(
            "Enter your mouse DPI (check mouse software, common: 400, 800, 1600, 3200)"
        )
        dpi_input = input("Mouse DPI: ").strip()

    # Validate DPI
    while True:
        try:
            dpi = int(dpi_input)
            if 100 <= dpi <= 32000:
                break
            print("DPI should be between 100 and 32000.")
        except ValueError:
            print("Please enter a valid number.")
        dpi_input = input("Mouse DPI: ").strip()

    config["dpi"] = dpi
    save_user_config(config)
    return dpi


# ============================================================
# WINDOWS MOUSE RECORDING
# ============================================================
class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


def select_game() -> dict:
    """Prompt user to select the game/application being recorded."""
    print()
    print("=" * 50)
    print("SELECT GAME/APPLICATION")
    print("=" * 50)
    print()
    print("[1] VALORANT")
    print("[2] CSGO")
    print("[3] Dota 2")
    print("[4] LoL")
    print("[5] PC (general desktop use)")
    print("[6] Other (enter custom name)")
    print()

    games = {
        "1": "VALORANT",
        "2": "CSGO",
        "3": "Dota 2",
        "4": "LoL",
        "5": "PC",
    }

    while True:
        choice = input("Enter choice [1-6]: ").strip()
        if choice in games:
            return {"game": games[choice]}
        elif choice == "6":
            custom = input("Enter game name: ").strip()
            if custom:
                return {"game": custom}
            print("Game name cannot be empty.")
        else:
            print("Invalid choice. Enter 1-6.")


def record_session(username: str, dpi: int) -> Path:
    """Record mouse movements until Ctrl+C."""
    # Select game first
    metadata = select_game()
    metadata["username"] = username
    metadata["dpi"] = dpi
    metadata["sample_rate_hz"] = SAMPLE_RATE_HZ

    # Create session directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_dir = RECORDINGS_DIR / username / timestamp
    metadata["session_id"] = timestamp

    # Save metadata
    session_dir.mkdir(parents=True, exist_ok=True)
    with open(session_dir / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    # Initialize writer
    writer = RollingWriter(session_dir)

    print()
    print("=" * 50)
    print("RECORDING SESSION")
    print("=" * 50)
    print(f"Game: {metadata['game']}")
    print(f"User: {username}")
    print(f"DPI: {dpi}")
    print(f"Sample rate: {SAMPLE_RATE_HZ}Hz")
    print(f"Output: {session_dir}")
    print()
    print("Move your mouse naturally. Press Ctrl+C to stop.")
    print("-" * 50)

    # Windows API setup
    user32 = ctypes.windll.user32
    get_cursor_pos = user32.GetCursorPos
    get_cursor_pos.argtypes = [ctypes.POINTER(POINT)]
    get_cursor_pos.restype = wintypes.BOOL

    get_async_key_state = user32.GetAsyncKeyState
    get_async_key_state.argtypes = [ctypes.c_int]
    get_async_key_state.restype = ctypes.c_short

    VK_LBUTTON = 0x01
    VK_RBUTTON = 0x02

    # Initialize state
    point = POINT()
    get_cursor_pos(ctypes.byref(point))
    last_x, last_y = point.x, point.y
    last_left_state = False
    last_right_state = False
    event_count = 0
    click_count = 0

    start_time = time.time()
    next_sample_time = start_time + SAMPLE_INTERVAL_SEC
    last_status_time = start_time

    try:
        while True:
            now = time.time()

            # Check for click state changes (immediate)
            left_pressed = (get_async_key_state(VK_LBUTTON) & 0x8000) != 0
            right_pressed = (get_async_key_state(VK_RBUTTON) & 0x8000) != 0

            # Left click events
            if left_pressed != last_left_state:
                state = "LEFT_DOWN" if left_pressed else "LEFT_UP"
                writer.write_event(now, 0, 0, state)
                event_count += 1
                if left_pressed:
                    click_count += 1
                last_left_state = left_pressed

            # Right click events
            if right_pressed != last_right_state:
                state = "RIGHT_DOWN" if right_pressed else "RIGHT_UP"
                writer.write_event(now, 0, 0, state)
                event_count += 1
                if right_pressed:
                    click_count += 1
                last_right_state = right_pressed

            # Sample position at target Hz intervals (always MOVE, no DRAG)
            if now >= next_sample_time:
                if get_cursor_pos(ctypes.byref(point)):
                    dx = point.x - last_x
                    dy = point.y - last_y

                    if dx != 0 or dy != 0:
                        writer.write_event(now, dx, dy, "MOVE")
                        event_count += 1
                        last_x, last_y = point.x, point.y

                next_sample_time += SAMPLE_INTERVAL_SEC

            # Status update every 5 seconds
            if now - last_status_time >= 5.0:
                elapsed = now - start_time
                print(f"Recording... {event_count} events ({elapsed:.0f}s)", end="\r")
                last_status_time = now

            time.sleep(0.001)

    except KeyboardInterrupt:
        pass
    finally:
        writer.close()

    actual_duration = time.time() - start_time

    print()
    print("-" * 50)
    print("Recording complete!")
    print(f"Duration: {actual_duration:.1f} seconds")
    print(f"Events: {event_count} ({click_count} clicks)")
    if actual_duration > 0:
        print(f"Actual rate: {event_count / actual_duration:.1f} Hz")
    print(f"Saved to: {session_dir}")

    return session_dir


# ============================================================
# MAIN
# ============================================================
def main():
    # Check Windows
    if sys.platform != "win32":
        print("ERROR: This recorder only works on Windows.")
        print("For macOS/Linux, contact the project maintainer.")
        sys.exit(1)

    print()
    print("=" * 50)
    print("MOUSE MOVEMENT RECORDER")
    print("=" * 50)
    print(f"Sample rate: {SAMPLE_RATE_HZ}Hz (fixed)")
    print()

    # Load user config
    config = load_user_config()

    # Get or create username
    username = get_or_create_username(config)
    print(f"\nLogged in as: {username}")

    # Get or update DPI
    dpi = get_or_update_dpi(config)
    print(f"Mouse DPI: {dpi}")

    # Prompt to start
    print()
    input("Press ENTER to start recording...")

    # Record until Ctrl+C
    session_dir = record_session(username, dpi)

    # Final instructions
    user_folder = RECORDINGS_DIR / username
    print()
    print("=" * 50)
    print("UPLOAD INSTRUCTIONS")
    print("=" * 50)
    print()
    print(f"When ready to submit, zip the folder:")
    print(f"  {user_folder}")
    print()
    print(f"Then upload {username}.zip to the shared folder.")
    print()

    input("Press ENTER to exit...")


if __name__ == "__main__":
    main()
