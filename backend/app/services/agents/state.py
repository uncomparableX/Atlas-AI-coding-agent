"""
LangGraph Agent State Definitions
Typed state model shared across all agent nodes in the pipeline.
"""
from typing import Annotated, Any, Dict, List, Optional, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


# ─── Code Change Record ───────────────────────────────────────────────────────

class CodeChange(TypedDict):
    """Represents a single file change applied by the Coder agent."""
    file_path:    str
    action:       str          # modify | create | delete
    original:     str          # original file content
    modified:     str          # new file content
    diff:         str          # unified diff string
    explanation:  str          # why this change was made
    lines_added:  int
    lines_removed: int
    success:      bool         # whether the write to disk succeeded


# ─── Execution Result Record ──────────────────────────────────────────────────

class ExecutionRecord(TypedDict):
    """Result of one command executed inside the Docker sandbox."""
    command:      str
    exit_code:    int
    stdout:       str
    stderr:       str
    duration_ms:  int
    status:       str          # success | failed | timeout | error
    container_id: Optional[str]
    timed_out:    bool


# ─── Agent Run Record ─────────────────────────────────────────────────────────

class AgentRunRecord(TypedDict):
    """Summary of a single agent's invocation, written to the DB."""
    agent_type:  str
    iteration:   int
    tokens_used: int
    duration_ms: int
    status:      str           # running | done | failed
    thoughts:    Optional[str]
    actions:     Optional[List[Any]]


# ─── Review Result ────────────────────────────────────────────────────────────

class ReviewResult(TypedDict):
    """Output produced by the Reviewer agent."""
    approved:                 bool
    score:                    int
    summary:                  str
    issues:                   List[Dict[str, Any]]
    positives:                List[str]
    suggestions:              List[str]
    test_coverage_assessment: str
    security_assessment:      str


# ─── Final Task Result ────────────────────────────────────────────────────────

class TaskFinalResult(TypedDict):
    """Persisted to the Task.result JSON column on completion."""
    review:           ReviewResult
    code_changes:     List[CodeChange]
    execution_results:List[ExecutionRecord]
    files_modified:   List[str]
    total_tokens:     int
    retry_count:      int


# ─── Main Agent State ─────────────────────────────────────────────────────────

class AgentState(TypedDict):
    """
    Shared state object that flows through every node in the LangGraph pipeline.
    Annotated fields use add_messages to append rather than replace.
    """

    # ── Identity ──────────────────────────────────────────────────────────────
    task_id:         str
    repository_id:   str
    task_description:str
    repo_path:       str
    user_id:         Optional[str]

    # ── Conversation messages (append-only via LangGraph) ─────────────────────
    messages: Annotated[List[BaseMessage], add_messages]

    # ── Planning output ───────────────────────────────────────────────────────
    implementation_plan:  Optional[Dict[str, Any]]
    relevant_files:       List[str]
    architecture_context: str
    analysis:             Optional[Dict[str, Any]]   # from AnalystAgent

    # ── Code changes applied to disk ─────────────────────────────────────────
    code_changes: List[CodeChange]

    # ── Execution results from Docker sandbox ────────────────────────────────
    execution_results: List[ExecutionRecord]
    test_output:       Optional[str]
    build_output:      Optional[str]

    # ── Control flow ─────────────────────────────────────────────────────────
    current_agent:  str        # which node runs next
    iteration:      int        # how many nodes have run so far
    max_iterations: int

    # ── Retry tracking ────────────────────────────────────────────────────────
    retry_count:   int
    max_retries:   int
    error_context: Optional[str]   # enriched error message for coder retry
    should_retry:  bool
    error_history: List[str]       # all error contexts across retries

    # ── Debugger output ────────────────────────────────────────────────────────
    debug_diagnosis: Optional[Dict[str, Any]]

    # ── Final output ──────────────────────────────────────────────────────────
    final_result: Optional[TaskFinalResult]
    status:       str    # running | completed | failed

    # ── Token and cost tracking ───────────────────────────────────────────────
    total_tokens:       int
    planner_tokens:     int
    analyst_tokens:     int
    coder_tokens:       int
    executor_tokens:    int
    debugger_tokens:    int
    reviewer_tokens:    int

    # ── Streaming ─────────────────────────────────────────────────────────────
    event_publisher: Optional[Any]   # TaskEventPublisher callable


# ─── State factory ────────────────────────────────────────────────────────────

def make_initial_state(
    task_id: str,
    repository_id: str,
    task_description: str,
    repo_path: str,
    architecture_context: str = "",
    relevant_files: Optional[List[str]] = None,
    event_publisher: Optional[Any] = None,
    user_id: Optional[str] = None,
    max_iterations: int = 20,
    max_retries: int = 3,
) -> AgentState:
    """
    Construct the initial state for a new agent pipeline run.
    """
    from langchain_core.messages import HumanMessage

    return AgentState(
        task_id=task_id,
        repository_id=repository_id,
        task_description=task_description,
        repo_path=repo_path,
        user_id=user_id,
        messages=[HumanMessage(content=task_description)],
        implementation_plan=None,
        relevant_files=relevant_files or [],
        architecture_context=architecture_context,
        analysis=None,
        code_changes=[],
        execution_results=[],
        test_output=None,
        build_output=None,
        current_agent="planner",
        iteration=0,
        max_iterations=max_iterations,
        retry_count=0,
        max_retries=max_retries,
        error_context=None,
        should_retry=False,
        error_history=[],
        debug_diagnosis=None,
        final_result=None,
        status="running",
        total_tokens=0,
        planner_tokens=0,
        analyst_tokens=0,
        coder_tokens=0,
        executor_tokens=0,
        debugger_tokens=0,
        reviewer_tokens=0,
        event_publisher=event_publisher,
    )


# ─── State helpers ─────────────────────────────────────────────────────────────

def add_tokens(state: AgentState, agent: str, tokens: int) -> Dict[str, int]:
    """
    Return a dict of token field updates for a given agent.
    Used inside node return values.
    """
    field_map = {
        "planner":  "planner_tokens",
        "analyst":  "analyst_tokens",
        "coder":    "coder_tokens",
        "executor": "executor_tokens",
        "debugger": "debugger_tokens",
        "reviewer": "reviewer_tokens",
    }
    field = field_map.get(agent, "total_tokens")
    return {
        field:        state.get(field, 0) + tokens,
        "total_tokens": state.get("total_tokens", 0) + tokens,
    }


def is_terminal(state: AgentState) -> bool:
    """Return True if the pipeline should stop."""
    return state["status"] in ("completed", "failed")


def summarise_changes(state: AgentState) -> str:
    """Human-readable summary of all code changes applied so far."""
    changes = state.get("code_changes", [])
    if not changes:
        return "No files changed."
    lines = []
    for c in changes:
        sign = "+" if c["action"] == "create" else ("~" if c["action"] == "modify" else "-")
        lines.append(
            f"  {sign} {c['file_path']}  "
            f"(+{c.get('lines_added', 0)} -{c.get('lines_removed', 0)})"
        )
    return "\n".join(lines)
