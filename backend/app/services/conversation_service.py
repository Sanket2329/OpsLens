"""
ConversationService — manages multi-turn chat sessions with memory.
"""

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.conversation import Conversation, Message
from app.repositories.conversation_repository import ConversationRepository
from app.services.rag_service import RagService

logger = get_logger(__name__)


class ConversationService:

    def __init__(self, db: Session):
        self.db = db
        self.repo = ConversationRepository(db)
        self.rag = RagService()

    def chat(
        self,
        question: str,
        user_id: int,
        organization_id: int,
        conversation_id: int | None = None,
    ) -> dict:
        # 1. Load existing or create new conversation
        conversation = None

        if conversation_id is not None:
            conversation = self.repo.get_by_id(
                conversation_id=conversation_id,
                user_id=user_id,
            )
            if conversation is None:
                logger.warning(
                    "conversation_id=%d not found or belongs to another user=%d — starting new",
                    conversation_id,
                    user_id,
                )

        if conversation is None:
            conversation = self._create_conversation(
                user_id=user_id,
                organization_id=organization_id,
                title=question[:80],
            )
            logger.info(
                "New conversation created: id=%d user_id=%d",
                conversation.id,
                user_id,
            )

        # 2. Build history context
        history = [
            {"role": msg.role, "content": msg.content}
            for msg in conversation.messages
        ]

        # 3. Generate answer with memory
        answer = self.rag.answer(
            question=question,
            organization_id=organization_id,
            conversation_history=history,
        )

        # 4. Persist both turns atomically
        self.repo.add_message(
            Message(
                conversation_id=conversation.id,
                role="user",
                content=question,
            )
        )
        self.repo.add_message(
            Message(
                conversation_id=conversation.id,
                role="assistant",
                content=answer,
            )
        )

        logger.info(
            "Chat turn saved: conversation_id=%d user_id=%d",
            conversation.id,
            user_id,
        )

        return {
            "answer": answer,
            "conversation_id": conversation.id,
        }

    def list_conversations(
        self,
        user_id: int,
        organization_id: int,
    ) -> list[Conversation]:
        return self.repo.list_by_user(
            user_id=user_id,
            organization_id=organization_id,
        )

    def get_conversation(
        self,
        conversation_id: int,
        user_id: int,
    ) -> Conversation | None:
        return self.repo.get_by_id(
            conversation_id=conversation_id,
            user_id=user_id,
        )

    def _create_conversation(
        self,
        user_id: int,
        organization_id: int,
        title: str | None = None,
    ) -> Conversation:
        return self.repo.create(
            Conversation(
                user_id=user_id,
                organization_id=organization_id,
                title=title,
            )
        )
