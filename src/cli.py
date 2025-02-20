import argparse
import json
import os
import asyncio

from pydantic import BaseModel, ValidationError
from llama_index.core.workflow import StopEvent

from src import logging
from src.workflows.common_events import ProgressEvent
from src.workflows.stacktrace.events import ParsedStackFramesEvent
from src.workflows.stacktrace.flow import StacktraceAgentFlow
from src.model.sample import Sample
from src.workflows.stacktrace.model import ResolvedFile, StackFrame

logging.configure_logging()
log = logging.get_logger(__name__)

def main():
    parser = argparse.ArgumentParser(
        description='Bug Buster - A tool for solving bugs with AI'
    )
    
    parser.add_argument(
        'bug_file',
        type=argparse.FileType('r'),
        help='Path to the JSON file that will store bug data'
    )
    
    # parser.add_argument(
    #     'repo_path',
    #     type=str,
    #     help='Path to the local repository'
    # )
    
    args = parser.parse_args()
    
    # Validate repository path exists
    # if not os.path.exists(args.repo_path):
    #     log.error(f"Error: Repository path '{args.repo_path}' does not exist")
    #     return 1
    
    try:
        sample = Sample.model_validate(json.load(args.bug_file))
    except ValidationError:
        log.error('Invalid sample file')
        return 2
    except Exception as e:
        log.error(f'Failed to open file {args.bug_file}: {str(e)}')
        return 3
      
    return asyncio.run(run(sample))
  

async def run(sample: Sample):
    # Your main program logic here
    # log.info(f"Repository path: {repo_path}")
    log.info(f"Sample: {sample}")

    workflow = StacktraceAgentFlow(timeout=60, verbose=True)
    handler = workflow.run(sample=sample)
    async for ev in handler.stream_events():
        match ev:
            case ProgressEvent(message=msg):
                log.info(f"[Progress]: {msg}")
            case ParsedStackFramesEvent(frames=f):
                log.info(f'[Progress]: Done parsing stack frames, relevant frames: \n{"\n".join([str(ff) for ff in f])}')
            case StopEvent(result=r):
                files: list[ResolvedFile] = r['files']
                frames: list[StackFrame] = r['frames']
                log.info("[DONE] Relevant stack frames:")
                for i, frame in enumerate(frames):
                    log.info(f"Frame {frame}")
                    for fi in files:
                        for off in fi.snippet_offsets:
                            if off.frame_id == i:
                                log.info(f'{fi.file_id} L{off.start}-L{off.end}')
                                log.info('\n'.join(fi.lines[off.start -1:off.end-1]))

            
    # res = await workflow.run(sample=sample)
    # if isinstance(res, BaseModel):
    #     res = res.model_dump_json(indent=2)
    # if isinstance(res, dict):
    #     res = json.dumps(res, default=lambda o: o.model_dump() if isinstance(o, BaseModel) else o)
    # log.info(f'Final result: {res}')
    
    return 0


if __name__ == '__main__':
  exit(main())