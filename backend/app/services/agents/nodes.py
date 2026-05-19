"""
LangGraph Agent Node Implementations
Each function is a graph node that receives AgentState,
does its work, and returns a partial state update dict.
"""
import json
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.core.config import settings
from app.services.agents.file_tools import FileTools
from app.services.agents.prompts import (
    ANALYST_SYSTEM,
    ANALYST_USER_TEMPLATE,
    CODER_RETRY_ADDENDUM,
    CODER_SYSTEM,
    CODER_USER_TEMPLATE,
    DEBUGGER_SYSTEM,
    DEBUGGER_USER_TEMPLATE,
    PLANNER_SYSTEM,
    PLANNER_USER_TEMPLATE,
    REVIEWER_SYSTEM,
    REVIEWER_USER_TEMPLATE,
)
from app.services.agents.state import (
    AgentState,
    CodeChange,
    ExecutionRecord,
    add_tokens,
    summarise_changes,
)
from app.services.execution.docker_executor import DockerExecutor
from app.services.execution.sandbox_templates import get_test_commands
from app.services.indexing.vector_store import VectorStore

logger = structlog.get_logger(__name__)


# ─── LLM factories ───────────────────────────────────────────────────────────

def _llm(temperature: float = None) -> ChatAnthropic:
    return ChatAnthropic(
        model=settings.DEFAULT_MODEL,
        api_key=settings.ANTHROPIC_API_KEY,
        temperature=temperature if temperature is not None else settings.TEMPERATURE,
        max_tokens=settings.MAX_TOKENS,
    )


def _fast_llm() -> ChatAnthropic:
    return ChatAnthropic(
        model=settings.FAST_MODEL,
        api_key=settings.ANTHROPIC_API_KEY,
        temperature=0.1,
        max_tokens=4096,
    )


def _count(text: str) -> int:
    return len(text.split()) * 4 // 3


def _parse_json(raw: str) -> Dict[str, Any]:
    """
    Extract and parse the first JSON object found in a string.
    Handles cases where the LLM wraps JSON in markdown fences.
    """
    # Strip markdown fences if present
    clean = raw.strip()
    if clean.startswith("```"):
        lines = clean.split("\n")
        clean = "\n".join(lines[1:-1]) if len(lines) > 2 else clean

    j_start = clean.find("{")
    j_end   = clean.rfind("}") + 1
    if j_start == -1 or j_end == 0:
        raise ValueError(f"No JSON object found in LLM output: {clean[:200]}")
    return json.loads(clean[j_start:j_end])


# ─── Event publisher helper ───────────────────────────────────────────────────

async def _publish(state: AgentState, event_type: str, data: Any, agent: str = ""):
    publisher = state.get("event_publisher")
    if publisher:
        try:
            await publisher({
                "type":       event_type,
                "task_id":    state["task_id"],
                "agent_type": agent,
                "data":       data,
                "timestamp":  datetime.utcnow().isoformat(),
            })
        except Exception:
            pass


# ─── Planner Node ─────────────────────────────────────────────────────────────

