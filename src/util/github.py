
def path_to_class_symbol(path: str) -> str:
  """
  Attempts to get a symbol to lookup in Github:
    org.apache.utils.TarCompressor.java -> TarCompressor
    /path/to/repo/module/submodule/file.py
  """
  return ""