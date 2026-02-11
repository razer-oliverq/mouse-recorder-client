#!/usr/bin/env python3
"""Mouse Movement Replay - Visualizes recorded mouse sessions.

Reads recordings from the recordings/ directory and replays them
in a popup window with highlighted circles for clicks.

Usage:
    python replay.py [session_path]

If no session_path provided, lists available sessions to choose from.
"""

import csv
import json
import sys
import time
import tkinter as tk
from pathlib import Path
from typing import NamedTuple


SCRIPT_DIR = Path(__file__).parent
RECORDINGS_DIR = SCRIPT_DIR / "recordings"

# Visual settings
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720
CURSOR_RADIUS = 5
CLICK_CIRCLE_RADIUS = 20
CLICK_CIRCLE_DURATION_MS = 300
LEFT_CLICK_COLOR = "#FF4444"
RIGHT_CLICK_COLOR = "#4444FF"
CURSOR_COLOR = "#00FF00"
TRAIL_COLOR = "#00AA00"
TRAIL_LENGTH = 50


class MouseEvent(NamedTuple):
    timestamp: float
    dx: int
    dy: int
    state: str


def load_session(session_dir: Path) -> tuple[list[MouseEvent], dict]:
    """Load all events from a session directory."""
    events = []

    # Load metadata
    metadata_file = session_dir / "metadata.json"
    metadata = {}
    if metadata_file.exists():
        with open(metadata_file) as f:
            metadata = json.load(f)

    # Find all log files and sort them
    log_files = sorted(session_dir.glob("log_*.csv"))

    for log_file in log_files:
        with open(log_file, newline="") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 5:
                    timestamp = float(row[0])
                    # row[1] is "MOUSE"
                    dx = int(row[2])
                    dy = int(row[3])
                    state = row[4]
                    events.append(MouseEvent(timestamp, dx, dy, state))

    return events, metadata


def list_sessions() -> list[Path]:
    """List all available recording sessions."""
    sessions = []
    if not RECORDINGS_DIR.exists():
        return sessions

    for user_dir in RECORDINGS_DIR.iterdir():
        if user_dir.is_dir():
            for session_dir in user_dir.iterdir():
                if session_dir.is_dir() and (session_dir / "metadata.json").exists():
                    sessions.append(session_dir)

    return sorted(sessions, key=lambda p: p.name, reverse=True)


def select_session() -> Path | None:
    """Interactive session selection."""
    sessions = list_sessions()

    if not sessions:
        print("No recording sessions found in recordings/")
        return None

    print("\nAvailable sessions:")
    print("-" * 60)

    for i, session in enumerate(sessions, 1):
        # Load metadata for display
        try:
            with open(session / "metadata.json") as f:
                meta = json.load(f)
            game = meta.get("game", "Unknown")
            user = meta.get("username", "Unknown")
            print(f"[{i}] {session.parent.name}/{session.name} - {game} ({user})")
        except Exception:
            print(f"[{i}] {session.parent.name}/{session.name}")

    print()

    while True:
        choice = input(f"Select session [1-{len(sessions)}]: ").strip()
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(sessions):
                return sessions[idx]
        except ValueError:
            pass
        print("Invalid selection.")


