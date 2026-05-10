from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Any, Literal, Optional

from admin_backend.deps import get_session
from app.models.database import LLMChatSession, LLMChatSessionTurn, LLMModelProfile, PromptTemplate
from admin_backend.crud import (
    serialize_llm_chat_session,
    serialize_llm_chat_session_turn,
    serialize_llm_profile_detail,
    serialize_llm_profile,
)
from app.utils.llm_client import (
    stream_llm_chat,
    test_llm_connection,
    test_llm_connection_config,
    test_llm_connection_with_prompt,
)

router = APIRouter(prefix="/llm", tags=["llm"])


class ModelProfileCreate(BaseModel):
    name: str
    provider: str
    base_url: Optional[str] = ""
    api_key: Optional[str] = ""
    model_name: str
    enable_web_search: bool = False
    enable_reasoning: bool = False
    enable_image: bool = False
    enable_tools: bool = False
    is_active: bool = True
    is_default: bool = False
    notes: Optional[str] = ""

class PromptTemplateUpdate(BaseModel):
    prompt_text: str
    model_profile_id: Optional[int] = None


class ProfileActivationUpdate(BaseModel):
    enabled: bool = True


class BatchProfileTestRequest(BaseModel):
    profile_ids: list[int]
    prompt: str
    system_prompt: Optional[str] = "Reply with one short sentence."


class ChatMessageItem(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatProfileRequest(BaseModel):
    messages: list[ChatMessageItem] = Field(default_factory=list)
    system_prompt: str = ""
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, ge=1, le=32768)
    timeout: int = Field(default=120, ge=1, le=600)


class ChatSessionCreateRequest(BaseModel):
    title: str = "新会话"
    model_ids: list[int] = Field(default_factory=list)
    system_prompt: str = ""
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, ge=1, le=32768)
    source: str = "workbench"


class ChatSessionUpdateRequest(BaseModel):
    title: Optional[str] = None
    model_ids: Optional[list[int]] = None
    system_prompt: Optional[str] = None
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, ge=1, le=32768)
    source: Optional[str] = None


class ChatSessionTurnCreateRequest(BaseModel):
    prompt: str
    model_results: list[Any] = Field(default_factory=list)
    model_ids: Optional[list[int]] = None
    system_prompt: Optional[str] = None
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, ge=1, le=32768)
    source: str = "workbench"


def _apply_default_profile(db: Session, profile_id: int) -> LLMModelProfile:
    profile = db.query(LLMModelProfile).filter_by(id=profile_id).first()
    if not profile:
        raise HTTPException(404, "Profile not found")

    profile.is_default = True
    if not profile.is_active:
        profile.is_active = True
    db.commit()
    db.refresh(profile)
    return profile


def _normalize_model_ids(values: list[int] | list[Any] | None) -> list[int]:
    normalized: list[int] = []
    if not values:
        return normalized
    for value in values:
        try:
            model_id = int(value)
        except Exception:
            continue
        if model_id > 0 and model_id not in normalized:
            normalized.append(model_id)
    return normalized


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _get_chat_session_or_404(db: Session, session_key: str) -> LLMChatSession:
    session = db.query(LLMChatSession).filter(LLMChatSession.session_key == session_key).first()
    if not session:
        raise HTTPException(404, "Chat session not found")
    return session


def _build_chat_session_title(prompt: str) -> str:
    first_line = " ".join((prompt or "").strip().splitlines()).strip()
    if not first_line:
        return "新会话"
    if len(first_line) <= 24:
        return first_line
    return f"{first_line[:24].rstrip()}…"


def _serialize_chat_session_detail(session: LLMChatSession, db: Session) -> dict[str, Any]:
    turns = (
        db.query(LLMChatSessionTurn)
        .filter(LLMChatSessionTurn.session_id == session.id)
        .order_by(LLMChatSessionTurn.turn_index.asc(), LLMChatSessionTurn.id.asc())
        .all()
    )
    return {
        "session": serialize_llm_chat_session(session),
        "turns": [serialize_llm_chat_session_turn(turn) for turn in turns],
    }


def _touch_session_from_payload(session: LLMChatSession, payload: ChatSessionUpdateRequest | ChatSessionTurnCreateRequest) -> None:
    if getattr(payload, "model_ids", None) is not None:
        session.model_ids_json = _json_dumps(_normalize_model_ids(payload.model_ids))
    if getattr(payload, "system_prompt", None) is not None:
        session.system_prompt = (payload.system_prompt or "").strip()
    if getattr(payload, "temperature", None) is not None:
        session.temperature = float(payload.temperature)
    if getattr(payload, "max_tokens", None) is not None:
        session.max_tokens = int(payload.max_tokens)
    if getattr(payload, "source", None) is not None:
        session.source = (payload.source or "workbench").strip() or "workbench"