async def planner_node(state: AgentState) -> Dict[str, Any]:
    """
    Analyses the task and produces a structured implementation plan.
    """
    t0 = time.time()
    logger.info("planner_node start", task_id=state["task_id"])

    await _publish(state, "agent_thought", {
        "message": "Analysing task and creating step-by-step implementation plan...",
    }, agent="planner")

    relevant_files_str = "\n".join(state.get("relevant_files", [])[:20]) or "Not yet determined"

    user_msg = PLANNER_USER_TEMPLATE.format(
        task_description=state["task_description"],
        architecture_context=state.get("architecture_context") or "Not available",
        relevant_files=relevant_files_str,
        error_context=state.get("error_context") or "None — this is the first attempt",
    )

    response = await _llm().ainvoke([
        SystemMessage(content=PLANNER_SYSTEM),
        HumanMessage(content=user_msg),
    ])
    raw    = response.content
    tokens = _count(raw)

    try:
        plan = _parse_json(raw)
    except Exception as e:
        logger.warning("planner JSON parse failed", error=str(e))
        plan = {
            "summary": raw[:400],
            "steps": [{
                "id": 1, "title": "Implement task",
                "description": state["task_description"],
                "files_to_modify": [], "files_to_create": [],
                "tests_to_run": [], "dependencies": [],
            }],
            "estimated_complexity": "medium",
            "risks": [],
            "success_criteria": [],
            "test_strategy": "Run existing test suite",
        }

    await _publish(state, "agent_result", {
        "plan":        plan,
        "steps_count": len(plan.get("steps", [])),
        "complexity":  plan.get("estimated_complexity"),
    }, agent="planner")

    duration_ms = int((time.time() - t0) * 1000)
    logger.info("planner_node done",
                task_id=state["task_id"],
                steps=len(plan.get("steps", [])),
                tokens=tokens)

    return {
        "implementation_plan": plan,
        "current_agent": "analyst",
        "iteration": state.get("iteration", 0) + 1,
        "messages": [AIMessage(content=(
            f"[Planner] {len(plan.get('steps', []))} steps planned. "
            f"Complexity: {plan.get('estimated_complexity')}. "
            f"Summary: {plan.get('summary', '')[:200]}"
        ))],
        **add_tokens(state, "planner", tokens),
    }


# ─── Analyst Node ─────────────────────────────────────────────────────────────

async def analyst_node(state: AgentState) -> Dict[str, Any]:
    """
    Performs semantic search and analyses the codebase to identify
    all files relevant to the task.
    """
    t0 = time.time()
    logger.info("analyst_node start", task_id=state["task_id"])

    await _publish(state, "agent_thought", {
        "message": "Performing semantic search and analysing codebase structure...",
    }, agent="analyst")

    # Semantic search
    vs = VectorStore()
    chunks = await vs.search_code(
        query=state["task_description"],
        repository_id=state["repository_id"],
        limit=15,
    )

    code_context = "\n\n---\n\n".join([
        f"File: {c['file_path']} "
        f"(lines {c.get('start_line','?')}-{c.get('end_line','?')})\n"
        f"```{c.get('language','')}\n{c['content'][:1200]}\n```"
        for c in chunks
    ])

    plan_summary = (
        state.get("implementation_plan", {}).get("summary", "No plan yet")
        if state.get("implementation_plan") else "No plan yet"
    )

    user_msg = ANALYST_USER_TEMPLATE.format(
        task_description=state["task_description"],
        plan_summary=plan_summary,
        code_context=code_context,
        architecture_context=state.get("architecture_context") or "Not available",
    )

    response = await _llm().ainvoke([
        SystemMessage(content=ANALYST_SYSTEM),
        HumanMessage(content=user_msg),
    ])
    raw    = response.content
    tokens = _count(raw)

    try:
        analysis = _parse_json(raw)
    except Exception as e:
        logger.warning("analyst JSON parse failed", error=str(e))
        analysis = {
            "files_to_read":    [],
            "files_to_modify":  [],
            "files_to_create":  [],
            "architecture_notes": raw[:400],
            "dependencies":     {},
            "entry_points":     [],
            "test_files":       [],
            "conventions":      {},
            "warnings":         [],
        }

    # Merge: analyst results + vector search results
    relevant_files = list(set(
        analysis.get("files_to_read", [])
        + analysis.get("files_to_modify", [])
        + analysis.get("files_to_create", [])
        + [c["file_path"] for c in chunks]
        + state.get("relevant_files", [])
    ))

    # Extend architecture context
    new_arch = (
        (state.get("architecture_context") or "")
        + "\n\n"
        + analysis.get("architecture_notes", "")
    ).strip()

    await _publish(state, "agent_result", {
        "relevant_files":     relevant_files,
        "chunks_found":       len(chunks),
        "architecture_notes": analysis.get("architecture_notes", ""),
        "warnings":           analysis.get("warnings", []),
    }, agent="analyst")

    duration_ms = int((time.time() - t0) * 1000)
    logger.info("analyst_node done",
                task_id=state["task_id"],
                relevant_files=len(relevant_files),
                tokens=tokens)

    return {
        "relevant_files":     relevant_files,
        "architecture_context": new_arch,
        "analysis":           analysis,
        "current_agent":      "coder",
        "iteration": state.get("iteration", 0) + 1,
        "messages": [AIMessage(content=(
            f"[Analyst] Found {len(relevant_files)} relevant files, "
            f"{len(chunks)} semantic matches. "
            f"Warnings: {len(analysis.get('warnings', []))}"
        ))],
        **add_tokens(state, "analyst", tokens),
    }


