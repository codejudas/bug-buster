
import json
import os
from typing import Type, TypeVar

from pydantic import BaseModel

ObjT = TypeVar('ObjT', bound=BaseModel)

class Database:
  """In-memory database which backs up to FS"""
  PATH = '/tmp/bugbuster.db.json'

  def __init__(self) -> None:
    if os.path.exists(self.PATH):
      with open(self.PATH, 'r') as f:
        self.data = json.load(f)
    else:
      self.data = {}
  
  def get(self, key: str, obj_type: Type[ObjT]) -> ObjT | None:
    if key not in self.data:
      return None

    return obj_type.model_validate(json.loads(self.data[key]))
  
  def set(self, key: str, val: ObjT):
    self.data[key] = val.model_dump_json()
    with open(self.PATH, 'w') as f:
      f.write(json.dumps(self.data))
      f.flush()