@router.get("/profiles")
def list_profiles(db: Session = Depends(get_session)):
    return [serialize_llm_profile(row) for row in db.query(LLMModelProfile).all()]


@router.get("/profiles/{profile_id}")
def get_profile(profile_id: int, db: Session = Depends(get_session)):
    profile = db.query(LLMModelProfile).filter_by(id=profile_id).first()
    if not profile:
        raise HTTPException(404, "Profile not found")
    return serialize_llm_profile_detail(profile)

@router.post("/profiles")
def create_profile(data: ModelProfileCreate, db: Session = Depends(get_session)):
    p = LLMModelProfile(**data.dict())
    db.add(p)
    db.commit()
    db.refresh(p)
    if data.is_default:
        p = _apply_default_profile(db, p.id)
    return serialize_llm_profile(p)

@router.put("/profiles/{profile_id}")
def update_profile(profile_id: int, data: ModelProfileCreate, db: Session = Depends(get_session)):
    p = db.query(LLMModelProfile).filter_by(id=profile_id).first()
    if not p:
        raise HTTPException(404, "Profile not found")
    for k, v in data.dict().items():
        setattr(p, k, v)
    db.commit()
    db.refresh(p)
    if data.is_default:
        p = _apply_default_profile(db, p.id)
    return serialize_llm_profile(p)


@router.post("/profiles/{profile_id}/activate")
def activate_profile(profile_id: int, db: Session = Depends(get_session)):
    profile = _apply_default_profile(db, profile_id)
    return serialize_llm_profile(profile)

@router.delete("/profiles/{profile_id}")
def delete_profile(profile_id: int, db: Session = Depends(get_session)):
    p = db.query(LLMModelProfile).filter_by(id=profile_id).first()
    if p:
        db.delete(p)
    db.commit()
    return {"success": True}


