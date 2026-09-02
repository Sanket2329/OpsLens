from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ConversationResponse,
    ConversationSummary,
)
from app.security.dependencies import get_current_user
from app.services.conversation_service import ConversationService

from app.core.rate_limiter import limiter
from fastapi import APIRouter, Depends, HTTPException, Request

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)

@router.post(
    "",
    response_model=ChatResponse,
)
@limiter.limit("10/minute")
def chat(
    request: Request,
    chat_request: ChatRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = ConversationService(db)

    result = service.chat(
        question=chat_request.question,
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        conversation_id=chat_request.conversation_id,
    )

    return ChatResponse(
        answer=result["answer"],
        conversation_id=result["conversation_id"],
    )


@router.get(
    "/conversations",
    response_model=list[ConversationSummary],
)
def list_conversations(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = ConversationService(db)

    return service.list_conversations(
        user_id=current_user.id,
        organization_id=current_user.organization_id,
    )


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationResponse,
)
def get_conversation(
    conversation_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = ConversationService(db)

    conversation = service.get_conversation(
        conversation_id=conversation_id,
        user_id=current_user.id,
    )

    if conversation is None:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found",
        )

    return conversation
