import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto

from src.device.base import DeviceController
from src.game.state import GameState


class TaskResult(Enum):
    SUCCESS = auto()
    FAILURE = auto()
    RETRY = auto()
    SKIPPED = auto()


@dataclass
class TaskConfig:
    """Configuration for a task."""
    enabled: bool = True
    priority: int = 5
    cooldown: float = 60.0


class Task(ABC):
    """Abstract base class for automation tasks."""

    def __init__(self, name: str, config: TaskConfig | None = None):
        self.name = name
        self.config = config or TaskConfig()
        self.last_run: float = 0.0
        self.run_count: int = 0
        self.fail_count: int = 0

    def should_run(self, game_state: GameState) -> bool:
        """Check if this task should run now.

        Override in subclasses for additional preconditions.
        """
        if not self.config.enabled:
            return False

        elapsed = time.time() - self.last_run
        return elapsed >= self.config.cooldown

    @abstractmethod
    def execute(self, device: DeviceController, game_state: GameState) -> TaskResult:
        """Execute the task.

        Args:
            device: Device controller for screen interaction.
            game_state: Current game state for context.

        Returns:
            TaskResult indicating outcome.
        """

    def on_complete(self, result: TaskResult, game_state: GameState) -> None:
        """Called after task execution. Update counters and state."""
        self.last_run = time.time()
        self.run_count += 1
        if result == TaskResult.FAILURE:
            self.fail_count += 1
        game_state.mark_task_run(self.name)
