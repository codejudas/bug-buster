import argparse
import json
import os
import asyncio

from pydantic import ValidationError

from src import logging
from src.workflows.stacktrace.flow import StacktraceAgentFlow
from src.model.sample import Sample

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
    res = await workflow.run(sample=sample)
    log.info(res)
    
    return 0


if __name__ == '__main__':
  exit(main())