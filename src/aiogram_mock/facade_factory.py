from contextlib import contextmanager
from typing import Callable, Generator, Iterable
from unittest.mock import patch

from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.types import Chat, User

from aiogram_mock.mocked_session import MockedSession
from aiogram_mock.tg_control import PrivateChatTgControl, TgControl
from aiogram_mock.tg_state import TgState


@contextmanager
def private_chat_tg_control(
    dispatcher: Dispatcher,
    bot: Bot,
    target_user: User | None = None,
    bot_user: User | None = None,
    tg_state_factory: Callable[[Iterable[Chat]], TgState] = TgState,
    mocked_session_factory: Callable[[TgState, User], BaseSession] = MockedSession,
) -> Generator[PrivateChatTgControl, None, None]:
    if target_user is None:
        target_user = User(
            id=103592704,
            first_name='Linus',
            last_name='Torvalds',
            is_bot=False,
        )
    if bot_user is None:
        bot_user = User(
            id=738453453,
            first_name='Test',
            last_name='bot',
            username='test_bot',
            is_bot=True,
        )

    chat = Chat(
        id=target_user.id,
        type='private',
        username=target_user.username,
        first_name=target_user.first_name,
        last_name=target_user.last_name,
    )

    tg_state = tg_state_factory([chat])
    session = mocked_session_factory(tg_state, bot_user)
    with patch.object(bot, 'session', session):
        yield PrivateChatTgControl(
            tg_control=TgControl(
                dispatcher=dispatcher,
                bot=bot,
                tg_state=tg_state,
            ),
            chat=chat,
            user=target_user,
        )
