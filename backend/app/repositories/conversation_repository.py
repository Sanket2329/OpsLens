from sqlalchemy.orm import Session

from app.models.conversation import Conversation, Message


class ConversationRepository:

    def __init__(self, db: Session):
        self.db = db

    def create(self, conversation: Conversation) -> Conversation:
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    def get_by_id(
        self,
        conversation_id: int,
        user_id: int,
    ) -> Conversation | None:
        return (
            self.db.query(Conversation)
            .filter(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
            .first()
        )

    def list_by_user(
        self,
        user_id: int,
        organization_id: int,
        limit: int = 50,
    ) -> list[Conversation]:
        return (
            self.db.query(Conversation)
            .filter(
                Conversation.user_id == user_id,
                Conversation.organization_id == organization_id,
            )
            .order_by(Conversation.created_at.desc())
            .limit(limit)
            .all()
        )

    def add_message(self, message: Message) -> Message:
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message
