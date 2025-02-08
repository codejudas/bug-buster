from typing import List
from llama_index.core.workflow import Event

from src.workflows.stacktrace.model import RawStackFrame


class ParsedStackFramesEvent(Event):
  frames: List[RawStackFrame]
  commit: str
  repo: str