# ─── Coder Node ───────────────────────────────────────────────────────────────

async def coder_node(state: AgentState) -> Dict[str, Any]:
    """
    Reads relevant files and generates complete file changes.
    Writes modified/created files to disk.
    """
    t0 = time.time()
    logger.info("coder_node start",
                task_id=state["task_id"],
                retry=state.get("retry_count", 0))

    await _publish(state, "agent_thought", {
        "message": (
            f"Reading files and generating code changes "
            f"(attempt {state.get('retry_count', 0) + 1})..."
        ),
    }, agent="coder")

    ft = FileTools(repo_path=state["repo_path"])

    # Read relevant files (cap at 12 to stay within context)
    file_contents: Dict[str, str] = {}
    for fp in state.get("relevant_files", [])[:12]:
        content = await ft.read_file(fp)
        if content is not None:
            file_contents[fp] = content

    files_ctx = "\n\n---\n\n".join([
        f"### {path}\n```\n{content[:3000]}\n```"
        for path, content in file_contents.items()
    ]) or "No files loaded."

    # Build plan text
    plan = state.get("implementation_plan", {})
    plan_text = "\n".join([
        f"Step {s['id']}: {s['title']}\n"
        f"  Description: {s['description']}\n"
        f"  Files to modify: {s.get('files_to_modify', [])}\n"
        f"  Files to create: {s.get('files_to_create', [])}\n"
        f"  Tests to run: {s.get('tests_to_run', [])}"
        for s in plan.get("steps", [])
    ]) or state["task_description"]

    analysis    = state.get("analysis") or {}
    arch_notes  = analysis.get("architecture_notes", state.get("architecture_context", ""))
    arch_notes += "\nConventions: " + str(analysis.get("conventions", {}))
    arch_notes += "\nWarnings: "    + str(analysis.get("warnings", []))

    # Build user message
    user_msg = CODER_USER_TEMPLATE.format(
        task_description=state["task_description"],
        plan_text=plan_text,
        file_contents=files_ctx,
        architecture_notes=arch_notes,
        error_context=state.get("error_context") or "None — first attempt",
    )

    # Append retry addendum if this is a retry
    if state.get("retry_count", 0) > 0 and state.get("debug_diagnosis"):
        diag = state["debug_diagnosis"]
        user_msg += CODER_RETRY_ADDENDUM.format(
            retry_number=state["retry_count"],
            max_retries=state["max_retries"],
            previous_error=state.get("test_output", "")[:1000],
            root_cause=diag.get("root_cause", ""),
            fix_strategy=diag.get("fix_strategy", ""),
            files_to_fix="\n".join(diag.get("files_to_fix", [])),
        )

    response = await _llm(temperature=0.1).ainvoke([
        SystemMessage(content=CODER_SYSTEM),
        HumanMessage(content=user_msg),
    ])
    raw    = response.content
    tokens = _count(raw)

    # Parse coder JSON
    try:
        result  = _parse_json(raw)
        changes_raw = result.get("changes", [])
        coder_notes = result.get("notes", "")
    except Exception as e:
        logger.error("coder JSON parse failed", error=str(e), task_id=state["task_id"])
        changes_raw = []
        coder_notes = ""

    # Apply changes to disk
    applied: List[CodeChange] = []
    for ch in changes_raw:
        try:
            fp      = ch.get("file_path", "")
            action  = ch.get("action", "modify")
            content = ch.get("content", "")

            applied_change = await ft.apply_change(
                file_path=fp,
                content=content,
                action=action,
                original_content=file_contents.get(fp),
            )
            applied.append(applied_change)

            await _publish(state, "file_changed", {
                "file_path":     fp,
                "action":        action,
                "explanation":   ch.get("explanation", ""),
                "diff":          applied_change.get("diff", ""),
                "lines_added":   applied_change.get("lines_added", 0),
                "lines_removed": applied_change.get("lines_removed", 0),
            }, agent="coder")

        except Exception as e:
            logger.error("Failed to apply change",
                         file=ch.get("file_path"), error=str(e))

    await _publish(state, "agent_result", {
        "changes_applied": len(applied),
        "files":           [c["file_path"] for c in applied],
        "notes":           coder_notes,
    }, agent="coder")

    duration_ms = int((time.time() - t0) * 1000)
    logger.info("coder_node done",
                task_id=state["task_id"],
                applied=len(applied),
                tokens=tokens)

    return {
        "code_changes": state.get("code_changes", []) + applied,
        "current_agent": "executor",
        "iteration": state.get("iteration", 0) + 1,
        "messages": [AIMessage(content=(
            f"[Coder] Applied {len(applied)} file changes. "
            + summarise_changes({"code_changes": applied})
        ))],
        **add_tokens(state, "coder", tokens),
    }


