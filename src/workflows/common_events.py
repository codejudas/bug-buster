from llama_index.core.workflow import Event


class ProgressEvent(Event):
  message: str