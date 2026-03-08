"""
Authorization decorator for Jackgram bot commands.

When ADMIN_IDS is configured, only listed Telegram user IDs can execute
protected commands.  When ADMIN_IDS is empty (default), all users are
allowed – a startup warning is logged to remind the operator.
"""

import logging
from functools import wraps

from jackgram.bot.bot import ADMIN_IDS
from jackgram.bot.i18n import t

logger = logging.getLogger(__name__)


def admin_only(func):
    """Decorator that restricts a handler to authorized admin users."""

    @wraps(func)
    async def wrapper(event, *args, **kwargs):
        # If ADMIN_IDS is not configured, allow everyone (backwards compat)
        if ADMIN_IDS and event.sender_id not in ADMIN_IDS:
            logger.warning(f"Unauthorized command attempt by user {event.sender_id}")
            await event.reply(t("common.not_authorized_command"))
            return
        return await func(event, *args, **kwargs)

    return wrapper
