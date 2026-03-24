import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

from src.utils.logger import logger

STATE_FILE = "state.json"


@dataclass
class GameState:
    """Tracks the current game automation state."""

    current_screen: str = "unknown"
    resources_collected: int = 0
    teams_joined: int = 0
    daily_tasks_completed: bool = False
    timers_checked: int = 0
    last_daily_reset: float = 0.0
    errors: int = 0
    last_error: str = ""
    task_timestamps: dict[str, float] = field(default_factory=dict)

    def mark_task_run(self, task_name: str) -> None:
        """Record when a task was last run."""
        self.task_timestamps[task_name] = time.time()

    def time_since_task(self, task_name: str) -> float:
        """Seconds since a task was last run. Returns inf if never run."""
        ts = self.task_timestamps.get(task_name, 0)
        if ts == 0:
            return float("inf")
        return time.time() - ts

    def save(self, path: str = STATE_FILE) -> None:
        """Persist state to JSON file."""
        try:
            Path(path).write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        except Exception as e:
            logger.error("Failed to save state: %s", e)

    @classmethod
    def load(cls, path: str = STATE_FILE) -> "GameState":
        """Load state from JSON file, or return fresh state if not found."""
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            return cls(**data)
        except (FileNotFoundError, json.JSONDecodeError):
            return cls()
