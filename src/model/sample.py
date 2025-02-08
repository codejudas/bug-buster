from pydantic import BaseModel, ConfigDict

class Sample(BaseModel):
    model_config = ConfigDict(frozen=True)

    stacktrace: str
    commit: str 
    repo: str
    language: str
