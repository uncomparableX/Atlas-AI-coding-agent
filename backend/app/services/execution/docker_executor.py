"""
Docker Sandbox Executor
Runs arbitrary commands inside isolated Docker containers.
Captures stdout/stderr, enforces timeouts and resource limits.
Supports Python, Node.js, Go, and generic shell execution.
"""
import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import docker
import docker.errors
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)

# ─── Language → Docker image mapping ─────────────────────────────────────────

LANGUAGE_IMAGES: Dict[str, str] = {
    "python":     "python:3.12-slim",
    "javascript": "node:20-slim",
    "typescript": "node:20-slim",
    "go":         "golang:1.22-alpine",
    "rust":       "rust:1.75-slim",
    "java":       "openjdk:21-slim",
    "ruby":       "ruby:3.3-slim",
    "php":        "php:8.3-cli",
    "default":    "ubuntu:22.04",
}

# ─── Execution Result ─────────────────────────────────────────────────────────

@dataclass
class ExecutionResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    container_id: Optional[str]
    status: str  # success | failed | timeout | error
    command: str
    timed_out: bool = False

    @property
    def success(self) -> bool:
        return self.exit_code == 0 and self.status == "success"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exit_code":    self.exit_code,
            "stdout":       self.stdout,
            "stderr":       self.stderr,
            "duration_ms":  self.duration_ms,
            "container_id": self.container_id,
            "status":       self.status,
            "command":      self.command,
            "timed_out":    self.timed_out,
            "success":      self.success,
        }


# ─── Docker Executor ─────────────────────────────────────────────────────────

