active_private_conversations: set[int] = set()


def mark_conversation_active(user_id: int) -> None:
    active_private_conversations.add(user_id)


def mark_conversation_inactive(user_id: int) -> None:
    active_private_conversations.discard(user_id)


def is_conversation_active(user_id: int) -> bool:
    return user_id in active_private_conversations
