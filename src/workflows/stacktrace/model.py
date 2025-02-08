
from typing import List
from pydantic import BaseModel, Field

class FileId(BaseModel):
    path: str = Field(description="The path to the file in the repository")
    repo: str = Field(description="The repository this file belongs to")
    commit: str = Field(description="The commit sha")
    url: str = Field(description="Url to the file")
    language: str = Field(description="The programming language of this file")

class ResolvedFile(BaseModel):
    _id: FileId = Field(description="Id of this file")
    content: str = Field(description="Entire content of the file")


class RawStackFrame(BaseModel):
    reason: str = Field(description="the reason for including this stack frame in your result.")
    path: str = Field(description="path to the relevant file from the stacktrace. eg: /foo/bar/baz.py")
    method_name: str = Field(description="name of the method that was called in the stacktrace, omitting parameters. eg: run_workflow")
    lineno: int = Field(description="the line number relevant to the stack frame.")
    is_third_party: bool = Field(description="true if you think the stack frame comes from a third party dependency or the standard library, false otherwise.")


class RelevantStackFrames(BaseModel):
   frames: List[RawStackFrame] = Field(description="list of relevant stack frames.")

