#!/usr/bin/env python3
"""Mouse Movement Recorder - Standalone Client (Windows)

Records mouse movements at 50Hz for research data collection.
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
SAMPLE_INTERVAL_SEC = 1.0 / SAMPLE_RATE_HZ  # 0.02s = 20ms
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
def get_or_create_username() -> str:
    """Get username from user.json or prompt user to create it."""
    if USER_CONFIG_FILE.exists():
        try:
            with open(USER_CONFIG_FILE, "r") as f:
                config = json.load(f)
                username = config.get("username", "").strip()
                if username:
                    return username
        except (json.JSONDecodeError, IOError):
            pass

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

    # Save to user.json
    with open(USER_CONFIG_FILE, "w") as f:
        json.dump({"username": username}, f, indent=2)

    print(f"\nSaved username to {USER_CONFIG_FILE.name}")
    return username


# ============================================================
# WINDOWS MOUSE RECORDING
# ============================================================
class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


def get_screen_resolution() -> tuple[int, int]:
    """Get the primary monitor screen resolution using Windows API."""
    user32 = ctypes.windll.user32
    # SM_CXSCREEN = 0, SM_CYSCREEN = 1
    width = user32.GetSystemMetrics(0)
    height = user32.GetSystemMetrics(1)
    return width, height


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


def record_session(username: str) -> Path:
    """Record mouse movements until Ctrl+C."""
    # Select game first
    metadata = select_game()
    metadata["username"] = username
    metadata["sample_rate_hz"] = SAMPLE_RATE_HZ

    # Detect screen resolution
    screen_width, screen_height = get_screen_resolution()
    metadata["screen_width"] = screen_width
    metadata["screen_height"] = screen_height

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
    print(f"Screen: {screen_width}x{screen_height}")
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

            if left_pressed != last_left_state:
                state = "CLICK_DOWN" if left_pressed else "CLICK_UP"
                writer.write_event(now, 0, 0, state)
                event_count += 1
                if left_pressed:
                    click_count += 1
                last_left_state = left_pressed

            if right_pressed != last_right_state:
                state = "CLICK_DOWN" if right_pressed else "CLICK_UP"
                writer.write_event(now, 0, 0, state)
                event_count += 1
                if right_pressed:
                    click_count += 1
                last_right_state = right_pressed

            # Sample position at 50Hz intervals
            if now >= next_sample_time:
                if get_cursor_pos(ctypes.byref(point)):
                    dx = point.x - last_x
                    dy = point.y - last_y

                    if dx != 0 or dy != 0:
                        state = (
                            "DRAG" if (last_left_state or last_right_state) else "MOVE"
                        )
                        writer.write_event(now, dx, dy, state)
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

    # Get or create username
    username = get_or_create_username()
    print(f"\nLogged in as: {username}")

    # Prompt to start
    print()
    input("Press ENTER to start recording...")

    # Record until Ctrl+C
    session_dir = record_session(username)

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
