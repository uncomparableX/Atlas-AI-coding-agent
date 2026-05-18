import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    JSON, Boolean, DateTime, ForeignKey, Index, Integer,
    String, Text, Float, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(255))
    github_token: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    repositories: Mapped[List["Repository"]] = relationship("Repository", back_populates="owner")
    tasks: Mapped[List["Task"]] = relationship("Task", back_populates="user")


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(512))
    github_url: Mapped[Optional[str]] = mapped_column(Text)
    local_path: Mapped[Optional[str]] = mapped_column(Text)
    default_branch: Mapped[str] = mapped_column(String(100), default="main")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    language: Mapped[Optional[str]] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(Text)
    architecture_summary: Mapped[Optional[str]] = mapped_column(Text)
    file_count: Mapped[int] = mapped_column(Integer, default=0)
    indexed_chunks: Mapped[int] = mapped_column(Integer, default=0)
    size_mb: Mapped[float] = mapped_column(Float, default=0.0)
    metadata_: Mapped[Optional[Dict[str, Any]]] = mapped_column("metadata", JSON)
    last_indexed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    owner: Mapped["User"] = relationship("User", back_populates="repositories")
    tasks: Mapped[List["Task"]] = relationship("Task", back_populates="repository")
    files: Mapped[List["RepositoryFile"]] = relationship("RepositoryFile", back_populates="repository", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_repo_owner_name", "owner_id", "name"),)


class RepositoryFile(Base):
    __tablename__ = "repository_files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    repository_id: Mapped[str] = mapped_column(String(36), ForeignKey("repositories.id"), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[Optional[str]] = mapped_column(String(50))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    line_count: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    ast_summary: Mapped[Optional[str]] = mapped_column(Text)
    last_modified: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    repository: Mapped["Repository"] = relationship("Repository", back_populates="files")

    __table_args__ = (Index("ix_repofile_repo_path", "repository_id", "path"),)


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    repository_id: Mapped[str] = mapped_column(String(36), ForeignKey("repositories.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="queued")
    plan: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    result: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    celery_task_id: Mapped[Optional[str]] = mapped_column(String(255))
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship("User", back_populates="tasks")
    repository: Mapped["Repository"] = relationship("Repository", back_populates="tasks")
    agent_runs: Mapped[List["AgentRun"]] = relationship("AgentRun", back_populates="task", cascade="all, delete-orphan")
    executions: Mapped[List["Execution"]] = relationship("Execution", back_populates="task", cascade="all, delete-orphan")
    diffs: Mapped[List["FileDiff"]] = relationship("FileDiff", back_populates="task", cascade="all, delete-orphan")
    messages: Mapped[List["ChatMessage"]] = relationship("ChatMessage", back_populates="task", cascade="all, delete-orphan")


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("tasks.id"), nullable=False)
    agent_type: Mapped[str] = mapped_column(String(30), nullable=False)
    iteration: Mapped[int] = mapped_column(Integer, default=0)
    input_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    output_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    thoughts: Mapped[Optional[str]] = mapped_column(Text)
    actions: Mapped[Optional[List[Any]]] = mapped_column(JSON)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(50), default="running")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    task: Mapped["Task"] = relationship("Task", back_populates="agent_runs")


class Execution(Base):
    __tablename__ = "executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("tasks.id"), nullable=False)
    command: Mapped[str] = mapped_column(Text, nullable=False)
    working_dir: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    exit_code: Mapped[Optional[int]] = mapped_column(Integer)
    stdout: Mapped[Optional[str]] = mapped_column(Text)
    stderr: Mapped[Optional[str]] = mapped_column(Text)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    container_id: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    task: Mapped["Task"] = relationship("Task", back_populates="executions")


class FileDiff(Base):
    __tablename__ = "file_diffs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("tasks.id"), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    original_content: Mapped[Optional[str]] = mapped_column(Text)
    modified_content: Mapped[Optional[str]] = mapped_column(Text)
    diff_unified: Mapped[Optional[str]] = mapped_column(Text)
    patch_applied: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    task: Mapped["Task"] = relationship("Task", back_populates="diffs")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    task_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("tasks.id"))
    repository_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("repositories.id"))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tokens: Mapped[int] = mapped_column(Integer, default=0)
    metadata_: Mapped[Optional[Dict[str, Any]]] = mapped_column("metadata", JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    task: Mapped[Optional["Task"]] = relationship("Task", back_populates="messages")


class AgentMemory(Base):
    __tablename__ = "agent_memories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    task_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("tasks.id"))
    repository_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("repositories.id"))
    memory_type: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_id: Mapped[Optional[str]] = mapped_column(String(255))
    importance: Mapped[float] = mapped_column(Float, default=0.5)
    access_count: Mapped[int] = mapped_column(Integer, default=0)
    metadata_: Mapped[Optional[Dict[str, Any]]] = mapped_column("metadata", JSON)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_accessed: Mapped[Optional[datetime]] = mapped_column(DateTime)