@router.get("/chat-sessions")
def list_chat_sessions(
    q: str | None = None,
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_session),
):
    page = max(1, int(page or 1))
    page_size = min(200, max(1, int(page_size or 50)))
    query = db.query(LLMChatSession)
    if q and q.strip():
      pattern = f"%{q.strip()}%"
      query = query.filter(
          (LLMChatSession.title.ilike(pattern)) | (LLMChatSession.session_key.ilike(pattern))
      )
    total = query.order_by(None).count()
    rows = (
        query.order_by(
            LLMChatSession.last_turn_at.desc().nullslast(),
            LLMChatSession.updated_at.desc().nullslast(),
            LLMChatSession.id.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [serialize_llm_chat_session(row) for row in rows],
    }


@router.post("/chat-sessions")
def create_chat_session(payload: ChatSessionCreateRequest, db: Session = Depends(get_session)):
    session = LLMChatSession(
        session_key=f"chat_{uuid4().hex}",
        title=(payload.title or "新会话").strip() or "新会话",
        source=(payload.source or "workbench").strip() or "workbench",
        model_ids_json=_json_dumps(_normalize_model_ids(payload.model_ids)),
        system_prompt=(payload.system_prompt or "").strip(),
        temperature=float(payload.temperature),
        max_tokens=int(payload.max_tokens),
        turns_count=0,
        last_turn_at=None,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return serialize_llm_chat_session(session)


@router.get("/chat-sessions/{session_key}")
def get_chat_session(session_key: str, db: Session = Depends(get_session)):
    session = _get_chat_session_or_404(db, session_key)
    return _serialize_chat_session_detail(session, db)


@router.put("/chat-sessions/{session_key}")
def update_chat_session(
    session_key: str,
    payload: ChatSessionUpdateRequest,
    db: Session = Depends(get_session),
):
    session = _get_chat_session_or_404(db, session_key)
    if payload.title is not None:
        title = payload.title.strip()
        session.title = title or "新会话"
    _touch_session_from_payload(session, payload)
    db.commit()
    db.refresh(session)
    return serialize_llm_chat_session(session)


@router.post("/chat-sessions/{session_key}/duplicate")
def duplicate_chat_session(session_key: str, db: Session = Depends(get_session)):
    session = _get_chat_session_or_404(db, session_key)
    source_turns = (
        db.query(LLMChatSessionTurn)
        .filter(LLMChatSessionTurn.session_id == session.id)
        .order_by(LLMChatSessionTurn.turn_index.asc(), LLMChatSessionTurn.id.asc())
        .all()
    )
    duplicated = LLMChatSession(
        session_key=f"chat_{uuid4().hex}",
        title=f"{session.title} 副本",
        source=session.source or "workbench",
        model_ids_json=session.model_ids_json or "[]",
        system_prompt=session.system_prompt or "",
        temperature=session.temperature,
        max_tokens=session.max_tokens,
        turns_count=0,
        last_turn_at=None,
    )
    db.add(duplicated)
    db.flush()
    for turn in source_turns:
        db.add(
            LLMChatSessionTurn(
                session_id=duplicated.id,
                turn_index=turn.turn_index,
                source=turn.source or session.source or "workbench",
                user_prompt=turn.user_prompt,
                model_results_json=turn.model_results_json or "[]",
                created_at=turn.created_at,
                updated_at=turn.updated_at,
            )
        )
    duplicated.turns_count = len(source_turns)
    duplicated.last_turn_at = source_turns[-1].created_at if source_turns else None
    db.commit()
    db.refresh(duplicated)
    return _serialize_chat_session_detail(duplicated, db)


@router.post("/chat-sessions/{session_key}/clear")
def clear_chat_session(session_key: str, db: Session = Depends(get_session)):
    session = _get_chat_session_or_404(db, session_key)
    db.query(LLMChatSessionTurn).filter(LLMChatSessionTurn.session_id == session.id).delete(
        synchronize_session=False
    )
    session.turns_count = 0
    session.last_turn_at = None
    db.commit()
    db.refresh(session)
    return serialize_llm_chat_session(session)


@router.delete("/chat-sessions/{session_key}")
def delete_chat_session(session_key: str, db: Session = Depends(get_session)):
    session = _get_chat_session_or_404(db, session_key)
    db.query(LLMChatSessionTurn).filter(LLMChatSessionTurn.session_id == session.id).delete(
        synchronize_session=False
    )
    db.delete(session)
    db.commit()
    return {"success": True}


@router.post("/chat-sessions/{session_key}/turns")
def add_chat_session_turn(
    session_key: str,
    payload: ChatSessionTurnCreateRequest,
    db: Session = Depends(get_session),
):
    session = _get_chat_session_or_404(db, session_key)
    prompt = payload.prompt.strip()
    if not prompt:
        raise HTTPException(400, "prompt required")

    _touch_session_from_payload(session, payload)
    if not session.title or session.title.strip() in {"新会话", "New session", "New Chat"}:
        session.title = _build_chat_session_title(prompt)

    current_turn_index = int(session.turns_count or 0) + 1
    turn = LLMChatSessionTurn(
        session_id=session.id,
        turn_index=current_turn_index,
        source=(payload.source or session.source or "workbench").strip() or "workbench",
        user_prompt=prompt,
        model_results_json=_json_dumps(payload.model_results or []),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    session.turns_count = current_turn_index
    session.last_turn_at = turn.created_at
    db.add(turn)
    db.commit()
    db.refresh(session)
    db.refresh(turn)
    return {
        "session": serialize_llm_chat_session(session),
        "turn": serialize_llm_chat_session_turn(turn),
    }

@router.post("/profiles/{profile_id}/test_connection")
def api_test_connection(profile_id: int):
    return test_llm_connection(profile_id)


@router.post("/test_connection")
def api_test_connection_config(data: ModelProfileCreate):
    return test_llm_connection_config(data)


@router.post("/profiles/{profile_id}/chat")
def chat_profile(profile_id: int, payload: ChatProfileRequest, db: Session = Depends(get_session)):
    profile = db.query(LLMModelProfile).filter_by(id=profile_id).first()
    if not profile:
        raise HTTPException(404, "Profile not found")

    messages = [
        {"role": item.role, "content": item.content.strip()}
        for item in payload.messages
        if item.content and item.content.strip()
    ]

    def event_stream():
        try:
            for event in stream_llm_chat(
                profile,
                messages,
                system_prompt=payload.system_prompt,
                temperature=payload.temperature,
                max_tokens=payload.max_tokens,
                timeout=payload.timeout,
            ):
                yield json.dumps(event, ensure_ascii=False) + "\n"
        except Exception as exc:
            yield json.dumps(
                {
                    "type": "error",
                    "success": False,
                    "message": str(exc),
                },
                ensure_ascii=False,
            ) + "\n"

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson; charset=utf-8",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/profiles/batch_test")
def batch_test_profiles(payload: BatchProfileTestRequest, db: Session = Depends(get_session)):
    profile_ids = [int(profile_id) for profile_id in payload.profile_ids if int(profile_id) > 0]
    if not profile_ids:
        raise HTTPException(400, "profile_ids required")

    prompt_text = payload.prompt.strip()
    if not prompt_text:
        raise HTTPException(400, "prompt required")

    profiles = db.query(LLMModelProfile).filter(LLMModelProfile.id.in_(profile_ids)).all()
    profile_map = {profile.id: profile for profile in profiles}
    ordered_profiles = [profile_map[profile_id] for profile_id in profile_ids if profile_id in profile_map]
    missing_ids = [profile_id for profile_id in profile_ids if profile_id not in profile_map]

    if not ordered_profiles and not missing_ids:
        raise HTTPException(404, "Profile not found")

    def run_one(profile: LLMModelProfile) -> dict[str, object]:
        started = time.perf_counter()
        result = test_llm_connection_with_prompt(profile, prompt_text)
        elapsed = result.get("elapsed_seconds")
        if elapsed is None:
            elapsed = round(time.perf_counter() - started, 2)
        return {
            "profile_id": profile.id,
            "profile_name": profile.name,
            "provider": profile.provider,
            "model_name": profile.model_name,
            "success": bool(result.get("success", False)),
            "message": result.get("message") or "",
            "elapsed_seconds": elapsed,
            "prompt_text": result.get("prompt_text") or prompt_text,
            "response_text": result.get("response_text") or "",
            "web_search_mode": result.get("web_search_mode"),
            "web_search_used": result.get("web_search_used"),
        }

    items: list[dict[str, object]] = []
    if ordered_profiles:
        max_workers = min(8, len(ordered_profiles))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {executor.submit(run_one, profile): profile.id for profile in ordered_profiles}
            collected: dict[int, dict[str, object]] = {}
            for future in as_completed(future_map):
                profile_id = future_map[future]
                try:
                    collected[profile_id] = future.result()
                except Exception as exc:
                    profile = profile_map.get(profile_id)
                    collected[profile_id] = {
                        "profile_id": profile_id,
                        "profile_name": profile.name if profile else "",
                        "provider": profile.provider if profile else "",
                        "model_name": profile.model_name if profile else "",
                        "success": False,
                        "message": str(exc),
                        "elapsed_seconds": None,
                        "prompt_text": prompt_text,
                        "response_text": "",
                        "web_search_mode": None,
                        "web_search_used": None,
                    }
            items.extend(collected[profile_id] for profile_id in profile_ids if profile_id in collected)

    for missing_id in missing_ids:
        items.append(
            {
                "profile_id": missing_id,
                "profile_name": "",
                "provider": "",
                "model_name": "",
                "success": False,
                "message": "Profile not found",
                "elapsed_seconds": None,
                "prompt_text": prompt_text,
                "response_text": "",
                "web_search_mode": None,
                "web_search_used": None,
            }
        )

    success_count = sum(1 for item in items if item.get("success"))
    failure_count = len(items) - success_count
    return {
        "prompt": prompt_text,
        "system_prompt": payload.system_prompt or "",
        "total": len(items),
        "success_count": success_count,
        "failure_count": failure_count,
        "items": items,
    }


@router.post("/profiles/{profile_id}/activation")
def update_profile_activation(
    profile_id: int,
    data: ProfileActivationUpdate,
    db: Session = Depends(get_session),
):
    profile = db.query(LLMModelProfile).filter_by(id=profile_id).first()
    if not profile:
        raise HTTPException(404, "Profile not found")

    profile.is_default = bool(data.enabled)
    if profile.is_default and not profile.is_active:
        profile.is_active = True
    db.commit()
    db.refresh(profile)
    return serialize_llm_profile(profile)

@router.get("/prompts")
def list_prompts(db: Session = Depends(get_session)):
    return db.query(PromptTemplate).all()

@router.put("/prompts/{prompt_id}")
def update_prompt(prompt_id: int, data: PromptTemplateUpdate, db: Session = Depends(get_session)):
    pt = db.query(PromptTemplate).filter_by(id=prompt_id).first()
    if not pt:
        raise HTTPException(404, "Prompt not found")
    pt.prompt_text = data.prompt_text
    pt.model_profile_id = data.model_profile_id
    db.commit()
    db.refresh(pt)
    return pt
