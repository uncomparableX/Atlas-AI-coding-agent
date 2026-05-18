import asyncio
import json

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.websockets.manager import redis_forwarder, ws_manager

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.websocket("/tasks/{task_id}")
async def task_stream(websocket: WebSocket, task_id: str):
    await ws_manager.connect(websocket, task_id)
    await redis_forwarder.subscribe_task(task_id)
    try:
        await websocket.send_json({"type": "connected", "task_id": task_id})
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "ping"})
            except WebSocketDisconnect:
                break
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("WebSocket error", task_id=task_id, error=str(e))
    finally:
        ws_manager.disconnect(websocket)


@router.websocket("/repos/{repo_id}/index")
async def repo_index_stream(websocket: WebSocket, repo_id: str):
    await ws_manager.connect(websocket, f"index:{repo_id}")
    try:
        await websocket.send_json({"type": "connected", "repo_id": repo_id})
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "ping"})
            except WebSocketDisconnect:
                break
    finally:
        ws_manager.disconnect(websocket)
