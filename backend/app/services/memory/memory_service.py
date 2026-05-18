"""
Agent Memory Service
Stores episodic and semantic memories in both PostgreSQL (metadata)
and Qdrant (vector search), with importance scoring and expiration.
"""
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)


class MemoryService:
    """
    Manages agent memories across tasks and repositories.

    Memory types:
      - episodic  : specific events that happened during a task
      - semantic  : general knowledge extracted from codebase
      - working   : short-lived context for the current task iteration
    """

    # ── Store ─────────────────────────────────────────────────────────────────

    async def store_memory(
        self,
        content: str,
        memory_type: str,
        task_id: Optional[str] = None,
        repository_id: Optional[str] = None,
        importance: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None,
        ttl_hours: Optional[int] = None,
    ) -> str:
        """
        Persist a memory in PostgreSQL and index it in Qdrant.

        Args:
            content:       The memory text.
            memory_type:   "episodic" | "semantic" | "working".
            task_id:       Related task (optional).
            repository_id: Related repository (optional).
            importance:    0.0 – 1.0 score; higher = retrieved first.
            metadata:      Extra arbitrary key-value pairs.
            ttl_hours:     Auto-expire after N hours (None = no expiry).

        Returns:
            The new memory UUID.
        """
        from app.core.database import AsyncSessionLocal
        from app.models.models import AgentMemory
        from app.services.indexing.vector_store import VectorStore

        memory_id  = str(uuid.uuid4())
        expires_at = (
            datetime.utcnow() + timedelta(hours=ttl_hours)
            if ttl_hours
            else None
        )

        async with AsyncSessionLocal() as db:
            mem = AgentMemory(
                id=memory_id,
                task_id=task_id,
                repository_id=repository_id,
                memory_type=memory_type,
                content=content,
                importance=max(0.0, min(1.0, importance)),
                metadata_=metadata or {},
                expires_at=expires_at,
            )
            db.add(mem)
            await db.commit()
            logger.debug(
                "Memory stored in DB",
                memory_id=memory_id,
                memory_type=memory_type,
            )

        try:
            vs = VectorStore()
            await vs.upsert_memory(
                memory_id=memory_id,
                content=content,
                metadata={
                    "task_id":       task_id,
                    "repository_id": repository_id,
                    "memory_type":   memory_type,
                    "importance":    importance,
                    **(metadata or {}),
                },
            )
        except Exception as e:
            logger.warning(
                "Failed to embed memory in Qdrant",
                memory_id=memory_id,
                error=str(e),
            )

        return memory_id

    # ── Retrieve by semantic similarity ───────────────────────────────────────

    async def retrieve_relevant(
        self,
        query: str,
        repository_id: Optional[str] = None,
        task_id: Optional[str] = None,
        memory_type: Optional[str] = None,
        limit: int = 5,
        min_importance: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        Semantic search over stored memories.
        Returns the most relevant memories sorted by vector similarity.
        """
        from app.services.indexing.vector_store import VectorStore

        vs      = VectorStore()
        filters: Dict[str, Any] = {}

        if repository_id:
            filters["repository_id"] = repository_id
        if task_id:
            filters["task_id"] = task_id
        if memory_type:
            filters["memory_type"] = memory_type

        results = await vs.search_memory(
            query=query,
            filters=filters,
            limit=limit,
        )

        # Filter by importance if requested
        if min_importance > 0.0:
            results = [
                r for r in results
                if r.get("importance", 0.0) >= min_importance
            ]

        # Bump access count
        if results:
            await self._bump_access_counts([r.get("id") for r in results if r.get("id")])

        return results

    # ── Retrieve by recency (DB) ───────────────────────────────────────────────

    async def retrieve_recent(
        self,
        repository_id: Optional[str] = None,
        task_id: Optional[str] = None,
        memory_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Retrieve the most recently created memories from PostgreSQL."""
        from app.core.database import AsyncSessionLocal
        from app.models.models import AgentMemory
        from sqlalchemy import select

        async with AsyncSessionLocal() as db:
            q = select(AgentMemory).where(
                AgentMemory.expires_at.is_(None)
                | (AgentMemory.expires_at > datetime.utcnow())
            )

            if repository_id:
                q = q.where(AgentMemory.repository_id == repository_id)
            if task_id:
                q = q.where(AgentMemory.task_id == task_id)
            if memory_type:
                q = q.where(AgentMemory.memory_type == memory_type)

            q = q.order_by(AgentMemory.created_at.desc()).limit(limit)

            result = await db.execute(q)
            memories = result.scalars().all()

            return [
                {
                    "id":            m.id,
                    "content":       m.content,
                    "memory_type":   m.memory_type,
                    "importance":    m.importance,
                    "access_count":  m.access_count,
                    "created_at":    m.created_at.isoformat(),
                    "task_id":       m.task_id,
                    "repository_id": m.repository_id,
                }
                for m in memories
            ]

    # ── Retrieve by importance ────────────────────────────────────────────────

    async def retrieve_important(
        self,
        repository_id: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Retrieve the highest-importance memories for a repository."""
        from app.core.database import AsyncSessionLocal
        from app.models.models import AgentMemory
        from sqlalchemy import select

        async with AsyncSessionLocal() as db:
            q = (
                select(AgentMemory)
                .where(
                    AgentMemory.repository_id == repository_id,
                    AgentMemory.expires_at.is_(None)
                    | (AgentMemory.expires_at > datetime.utcnow()),
                )
                .order_by(AgentMemory.importance.desc())
                .limit(limit)
            )
            result   = await db.execute(q)
            memories = result.scalars().all()

            return [
                {
                    "id":          m.id,
                    "content":     m.content,
                    "memory_type": m.memory_type,
                    "importance":  m.importance,
                    "created_at":  m.created_at.isoformat(),
                }
                for m in memories
            ]

    # ── Update importance ─────────────────────────────────────────────────────

    async def update_importance(self, memory_id: str, importance: float):
        """Adjust the importance score of an existing memory."""
        from app.core.database import AsyncSessionLocal
        from app.models.models import AgentMemory
        from sqlalchemy import update

        async with AsyncSessionLocal() as db:
            await db.execute(
                update(AgentMemory)
                .where(AgentMemory.id == memory_id)
                .values(importance=max(0.0, min(1.0, importance)))
            )
            await db.commit()

    # ── Delete ────────────────────────────────────────────────────────────────

    async def delete_memory(self, memory_id: str):
        """Delete a memory from both DB and Qdrant."""
        from app.core.database import AsyncSessionLocal
        from app.models.models import AgentMemory
        from app.services.indexing.vector_store import VectorStore
        from sqlalchemy import delete

        async with AsyncSessionLocal() as db:
            await db.execute(
                delete(AgentMemory).where(AgentMemory.id == memory_id)
            )
            await db.commit()

        try:
            vs = VectorStore()
            await vs.delete_memory(memory_id)
        except Exception as e:
            logger.warning("Failed to delete memory vector", id=memory_id, error=str(e))

    async def delete_task_memories(self, task_id: str):
        """Remove all working memories for a completed task."""
        from app.core.database import AsyncSessionLocal
        from app.models.models import AgentMemory
        from sqlalchemy import delete

        async with AsyncSessionLocal() as db:
            await db.execute(
                delete(AgentMemory).where(AgentMemory.task_id == task_id)
            )
            await db.commit()

    async def delete_expired(self):
        """Purge all expired memories. Called by periodic Celery beat task."""
        from app.core.database import AsyncSessionLocal
        from app.models.models import AgentMemory
        from sqlalchemy import delete, select

        async with AsyncSessionLocal() as db:
            # Collect IDs first so we can remove from Qdrant
            expired_q = select(AgentMemory.id).where(
                AgentMemory.expires_at < datetime.utcnow()
            )
            result      = await db.execute(expired_q)
            expired_ids = [row[0] for row in result.fetchall()]

            if not expired_ids:
                return

            await db.execute(
                delete(AgentMemory).where(AgentMemory.id.in_(expired_ids))
            )
            await db.commit()
            logger.info("Expired memories purged", count=len(expired_ids))

        # Remove from Qdrant
        try:
            vs = VectorStore()
            for mid in expired_ids:
                await vs.delete_memory(mid)
        except Exception as e:
            logger.warning("Failed to purge expired memory vectors", error=str(e))

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _bump_access_counts(self, memory_ids: List[str]):
        """Increment access_count for retrieved memories."""
        if not memory_ids:
            return
        from app.core.database import AsyncSessionLocal
        from app.models.models import AgentMemory
        from sqlalchemy import update

        async with AsyncSessionLocal() as db:
            await db.execute(
                update(AgentMemory)
                .where(AgentMemory.id.in_(memory_ids))
                .values(
                    access_count=AgentMemory.access_count + 1,
                    last_accessed=datetime.utcnow(),
                )
            )
            await db.commit()

    # ── Convenience builders ──────────────────────────────────────────────────

    async def record_task_start(self, task_id: str, repository_id: str, description: str):
        await self.store_memory(
            content=f"Task started: {description}",
            memory_type="episodic",
            task_id=task_id,
            repository_id=repository_id,
            importance=0.6,
            metadata={"event": "task_start"},
        )

    async def record_task_completion(
        self,
        task_id: str,
        repository_id: str,
        summary: str,
        score: int = 7,
    ):
        await self.store_memory(
            content=f"Task completed (score {score}/10): {summary}",
            memory_type="episodic",
            task_id=task_id,
            repository_id=repository_id,
            importance=0.8,
            metadata={"event": "task_complete", "score": score},
        )

    async def record_code_pattern(
        self,
        repository_id: str,
        pattern: str,
        file_path: str,
    ):
        await self.store_memory(
            content=f"Code pattern observed in {file_path}: {pattern}",
            memory_type="semantic",
            repository_id=repository_id,
            importance=0.5,
            metadata={"event": "code_pattern", "file_path": file_path},
        )
