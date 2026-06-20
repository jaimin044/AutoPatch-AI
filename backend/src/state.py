from typing import Annotated, TypedDict
import operator

class AgentState(TypedDict):
    job_id: str
    repo_url: str
    issue_text: str

    sandbox_id: str
    network_name: str
    repo_path: str

    repo_index: list[dict]
    retrieved_files: Annotated[list[str], operator.add]
    retrieved_context: str

    test_command: str
    target_file: str
    target_code: str
    baseline_error: str

    proposed_patch: str
    search_block: str
    replace_block: str
    replacement_file: str
    replacement_code: str

    validation_error: str
    validation_passed: bool

    attempt: int
    max_attempts: int
    status: str

    logs: Annotated[list[str], operator.add]
