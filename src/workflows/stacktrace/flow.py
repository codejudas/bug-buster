
import textwrap
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
from github import Github, Auth, GithubException

from src import logging
from src.config import Config
from src.model.sample import Sample
from src.workflows.common_events import ProgressEvent
from src.workflows.stacktrace.events import ParsedStackFramesEvent
from src.workflows.stacktrace.model import FileId, FileOffset, RelevantStackFrames, ResolvedFile, SnippetOffset

log = logging.get_logger(__name__)

gh_client = Github(auth=Auth.Token(Config.GITHUB_TOKEN or "SET ME"))


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
  async def parse_stacktrace(self, ctx: Context, ev: StartEvent) -> ParsedStackFramesEvent | StopEvent:
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

    return ParsedStackFramesEvent(frames=response.raw.frames, sample=s)
  
  @step
  async def fetch_files(self, ctx: Context, ev: ParsedStackFramesEvent) -> StopEvent:
    files: dict[str, ResolvedFile] = {}
    for idx, frame in enumerate(ev.frames):
      ctx.write_event_to_stream(ProgressEvent(message=f'resolving {frame.path}:{frame.method}:{frame.lineno}'))
      log.info(f'Resolving {frame.path} in GitHub', commit=ev.sample.commit, repo=ev.sample.repo)

      if frame.path not in files:
        f = self._resolve_file_in_github(ev.sample.language, ev.sample.repo, ev.sample.commit, frame.path)
        if not f:
          log.warning(f'Unable to resolve {frame.path} to a file in Github', frame=frame, repo=ev.sample.repo, commit=ev.sample.commit)
          continue
      else:
        f = files[frame.path]
      
      # Refine and add a new snippet_offset mapping
      file_off = await self._refine_method(f, frame.method)
      f.snippet_offsets.append(SnippetOffset(frame_id=idx, start=file_off.start, end=file_off.end))
      files[frame.path] = f
    
    # Abort if no files, won't be able to continue anyways
    if not files:
      return StopEvent(result="Unable to link stack trace to files in Github")
      
    return StopEvent(result={'frames':ev.frames, 'files':list(files.values())})
  
  async def _refine_method(self, file: ResolvedFile, method_name: str) -> FileOffset:
    """
    Returns the start and end line of the location of the method in the file.
    """
    sllm = self.llm.as_structured_llm(FileOffset)
    response = await sllm.acomplete(textwrap.dedent(f"""
      Please find the following method `{method_name}` in the provided {file.file_id.language} file. 
      You should return the start and end line number such that this contains the entire method definition and body, as well as any associated
      method documentation, annotations, or comments if they are present.
      Note that start line number should be inclusive, while end line number is exclusive.
      
      ```
      {file.content}
      ```"""))
    return response.raw


  def _resolve_file_in_github(self, language: str, repo: str, commit: str, path: str) -> ResolvedFile | None:
    """
    Attempts to resolve a file in github
    Note: Consciously trying to avoid calling get_git_tree(..., recursive=True) because this might be a huge result for very large repos.

    How to go from stack trace path to path in the repo in a good way? Options:
    1. Get the root dir contents, ask the LLM to pick next step each time... Could be a lot of LLM calls, how do you cache?
      - LLM calls are expensive, so want to avoid asking.. 
    2. Recursively get all the files or alternatively just the directories of the repo, give that to LLM and ask it to pick the path for each frame..
      - The repo might be huge, ie web-ui, probably like 50k files? 100k?.
    3. Use search_code endpoint with symbol: the last thing with some heuristics to try and get the class -> file

    Broadly two types of stack traces
    1. Include the file name + path in the stack, eg: python, JS/TS, ruby.
      - For these the complexity is that the path will have a prefix not in the repo. 
      => To match to repo we could basically list dirs in the root of the repo and find the matching prefix. Probably some edge cases but oh well.
    2. Include a class path and the file name, eg: JVM languages
      - class path kind of maps to the file path, but not exactly since you can have nested classes for instance
      - There is also and extra prefix in the repo, eg : proj/src/java/<... portion that matches the classpath more or less>
      => To match just statically add the prefix.
    """
    log.info(f"Searching for {path} in Github")
    r = gh_client.get_repo(repo)
    if language in {"java", "scala", "kotlin"}:
      # TODO: Need to remove $ and other stuff from (especially) kotlin, scala class paths?
      file_name = path.split('/')[-1]
      if 'Test' in file_name:
        candidate_path = f'src/test/{language}/' + path.lstrip('/')
      else:
        candidate_path = f'src/main/{language}/' + path.lstrip('/')
    else:
      # Look for the directories in the root dir of the repo
      t = r.get_git_tree(commit, recursive=False)
      # Include directories and files because maybe the file we are matching is in the root of the repo
      dirs = [item.path for item in t.tree]
      path_parts = path.split('/')
      i = len(path_parts) - 1
      while i >= 0:
        # Found the common suffix of the path with the repo
        if any((path_parts[i] == d for d in dirs)):
          break

        i -= 1
      
      candidate_path = '/'.join(path_parts[i:])
    
    # Now we have a canidate path, lets try fetching the file to ensure that it exists
    log.info(f'Checking if {candidate_path} is a valid file on Github', repo=repo, commit=commit)
    c = r.get_commit(commit)
    try:
      content = r.get_contents(candidate_path, ref=commit)
      if isinstance(content, list):
        content = content[0]
    except GithubException as ge:
      # TODO: Handle 404 and try a different candidate path
      log.error(f'Failed to get file {candidate_path}', ge)
      return None
    
    url = f'https://github.com/{repo}/blob/{c.sha}/{candidate_path}'
    return ResolvedFile(
      file_id=FileId(path=candidate_path, repo=repo, commit=commit, url=url, language=language),
      content=content.decoded_content.decode('utf-8'),
      snippet_offsets=[],
      )
    