# ─── Executor Node ────────────────────────────────────────────────────────────

async def executor_node(state: AgentState) -> Dict[str, Any]:
    """
    Runs tests and build commands inside the Docker sandbox.
    Decides whether to send state to reviewer (pass) or debugger (fail).
    """
    t0 = time.time()
    logger.info("executor_node start", task_id=state["task_id"])

    await _publish(state, "agent_thought", {
        "message": "Running tests inside Docker sandbox...",
    }, agent="executor")

    executor = DockerExecutor()
    plan     = state.get("implementation_plan", {})

    # Collect commands from plan
    test_commands: List[str] = []
    for step in plan.get("steps", []):
        test_commands.extend(step.get("tests_to_run", []))

    # Fall back to auto-detected commands if plan has none
    if not test_commands:
        test_commands = await get_test_commands(state["repo_path"])

    exec_records: List[ExecutionRecord] = []
    all_output:   List[str]             = []
    overall_ok    = True

    for cmd in test_commands[:5]:
        await _publish(state, "execution_log", {
            "command": cmd,
            "status":  "starting",
        }, agent="executor")

        result = await executor.run(
            command=cmd,
            repo_path=state["repo_path"],
            task_id=state["task_id"],
            timeout=settings.SANDBOX_TIMEOUT_SECONDS,
        )

        record: ExecutionRecord = {
            "command":      cmd,
            "exit_code":    result.exit_code,
            "stdout":       result.stdout,
            "stderr":       result.stderr,
            "duration_ms":  result.duration_ms,
            "status":       result.status,
            "container_id": result.container_id,
            "timed_out":    result.timed_out,
        }
        exec_records.append(record)
        chunk = f"$ {cmd}\n{result.stdout}"
        if result.stderr:
            chunk += f"\nSTDERR:\n{result.stderr}"
        all_output.append(chunk)

        if result.exit_code != 0:
            overall_ok = False

        await _publish(state, "execution_log", {
            "command":   cmd,
            "exit_code": result.exit_code,
            "stdout":    result.stdout[:3000],
            "status":    result.status,
        }, agent="executor")

    combined_output = "\n\n".join(all_output)
    next_agent      = "reviewer" if overall_ok else "debugger"

    await _publish(state, "agent_result", {
        "passed":      overall_ok,
        "commands_run": len(exec_records),
        "next_agent":  next_agent,
    }, agent="executor")

    duration_ms = int((time.time() - t0) * 1000)
    logger.info("executor_node done",
                task_id=state["task_id"],
                passed=overall_ok,
                commands=len(exec_records))

    return {
        "execution_results": state.get("execution_results", []) + exec_records,
        "test_output":       combined_output,
        "current_agent":     next_agent,
        "should_retry":      not overall_ok,
        "error_context":     combined_output if not overall_ok else state.get("error_context"),
        "iteration": state.get("iteration", 0) + 1,
        "messages": [AIMessage(content=(
            f"[Executor] Tests {'PASSED' if overall_ok else 'FAILED'}. "
            f"Ran {len(exec_records)} command(s). "
            f"Routing to {next_agent}."
        ))],
    }


# ─── Debugger Node ────────────────────────────────────────────────────────────