class DockerExecutor:
    """
    Executes shell commands inside isolated Docker containers.
    Each execution gets a fresh container that is removed after completion.
    """

    def __init__(self):
        self._client: Optional[docker.DockerClient] = None
        self._init_client()

    def _init_client(self):
        try:
            self._client = docker.from_env()
            self._client.ping()
            logger.info("Docker client initialized successfully")
        except Exception as e:
            logger.error("Docker client initialization failed", error=str(e))
            self._client = None

    @property
    def available(self) -> bool:
        if not self._client:
            return False
        try:
            self._client.ping()
            return True
        except Exception:
            return False

    def _get_image(self, language: Optional[str]) -> str:
        if not language:
            return LANGUAGE_IMAGES["default"]
        return LANGUAGE_IMAGES.get(language.lower(), LANGUAGE_IMAGES["default"])

    def _ensure_image(self, image: str):
        """Pull image if not present locally."""
        try:
            self._client.images.get(image)
        except docker.errors.ImageNotFound:
            logger.info("Pulling Docker image", image=image)
            self._client.images.pull(image)
            logger.info("Docker image pulled", image=image)
        except Exception as e:
            logger.warning("Could not verify image", image=image, error=str(e))

    async def run(
        self,
        command: str,
        repo_path: str,
        task_id: str,
        language: Optional[str] = None,
        timeout: Optional[int] = None,
        environment: Optional[Dict[str, str]] = None,
        stream_callback: Optional[Callable[[str], None]] = None,
        working_dir: Optional[str] = None,
    ) -> ExecutionResult:
        """
        Execute a command in an isolated Docker container.

        Args:
            command:         Shell command to run.
            repo_path:       Host path to mount as /workspace in the container.
            task_id:         Task identifier for naming and logging.
            language:        Programming language (selects Docker image).
            timeout:         Max seconds before container is killed.
            environment:     Additional environment variables.
            stream_callback: Optional callback receiving each output line.
            working_dir:     Working directory inside container (default: /workspace).

        Returns:
            ExecutionResult with stdout, stderr, exit_code, duration, and status.
        """
        if not self._client:
            logger.error("Docker client not available")
            return ExecutionResult(
                exit_code=-1,
                stdout="",
                stderr="Docker daemon is not available. Cannot execute command.",
                duration_ms=0,
                container_id=None,
                status="error",
                command=command,
            )

        timeout    = timeout or settings.SANDBOX_TIMEOUT_SECONDS
        image      = self._get_image(language)
        work_dir   = working_dir or "/workspace"
        cname      = f"agentforge-{task_id[:8]}-{uuid.uuid4().hex[:6]}"
        start_time = time.time()

        logger.info(
            "Executing command in Docker sandbox",
            command=command[:120],
            image=image,
            task_id=task_id,
            container_name=cname,
        )

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self._run_sync(
                    command=command,
                    repo_path=repo_path,
                    image=image,
                    container_name=cname,
                    timeout=timeout,
                    environment=environment or {},
                    working_dir=work_dir,
                    stream_callback=stream_callback,
                ),
            )
            result.duration_ms = int((time.time() - start_time) * 1000)

            logger.info(
                "Docker execution complete",
                exit_code=result.exit_code,
                duration_ms=result.duration_ms,
                status=result.status,
                task_id=task_id,
            )
            return result

        except asyncio.TimeoutError:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.warning("Docker execution timed out", task_id=task_id, timeout=timeout)
            return ExecutionResult(
                exit_code=-1,
                stdout="",
                stderr=f"Execution timed out after {timeout} seconds.",
                duration_ms=duration_ms,
                container_id=None,
                status="timeout",
                command=command,
                timed_out=True,
            )

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error("Docker execution raised exception", error=str(e), task_id=task_id)
            return ExecutionResult(
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_ms=duration_ms,
                container_id=None,
                status="error",
                command=command,
            )

    def _run_sync(
        self,
        command: str,
        repo_path: str,
        image: str,
        container_name: str,
        timeout: int,
        environment: Dict[str, str],
        working_dir: str,
        stream_callback: Optional[Callable[[str], None]],
    ) -> ExecutionResult:
        """
        Synchronous Docker run — called via run_in_executor to avoid blocking the event loop.
        """
        container = None
        start_time = time.time()

        try:
            self._ensure_image(image)

            env = {
                "CI":              "true",
                "TERM":            "xterm-256color",
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONUNBUFFERED": "1",
                **environment,
            }

            container = self._client.containers.run(
                image=image,
                command=["/bin/sh", "-c", command],
                name=container_name,
                volumes={
                    repo_path: {"bind": "/workspace", "mode": "rw"},
                },
                working_dir=working_dir,
                environment=env,
                # Resource limits
                mem_limit=settings.SANDBOX_MEMORY_LIMIT,
                cpu_quota=settings.SANDBOX_CPU_QUOTA,
                cpu_period=100_000,
                # Security
                network_disabled=False,  # Some tests need network (pip install, npm install)
                read_only=False,         # Need write for test artefacts
                remove=False,            # We remove manually in finally
                detach=True,
                stdout=True,
                stderr=True,
            )

            stdout_lines: List[str] = []
            stderr_lines: List[str] = []

            # Stream combined output (docker merges by default in non-tty mode)
            try:
                for raw_line in container.logs(stream=True, follow=True, timestamps=False):
                    decoded = raw_line.decode("utf-8", errors="replace").rstrip("\n")
                    stdout_lines.append(decoded)
                    if stream_callback:
                        try:
                            stream_callback(decoded)
                        except Exception:
                            pass
            except Exception as stream_err:
                logger.warning("Log stream interrupted", error=str(stream_err))

            # Wait for container to finish with timeout
            try:
                wait_result = container.wait(timeout=timeout)
                exit_code   = wait_result.get("StatusCode", -1)
                timed_out   = False
            except Exception:
                try:
                    container.kill()
                except Exception:
                    pass
                exit_code = -1
                timed_out = True

            duration_ms = int((time.time() - start_time) * 1000)
            stdout_text = "\n".join(stdout_lines)
            status      = "success" if exit_code == 0 else ("timeout" if timed_out else "failed")

            return ExecutionResult(
                exit_code=exit_code,
                stdout=stdout_text,
                stderr="\n".join(stderr_lines),
                duration_ms=duration_ms,
                container_id=container.id[:12] if container else None,
                status=status,
                command=command,
                timed_out=timed_out,
            )

        except docker.errors.ContainerError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return ExecutionResult(
                exit_code=e.exit_status,
                stdout="",
                stderr=e.stderr.decode("utf-8", errors="replace") if e.stderr else str(e),
                duration_ms=duration_ms,
                container_id=None,
                status="failed",
                command=command,
            )

        except docker.errors.ImageNotFound as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return ExecutionResult(
                exit_code=-1,
                stdout="",
                stderr=f"Docker image not found: {e}",
                duration_ms=duration_ms,
                container_id=None,
                status="error",
                command=command,
            )

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return ExecutionResult(
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_ms=duration_ms,
                container_id=None,
                status="error",
                command=command,
            )

        finally:
            if container:
                try:
                    container.remove(force=True)
                    logger.debug("Container removed", container=container_name)
                except Exception as cleanup_err:
                    logger.warning(
                        "Failed to remove container",
                        container=container_name,
                        error=str(cleanup_err),
                    )

    async def cleanup_orphaned_containers(self, prefix: str = "agentforge-"):
        """Remove any leftover containers from previous runs."""
        if not self._client:
            return
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._cleanup_sync, prefix)
        except Exception as e:
            logger.warning("Orphan cleanup failed", error=str(e))

    def _cleanup_sync(self, prefix: str):
        containers = self._client.containers.list(
            all=True,
            filters={"name": prefix, "status": "exited"},
        )
        for c in containers:
            try:
                c.remove(force=True)
                logger.info("Removed orphaned container", container_id=c.id[:12])
            except Exception:
                pass


# ─── Mock Executor (development / testing without Docker) ─────────────────────

class MockDockerExecutor(DockerExecutor):
    """
    Fake executor used in development or CI environments without Docker.
    Returns successful mock output without actually running containers.
    """

    def _init_client(self):
        self._client = None

    @property
    def available(self) -> bool:
        return True

    async def run(
        self,
        command: str,
        repo_path: str,
        task_id: str,
        **kwargs,
    ) -> ExecutionResult:
        logger.info("MockDockerExecutor running command", command=command[:80])
        await asyncio.sleep(0.3)  # Simulate execution time

        mock_stdout = (
            f"[MOCK SANDBOX] $ {command}\n"
            "Collected 3 items\n"
            "test_example.py::test_one PASSED\n"
            "test_example.py::test_two PASSED\n"
            "test_example.py::test_three PASSED\n"
            "========== 3 passed in 0.42s ==========\n"
        )

        return ExecutionResult(
            exit_code=0,
            stdout=mock_stdout,
            stderr="",
            duration_ms=300,
            container_id="mock-container-abc123",
            status="success",
            command=command,
        )

    async def cleanup_orphaned_containers(self, prefix: str = "agentforge-"):
        pass
