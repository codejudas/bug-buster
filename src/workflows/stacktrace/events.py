from typing import List
from llama_index.core.workflow import Event

from src.model.sample import Sample
from src.workflows.stacktrace.model import ResolvedFile, StackFrame


class ParsedStackFramesEvent(Event):
  frames: List[StackFrame]
  sample: Sample