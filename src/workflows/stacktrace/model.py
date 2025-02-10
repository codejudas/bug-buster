
from typing import List, Optional
from pydantic import BaseModel, Field


# LLM Models
class FileOffset(BaseModel):
    start: int = Field(description="Start line number of the snippet, inclusive")
    end: int = Field(description="End line number of the snippet, exclusive")

class StackFrame(BaseModel):
    reason: str = Field(description="the reason for including this stack frame in your result.")
    path: str = Field(description="path to the relevant file from the stacktrace. eg: /foo/bar/baz.py")
    method: str = Field(description="name of the method that was called in the stacktrace, omitting parameters. eg: run_workflow")
    lineno: int = Field(description="the line number relevant to the stack frame.")
    is_third_party: bool = Field(description="true if you think the stack frame comes from a third party dependency or the standard library, false otherwise.")


# General purpose models for passing data

class FileId(BaseModel):
    path: str = Field(description="The path to the file in the repository")
    repo: str = Field(description="The repository this file belongs to")
    commit: str = Field(description="The commit sha")
    url: str = Field(description="Url to the file")
    language: str = Field(description="The programming language of this file")

class SnippetOffset(FileOffset):
    """A snippet is a part of a ResolvedFile and also has an optional stack_frame_id"""
    frame_id: Optional[int] = None

class ResolvedFile(BaseModel):
    file_id: FileId = Field(description="Id of this file")
    content: str = Field(description="Entire content of the file")
    snippet_offsets: List[SnippetOffset] = Field(description="Offsets of snippets we care about in this file")

class RelevantStackFrames(BaseModel):
   frames: List[StackFrame] = Field(description="list of relevant stack frames.")