class ReplayWindow:
    """Tkinter window for replaying mouse movements."""

    def __init__(self, events: list[MouseEvent], metadata: dict):
        self.events = events
        self.metadata = metadata
        self.event_idx = 0
        self.paused = False
        self.speed = 1.0

        # Current cursor position (start at center)
        self.cursor_x = WINDOW_WIDTH // 2
        self.cursor_y = WINDOW_HEIGHT // 2

        # Trail points
        self.trail: list[tuple[int, int]] = []

        # Active click circles (x, y, color, expire_time)
        self.click_circles: list[tuple[int, int, str, float]] = []

        # Setup window
        self.root = tk.Tk()
        self.root.title(self._build_title())
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.configure(bg="black")

        # Canvas for drawing
        self.canvas = tk.Canvas(
            self.root,
            width=WINDOW_WIDTH,
            height=WINDOW_HEIGHT,
            bg="black",
            highlightthickness=0,
        )
        self.canvas.pack()

        # Status bar
        self.status_var = tk.StringVar()
        self.status_label = tk.Label(
            self.root,
            textvariable=self.status_var,
            fg="white",
            bg="black",
            font=("Courier", 10),
        )
        self.status_label.place(x=10, y=10)

        # Controls info
        controls_text = "Space: Pause | +/-: Speed | R: Reset | Q: Quit"
        self.controls_label = tk.Label(
            self.root, text=controls_text, fg="gray", bg="black", font=("Courier", 9)
        )
        self.controls_label.place(x=10, y=WINDOW_HEIGHT - 25)

        # Key bindings
        self.root.bind("<space>", self._toggle_pause)
        self.root.bind("<plus>", self._speed_up)
        self.root.bind("<equal>", self._speed_up)  # = key (shift+= is +)
        self.root.bind("<minus>", self._slow_down)
        self.root.bind("r", self._reset)
        self.root.bind("q", self._quit)
        self.root.bind("<Escape>", self._quit)

        # Start time tracking
        self.replay_start_time = None
        self.last_event_timestamp = None

    def _build_title(self) -> str:
        game = self.metadata.get("game", "Unknown")
        user = self.metadata.get("username", "Unknown")
        return f"Mouse Replay - {game} ({user})"

    def _toggle_pause(self, event=None):
        self.paused = not self.paused
        if not self.paused and self.event_idx < len(self.events):
            # Adjust timing when unpausing
            self.replay_start_time = time.time()
            if self.event_idx > 0:
                self.last_event_timestamp = self.events[self.event_idx - 1].timestamp
            else:
                self.last_event_timestamp = self.events[0].timestamp

    def _speed_up(self, event=None):
        self.speed = min(self.speed * 1.5, 10.0)

    def _slow_down(self, event=None):
        self.speed = max(self.speed / 1.5, 0.1)

    def _reset(self, event=None):
        self.event_idx = 0
        self.cursor_x = WINDOW_WIDTH // 2
        self.cursor_y = WINDOW_HEIGHT // 2
        self.trail.clear()
        self.click_circles.clear()
        self.replay_start_time = None
        self.last_event_timestamp = None
        self.paused = False

    def _quit(self, event=None):
        self.root.quit()

    def _update_status(self):
        progress = f"{self.event_idx}/{len(self.events)}"
        speed_str = f"{self.speed:.1f}x"
        status = f"Events: {progress} | Speed: {speed_str}"
        if self.paused:
            status += " | PAUSED"
        self.status_var.set(status)

    def _draw(self):
        self.canvas.delete("all")

        # Draw trail
        if len(self.trail) > 1:
            for i in range(1, len(self.trail)):
                alpha = i / len(self.trail)
                # Fade effect via line width
                width = max(1, int(3 * alpha))
                self.canvas.create_line(
                    self.trail[i - 1][0],
                    self.trail[i - 1][1],
                    self.trail[i][0],
                    self.trail[i][1],
                    fill=TRAIL_COLOR,
                    width=width,
                )

        # Draw click circles
        current_time = time.time()
        remaining_circles = []
        for cx, cy, color, expire_time in self.click_circles:
            if current_time < expire_time:
                remaining_circles.append((cx, cy, color, expire_time))
                # Fade out effect
                time_left = expire_time - current_time
                ratio = time_left / (CLICK_CIRCLE_DURATION_MS / 1000)
                radius = int(CLICK_CIRCLE_RADIUS * (2 - ratio))
                self.canvas.create_oval(
                    cx - radius,
                    cy - radius,
                    cx + radius,
                    cy + radius,
                    outline=color,
                    width=3,
                )
        self.click_circles = remaining_circles

        # Draw cursor
        self.canvas.create_oval(
            self.cursor_x - CURSOR_RADIUS,
            self.cursor_y - CURSOR_RADIUS,
            self.cursor_x + CURSOR_RADIUS,
            self.cursor_y + CURSOR_RADIUS,
            fill=CURSOR_COLOR,
            outline=CURSOR_COLOR,
        )

    def _process_events(self):
        if self.paused or self.event_idx >= len(self.events):
            return

        current_time = time.time()

        # Initialize timing on first run
        if self.replay_start_time is None:
            self.replay_start_time = current_time
            self.last_event_timestamp = self.events[0].timestamp

        # Process events that should have happened by now
        while self.event_idx < len(self.events):
            event = self.events[self.event_idx]

            # Calculate when this event should play
            time_since_last = event.timestamp - self.last_event_timestamp
            target_time = self.replay_start_time + (time_since_last / self.speed)

            if current_time < target_time:
                break

            # Process this event
            if event.state == "MOVE":
                self.cursor_x += event.dx
                self.cursor_y += event.dy

                # Clamp to window bounds
                self.cursor_x = max(0, min(WINDOW_WIDTH, self.cursor_x))
                self.cursor_y = max(0, min(WINDOW_HEIGHT, self.cursor_y))

                # Add to trail
                self.trail.append((self.cursor_x, self.cursor_y))
                if len(self.trail) > TRAIL_LENGTH:
                    self.trail.pop(0)

            elif event.state == "LEFT_DOWN":
                expire = current_time + (CLICK_CIRCLE_DURATION_MS / 1000)
                self.click_circles.append(
                    (self.cursor_x, self.cursor_y, LEFT_CLICK_COLOR, expire)
                )

            elif event.state == "RIGHT_DOWN":
                expire = current_time + (CLICK_CIRCLE_DURATION_MS / 1000)
                self.click_circles.append(
                    (self.cursor_x, self.cursor_y, RIGHT_CLICK_COLOR, expire)
                )

            self.last_event_timestamp = event.timestamp
            self.replay_start_time = current_time
            self.event_idx += 1

    def _tick(self):
        self._process_events()
        self._draw()
        self._update_status()
        self.root.after(16, self._tick)  # ~60 FPS

    def run(self):
        if not self.events:
            print("No events to replay.")
            return

        print(f"\nReplaying {len(self.events)} events...")
        print("Controls: Space=Pause, +/-=Speed, R=Reset, Q=Quit")

        self._tick()
        self.root.mainloop()


def main():
    # Get session path from argument or interactive selection
    if len(sys.argv) > 1:
        session_path = Path(sys.argv[1])
        if not session_path.exists():
            print(f"Session not found: {session_path}")
            sys.exit(1)
    else:
        session_path = select_session()
        if session_path is None:
            sys.exit(1)

    print(f"\nLoading session: {session_path}")
    events, metadata = load_session(session_path)

    if not events:
        print("No events found in session.")
        sys.exit(1)

    print(f"Loaded {len(events)} events")

    # Create and run replay window
    window = ReplayWindow(events, metadata)
    window.run()


if __name__ == "__main__":
    main()