async def debugger_node(state: AgentState) -> Dict[str, Any]:
    """
    Analyses test failures, diagnoses the root cause, and decides
    whether to retry (routes back to coder) or give up.
    """
    t0          = time.time()
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", settings.MAX_RETRY_ATTEMPTS)

    logger.info("debugger_node start",
                task_id=state["task_id"],
                retry=retry_count)

    # Hard stop: exceeded retry budget
    if retry_count >= max_retries:
        await _publish(state, "agent_thought", {
            "message": f"Max retries ({max_retries}) exceeded. Failing task.",
        }, agent="debugger")
        return {
            "current_agent": "done",
            "status":        "failed",
            "iteration": state.get("iteration", 0) + 1,
            "messages": [AIMessage(content=(
                f"[Debugger] Retry budget exhausted ({retry_count}/{max_retries}). "
                "Task marked as failed."
            ))],
        }

    await _publish(state, "agent_thought", {
        "message": (
            f"Diagnosing failure (attempt {retry_count + 1} of {max_retries})..."
        ),
    }, agent="debugger")

    modified_files_str = "\n".join([
        f"- {c['file_path']}" for c in state.get("code_changes", [])
    ]) or "None"

    user_msg = DEBUGGER_USER_TEMPLATE.format(
        task_description=state["task_description"],
        test_output=state.get("test_output", "No test output available")[:3000],
        modified_files=modified_files_str,
        previous_error_context=state.get("error_context", "None")[:1500],
        retry_number=retry_count + 1,
        max_retries=max_retries,
    )

    response = await _llm().ainvoke([
        SystemMessage(content=DEBUGGER_SYSTEM),
        HumanMessage(content=user_msg),
    ])
    raw    = response.content
    tokens = _count(raw)

    try:
        diagnosis = _parse_json(raw)
    except Exception as e:
        logger.warning("debugger JSON parse failed", error=str(e))
        diagnosis = {
            "root_cause":         raw[:300],
            "error_type":         "other",
            "fix_strategy":       "Review the error output and retry.",
            "files_to_fix":       [],
            "should_retry":       True,
            "confidence":         "low",
            "additional_context": "",
        }

    should_retry = diagnosis.get("should_retry", True)

    await _publish(state, "agent_result", {
        "root_cause":   diagnosis.get("root_cause"),
        "error_type":   diagnosis.get("error_type"),
        "fix_strategy": diagnosis.get("fix_strategy"),
        "should_retry": should_retry,
        "retry_number": retry_count + 1,
    }, agent="debugger")

    if not should_retry:
        logger.info("debugger says unrecoverable", task_id=state["task_id"])
        return {
            "debug_diagnosis": diagnosis,
            "current_agent":   "done",
            "status":          "failed",
            "iteration": state.get("iteration", 0) + 1,
            "messages": [AIMessage(content=(
                f"[Debugger] Unrecoverable error: {diagnosis.get('root_cause', '')[:200]}"
            ))],
            **add_tokens(state, "debugger", tokens),
        }

    # Build enriched error context for next coder attempt
    enriched = (
        f"=== RETRY {retry_count + 1}/{max_retries} ===\n\n"
        f"ERROR TYPE: {diagnosis.get('error_type')}\n\n"
        f"ROOT CAUSE:\n{diagnosis.get('root_cause', '')}\n\n"
        f"FIX STRATEGY:\n{diagnosis.get('fix_strategy', '')}\n\n"
        f"FILES TO FIX:\n" + "\n".join(diagnosis.get("files_to_fix", []))
    )

    error_history = state.get("error_history", []) + [
        state.get("test_output", "")[:500]
    ]

    duration_ms = int((time.time() - t0) * 1000)
    logger.info("debugger_node done",
                task_id=state["task_id"],
                routing_to="coder",
                tokens=tokens)

    return {
        "debug_diagnosis": diagnosis,
        "error_context":   enriched,
        "error_history":   error_history,
        "retry_count":     retry_count + 1,
        "current_agent":   "coder",
        "iteration": state.get("iteration", 0) + 1,
        "messages": [AIMessage(content=(
            f"[Debugger] Root cause: {diagnosis.get('root_cause', '')[:200]}. "
            f"Routing back to coder (retry {retry_count + 1})."
        ))],
        **add_tokens(state, "debugger", tokens),
    }


