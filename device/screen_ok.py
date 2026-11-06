#!/usr/bin/env python3
"""screen_ok.py <screenshot>: prints 'app' when the harness's host-screen check (lifecycle.screen_state)
reads the screenshot as the app rather than the bare host page, else what it read. run_apps.sh's early
exit uses it, so a launch moves on only once the screenshot the scorer will judge shows the app."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness.westlake_gap import lifecycle
print(lifecycle.screen_state(Path(sys.argv[1])) or 'unknown')
