from llama_index.core.workflow import Event


class ProgressEvent(Event):
  """Used to send a progress updates"""
  message: str