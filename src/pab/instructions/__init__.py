"""PAB Instruction Manager."""

from pab.instructions.differ import compare_instruction_texts
from pab.instructions.manager import InstructionManager
from pab.instructions.merger import merge_instruction_rules

__all__ = ["InstructionManager", "compare_instruction_texts", "merge_instruction_rules"]
