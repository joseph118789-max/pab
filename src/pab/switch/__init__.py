"""One-command agent switching and session handoff package."""

from pab.switch.engine import SwitchEngine
from pab.switch.launcher import build_launch_command, execute_native_launch
from pab.switch.models import HandoffManifest, SwitchMode, SwitchPlan, SwitchResult

__all__ = [
    "SwitchEngine",
    "SwitchMode",
    "HandoffManifest",
    "SwitchPlan",
    "SwitchResult",
    "build_launch_command",
    "execute_native_launch",
]
