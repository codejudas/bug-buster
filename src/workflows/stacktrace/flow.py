
from typing import List
from llama_index.core.workflow import (
    StartEvent,
    StopEvent,
    Workflow,
    step,
    Context,
)
from llama_index.llms.openai import (
  OpenAI
)
from github import Github, Auth # type: ignore

from src import logging
from src.config import Config
from src.model.sample import Sample
from src.workflows.common_events import ProgressEvent
from src.workflows.stacktrace.events import ParsedStackFramesEvent
from src.workflows.stacktrace.model import RelevantStackFrames

log = logging.get_logger(__name__)

print(f'GH TOKEN {Config.GITHUB_TOKEN}')
gh_client = Github(auth=Auth.Token(Config.GITHUB_TOKEN))


class StacktraceAgentFlow(Workflow):
  """
  Graph does call all steps with the target input event, so does fan-out

  Stack Trace Steps
  1. Enrich the stack trace by resolving to github (ask the agent to list files from the stack trace)
  2. Fetch and refine the snippets
  3. Diagnose the root cause
  4. Check if fixable in code
  5. Propose a high level fix + summary
  6. While bug not fixed, pick a file to edit to fix
  7. (Optional) Generate a test
  8. Generate PR title + description

  Chat steps
  1. Understand what to do
  2. Call tool to rediagnose the issue (StackTraceAgent), 

  DB Updates happen from streaming events, same as updates

  Maybe we want to structure this as re-entrant anywhere?
  Start looks at current state and emits correct event to next place? Then all the other steps could be "reusable" no matter the context

  """
  llm = OpenAI(model="gpt-4o")

  @step
  async def parse_stacktrace(self, ctx: Context, ev: StartEvent) -> ParsedStackFramesEvent:
    s: Sample = ev.sample

    # Let user know we have started looking at the stack trace
    ctx.write_event_to_stream(ProgressEvent(message='analyzing stack trace'))

    prompt = f"""You are an expert software engineer who is tasked with debugging a stack trace that happened in production.
    You will be given a stack trace and the name of the repository where the code which produced this error exists.
    You must return a list of files and methods from the stack trace that would be useful to view to understand the error. 
    This list may not include all the files in the stack trace, you should only include the ones you think are relevant to the error.

    Examples of non-relevant stack frames are:
    - Stack frames which are from library code likely outside of the repository
    - Stack frames which are from the language's standard library
    - Stack frames which are from tests (except the first frame after the error which might be useful to see how the function producing the error was called).

    # Repository
    The error occurred in the {s.language} {s.repo} repository.

    # Stack Trace
    {s.stacktrace}
"""
    sllm = self.llm.as_structured_llm(RelevantStackFrames)
    response = await sllm.acomplete(prompt)
    log.info(f"Got response: {response.text}")
    # files = {}
    for frame in response.raw.frames:
      ctx.write_event_to_stream(ProgressEvent(message=f'resolving {frame.path}'))

      # Broadly two types of stack traces
      # 1. Include the file name + path in the stack, eg: python, JS/TS, ruby.
      #   - For these the complexity is that the path will have a prefix not in the repo. 
      #   => To match to repo we could basically list dirs in the root of the repo and find the matching prefix. Probably some edge cases but oh well.
      # 2. Include a class path and the file name, eg: JVM languages
      #   - class path kind of maps to the file path, but not exactly since you can have nested classes for instance
      #   - There is also and extra prefix in the repo, eg : proj/src/java/<... portion that matches the classpath more or less>
      #   => To match just statically add the prefix.

      log.info(f"Searching for {frame.path} with pattern {file_pattern}")
      
      # Store results in files dict
      # files[frame.path] = results
      
    return ParsedStackFramesEvent(frames=response.raw.frames, commit=s.commit, repo=s.repo)
  
  @step
  async def fetch_files(self, ctx: Context, ev: ParsedStackFramesEvent) -> StopEvent:
    # How to go from stack trace path to path in the repo in a good way? Options:
    # 1. Get the root dir contents, ask the LLM to pick next step each time... Could be a lot of LLM calls, how do you cache?
    #   - LLM calls are expensive, so want to avoid asking.. 
    # 2. Recursively get all the files or alternatively just the directories of the repo, give that to LLM and ask it to pick the path for each frame..
    #   - The repo might be huge, ie web-ui, probably like 50k files? 100k?.
    # 3. Use search_code endpoint with symbol: the last thing with some heuristics to try and get the class -> file

    unique_files = { f.path for f in ev.frames }
    for f_path in unique_files:
      ctx.write_event_to_stream(ProgressEvent(message=f'fetching file'))
      log.info(f'Fetching {f_path} from GitHub', commit=ev.commit, repo=ev.repo)
      # gh_repo.get_repo()

    return StopEvent(result='done')