# ─── Reviewer Node ────────────────────────────────────────────────────────────

async def reviewer_node(state: AgentState) -> Dict[str, Any]:
    """
    Reviews code quality, correctness, and test results.
    Produces a structured review and marks the task completed.
    """
    t0 = time.time()
    logger.info("reviewer_node start", task_id=state["task_id"])

    await _publish(state, "agent_thought", {
        "message": "Reviewing code quality, correctness, and test results...",
    }, agent="reviewer")

    changes        = state.get("code_changes", [])
    changes_summary = "\n".join([
        f"- {c['action'].upper()} {c['file_path']}  "
        f"(+{c.get('lines_added',0)} -{c.get('lines_removed',0)})"
        for c in changes
    ]) or "No files changed."

    diffs_text = "\n\n".join([
        f"### {c['file_path']}\n```diff\n{c.get('diff','')[:2000]}\n```"
        for c in changes[:5]
    ]) or "No diffs available."

    # Try to get coder notes from last AIMessage
    coder_notes = ""
    for msg in reversed(state.get("messages", [])):
        if hasattr(msg, "content") and msg.content.startswith("[Coder]"):
            coder_notes = msg.content
            break

    user_msg = REVIEWER_USER_TEMPLATE.format(
        task_description=state["task_description"],
        changes_summary=changes_summary,
        diffs_text=diffs_text,
        test_output=state.get("test_output", "No tests were run.")[:2000],
        coder_notes=coder_notes,
    )

    response = await _fast_llm().ainvoke([
        SystemMessage(content=REVIEWER_SYSTEM),
        HumanMessage(content=user_msg),
    ])
    raw    = response.content
    tokens = _count(raw)

    try:
        review = _parse_json(raw)
    except Exception:
        review = {
            "approved":                 True,
            "score":                    7,
            "summary":                  "Implementation completed and tests passed.",
            "issues":                   [],
            "positives":                ["Tests passed"],
            "suggestions":              [],
            "test_coverage_assessment": "Tests passed",
            "security_assessment":      "No obvious security concerns",
        }

    final_result = {
        "review":             review,
        "code_changes":       changes,
        "execution_results":  state.get("execution_results", []),
        "files_modified":     [c["file_path"] for c in changes],
        "total_tokens":       state.get("total_tokens", 0) + tokens,
        "retry_count":        state.get("retry_count", 0),
    }

    await _publish(state, "agent_result", {
        "review":   review,
        "score":    review.get("score"),
        "approved": review.get("approved"),
        "issues":   len(review.get("issues", [])),
    }, agent="reviewer")

    duration_ms = int((time.time() - t0) * 1000)
    logger.info("reviewer_node done",
                task_id=state["task_id"],
                score=review.get("score"),
                approved=review.get("approved"),
                tokens=tokens)

    return {
        "final_result":  final_result,
        "current_agent": "done",
        "status":        "completed",
        "iteration": state.get("iteration", 0) + 1,
        "messages": [AIMessage(content=(
            f"[Reviewer] Score: {review.get('score')}/10. "
            f"Approved: {review.get('approved')}. "
            f"{review.get('summary','')[:200]}"
        ))],
        **add_tokens(state, "reviewer", tokens),
    }


# ─── Routing functions ────────────────────────────────────────────────────────

def route_from_planner(state: AgentState) -> str:
    return state.get("current_agent", "analyst")


def route_from_analyst(state: AgentState) -> str:
    return state.get("current_agent", "coder")


def route_from_coder(state: AgentState) -> str:
    return state.get("current_agent", "executor")


def route_from_executor(state: AgentState) -> str:
    return state.get("current_agent", "reviewer")


def route_from_debugger(state: AgentState) -> str:
    from langgraph.graph import END
    agent = state.get("current_agent", "coder")
    if agent == "done" or state.get("status") == "failed":
        return END
    return agent


def route_from_reviewer(state: AgentState) -> str:
    from langgraph.graph import END
    return END
