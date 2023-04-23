from datetime import datetime
from typing import Any, AsyncGenerator, Mapping, Sequence, Type

from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.methods import (AnswerCallbackQuery, EditMessageReplyMarkup,
                             EditMessageText, SendMessage, SendPhoto,
                             SetChatMenuButton, TelegramMethod)
from aiogram.methods.base import TelegramType
from aiogram.types import (UNSET, InlineKeyboardMarkup, Message,
                           ReplyKeyboardRemove, User)

from aiogram_mock.tg_state import TgState

SendMessageVariant = SendMessage | SendPhoto


class MockedSession(BaseSession):
    def __init__(self, tg_state: TgState, bot_user: User):
        self._tg_state = tg_state
        self._bot_user = bot_user
        self._sent_methods: list[TelegramMethod[Any]] = []
        super().__init__()

    async def close(self) -> None:
        pass

    def _process_reply_markup(self, chat_id: int, method: SendMessageVariant) -> InlineKeyboardMarkup | None:
        if isinstance(method.reply_markup, InlineKeyboardMarkup):
            return method.reply_markup
        elif isinstance(method.reply_markup, ReplyKeyboardRemove):
            self._tg_state.update_chat_user_state(chat_id=chat_id, reply_markup=None)
            return None
        if method.reply_markup is not None:
            self._tg_state.update_chat_user_state(chat_id=chat_id, reply_markup=method.reply_markup)
        return None

    def _process_reply(self, chat_id: int, method: SendMessageVariant) -> Message | None:
        if method.reply_to_message_id is not None:
            try:
                return self._tg_state.get_message(chat_id, method.reply_to_message_id)
            except KeyError:
                if not method.allow_sending_without_reply:
                    raise
        return None

    async def _mock_send_message(self, bot: Bot, method: SendMessage, timeout: int | None = UNSET) -> Message:
        chat_id = int(method.chat_id)
        return self._tg_state.add_message(
            Message(
                message_id=self._tg_state.next_message_id(chat_id),
                text=method.text,
                chat=self._tg_state.chats[chat_id],
                date=datetime.utcnow(),
                message_thread_id=method.message_thread_id,
                from_user=self._bot_user,
                reply_to_message=self._process_reply(chat_id, method),
                reply_markup=self._process_reply_markup(chat_id, method),
            ),
        )

    async def _mock_send_photo(self, bot: Bot, method: SendPhoto, timeout: int | None = UNSET) -> Message:
        chat_id = int(method.chat_id)
        return self._tg_state.add_message(
            Message(
                message_id=self._tg_state.next_message_id(chat_id),
                text=method.caption,
                chat=self._tg_state.chats[chat_id],
                date=datetime.utcnow(),
                message_thread_id=method.message_thread_id,
                from_user=self._bot_user,
                reply_to_message=self._process_reply(chat_id, method),
                reply_markup=self._process_reply_markup(chat_id, method),
                document=await self._tg_state.load_file(bot.id, method.photo),
            ),
        )

    async def _mock_answer_callback_query(
        self,
        bot: Bot,
        method: AnswerCallbackQuery,
        timeout: int | None = UNSET,
    ) -> bool:
        self._tg_state.add_answer_callback_query(method)
        return True

    async def _mock_set_chat_menu_button(
        self,
        bot: Bot,
        method: AnswerCallbackQuery,
        timeout: int | None = UNSET,
    ) -> bool:
        return True

    async def _mock_edit_message_text(
        self,
        bot: Bot,
        method: EditMessageText,
        timeout: int | None = UNSET,
    ) -> Message | bool:
        if method.chat_id is None and method.message_id is None:
            raise NotImplementedError('Editing of inlined message is not supported')
        if method.chat_id is None or method.message_id is None:
            raise ValueError('Bad sent message')

        message = self._tg_state.get_message(int(method.chat_id), method.message_id)
        new_message = message.copy(
            update={'text': method.text, 'reply_markup': method.reply_markup},
        )
        self._tg_state.replace_message(new_message)
        return new_message

    async def _mock_edit_message_reply_markup(
        self,
        bot: Bot,
        method: EditMessageReplyMarkup,
        timeout: int | None = UNSET,
    ) -> Message | bool:
        if method.chat_id is None and method.message_id is None:
            raise NotImplementedError('Edititng of inlined message is not supported')
        if method.chat_id is None or method.message_id is None:
            raise ValueError('Bad sent message')

        message = self._tg_state.get_message(int(method.chat_id), method.message_id)
        new_message = message.copy(
            update={'reply_markup': method.reply_markup},
        )
        self._tg_state.replace_message(new_message)
        return new_message

    METHOD_MOCKS: Mapping[Type[TelegramMethod[Any]], str] = {
        SendMessage: _mock_send_message.__name__,
        SendPhoto: _mock_send_photo.__name__,
        AnswerCallbackQuery: _mock_answer_callback_query.__name__,
        SetChatMenuButton: _mock_set_chat_menu_button.__name__,
        EditMessageText: _mock_edit_message_text.__name__,
        EditMessageReplyMarkup: _mock_edit_message_reply_markup.__name__,
    }

    async def make_request(
        self,
        bot: Bot,
        method: TelegramMethod[TelegramType],
        timeout: int | None = UNSET,
    ) -> TelegramType:
        self._sent_methods.append(method)
        try:
            method_mock_attr = self.METHOD_MOCKS[type(method)]
        except KeyError:
            raise TypeError(f'Method mock for type {type(method)} is not implemented') from None

        return await getattr(self, method_mock_attr)(bot, method, timeout)

    def stream_content(
        self,
        url: str,
        timeout: int,
        chunk_size: int,
        raise_for_status: bool,
    ) -> AsyncGenerator[bytes, None]:
        raise NotImplementedError

    @property
    def sent_methods(self) -> Sequence[TelegramMethod[Any]]:
        return self._sent_methods
