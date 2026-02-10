# Mouse Movement Recorder

Records mouse movements at 50Hz for research data collection.

## Requirements

- Windows 10/11
- Python 3.10+ (with "Add to PATH" enabled)

## Quick Start

```
git clone https://github.com/YOUR_ORG/mouse-recorder-client.git
cd mouse-recorder-client
run.bat
```

Or double-click `run.bat` after cloning.

## Usage

1. **First run**: Enter your username when prompted
2. **Recording**: Move your mouse naturally, press `Ctrl+C` to stop
3. **Submit**: Zip your `recordings/username/` folder and upload

```
==================================================
MOUSE MOVEMENT RECORDER
==================================================
Sample rate: 50Hz (fixed)

Enter your username (e.g., john_doe): yourname

Press ENTER to start recording...
Recording... 1542 events (45s)
^C
Recording complete!

When ready to submit, zip the folder:
  recordings/yourname/
Then upload yourname.zip to the shared folder.
```

## Output

```
recordings/
└── yourname/
    ├── 20260210_175530/
    │   └── log_00001.csv
    └── 20260210_183012/
        └── log_00001.csv
```

Each session creates a timestamped folder with CSV files.

## Data Format

```csv
1707580000.000000,MOUSE,-5,12,MOVE
1707580000.020000,MOUSE,3,-2,MOVE
1707580000.040000,MOUSE,0,0,CLICK_DOWN
```

- Only **movement deltas** (dx, dy) are recorded
- **No absolute positions** - your screen layout is not captured
- **No keystrokes** - only mouse movements and clicks

## Troubleshooting

**"Python not found"**
1. Install Python from [python.org](https://www.python.org/downloads/)
2. **Important**: Check "Add Python to PATH" during installation
3. Restart your terminal and try again

**"Permission denied"**
- Run Command Prompt as Administrator

## Questions?

Contact the project maintainer.