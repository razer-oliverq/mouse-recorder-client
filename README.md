# Mouse Movement Recorder

Records mouse movements at 60Hz for research data collection.

## Requirements

- Windows 10/11
- Python 3.10+ (with "Add to PATH" during install)

## Setup

```
python recorder.py
```

Or double-click `run.bat`.

## Recording

1. Enter username (first run only)
2. Enter mouse DPI
3. Select game/application
4. Press Enter to start
5. Press `Ctrl+C` to stop

## Replay

```
python replay.py
```

Controls: `Space` (pause), `+/-` (speed), `R` (reset), `Q` (quit)

## Submit

Zip `recordings/yourname/` and upload to the shared folder.

## Data Format

```csv
timestamp,MOUSE,dx,dy,state
```

States: `MOVE`, `LEFT_DOWN`, `LEFT_UP`, `RIGHT_DOWN`, `RIGHT_UP`

Only deltas recorded — no absolute positions or keystrokes.