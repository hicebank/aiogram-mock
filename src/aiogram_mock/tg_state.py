import itertools
from collections import defaultdict
from dataclasses import dataclass, replace
from typing import DefaultDict, Iterable, Mapping, Sequence, Dict, Tuple, List
from uuid import uuid4

from aiogram.methods import AnswerCallbackQuery
from aiogram.types import (
    UNSET,
    Chat,
    Document,
    ForceReply,
    InlineKeyboardMarkup,
    InputFile,
    Message,
    ReplyKeyboardMarkup,
)


@dataclass(frozen=True)
class UserState:
    reply_markup: ReplyKeyboardMarkup | ForceReply | None = None


class TgState:
    def __init__(self, chats: Iterable[Chat]):
        self._chats = {chat.id: chat for chat in chats}
        self._histories: Dict[int, List[Message | None]] = {chat.id: [] for chat in chats}
        self._message_dict: Dict[Tuple[int, int], Message] = {}
        self._last_update_id: int = 0
        self._last_callback_query_id: int = 0
        self._answers: Dict[str, AnswerCallbackQuery] = {}

        self._chat_user_state: Dict[int, UserState] = {chat.id: UserState() for chat in chats}
        self._selective_user_state: Dict[int, Dict[int, UserState]] = {}

        self._content_to_unique_id: Dict[bytes, str] = {}
        self._user_id_to_unique_id_to_local_id: DefaultDict[int, Dict[str, str]] = defaultdict(dict)
        self._user_id_to_local_id_to_unique_id: DefaultDict[int, Dict[str, str]] = defaultdict(dict)

    @property
    def chats(self) -> Mapping[int, Chat]:
        return self._chats

    def chat_history(self, chat_id: int) -> Sequence[Message]:
        return [message for message in self._histories[chat_id] if message is not None]

    def add_chat(self, chat: Chat, history: Iterable[Message] = ()) -> None:
        if chat.id in self._chats:
            raise ValueError('chat.id duplication')

        self._chats[chat.id] = chat
        self._histories[chat.id] = list(history)
        self._chat_user_state[chat.id] = UserState()

    def next_message_id(self, chat_id: int) -> int:
        return len(self._histories[chat_id])

    def _validate_message(self, message: Message) -> None:
        if isinstance(message.reply_markup, InlineKeyboardMarkup):
            buttons = itertools.chain.from_iterable(message.reply_markup.inline_keyboard)
            for button in buttons:
                if button.callback_data is not None and len(button.callback_data) > 64:
                    raise ValueError(f'callback_data of {button} has more than 64 chars')

    def add_message(self, message: Message) -> Message:
        if (message.chat.id, message.message_id) in self._message_dict:
            raise ValueError('(message.chat.id, message.message_id) duplication')

        self._validate_message(message)
        self._histories[message.chat.id].append(message)
        self._message_dict[(message.chat.id, message.message_id)] = message
        return message

    def get_message(self, chat_id: int, message_id: int) -> Message:
        return self._message_dict[(chat_id, message_id)]

    def replace_message(self, new_message: Message) -> None:
        if (new_message.chat.id, new_message.message_id) not in self._message_dict:
            raise KeyError('(message.chat.id, message.message_id) not exists')

        self._validate_message(new_message)
        self._histories[new_message.chat.id][new_message.message_id] = new_message
        self._message_dict[(new_message.chat.id, new_message.message_id)] = new_message

    def delete_message(self, chat_id: int, message_id: int) -> None:
        self._histories[chat_id][message_id] = None
        del self._message_dict[(chat_id, message_id)]

    def increment_update_id(self) -> int:
        self._last_update_id += 1
        return self._last_update_id

    def next_callback_query_id(self) -> str:
        self._last_callback_query_id += 1
        return str(self._last_callback_query_id)

    def add_answer_callback_query(self, answer: AnswerCallbackQuery) -> None:
        if answer.callback_query_id in self._answers:
            raise ValueError('callback_query_id duplication')
        self._answers[answer.callback_query_id] = answer

    def get_answer_callback_query(self, callback_query_id: str) -> AnswerCallbackQuery:
        return self._answers[callback_query_id]

    def get_user_state(self, *, chat_id: int, user_id: int) -> UserState:
        try:
            return self._selective_user_state.get(chat_id, {})[user_id]
        except KeyError:
            pass

        return self._chat_user_state[chat_id]

    def update_chat_user_state(
        self,
        chat_id: int,
        reply_markup: ReplyKeyboardMarkup | ForceReply | None = UNSET,
    ) -> None:
        replace_data = {}
        if reply_markup != UNSET:
            replace_data['reply_markup'] = reply_markup

        if chat_id in self._selective_user_state:
            self._selective_user_state[chat_id] = {
                user_id: replace(user_state, **replace_data)
                for user_id, user_state in self._selective_user_state[chat_id].items()
            }
        self._chat_user_state[chat_id] = replace(self._chat_user_state[chat_id], **replace_data)

    def update_selective_user_state(
        self,
        chat_id: int,
        users_ids: Iterable[int],
        reply_markup: ReplyKeyboardMarkup | ForceReply | None = UNSET,
    ) -> None:
        replace_data = {}
        if reply_markup != UNSET:
            replace_data['reply_markup'] = reply_markup

        chat_dict = self._selective_user_state[chat_id]
        for user_id in users_ids:
            chat_dict[user_id] = replace(chat_dict.get(user_id, UserState()), **replace_data)

    def _generate_file_unique_id(self) -> str:
        return str(uuid4())

    def _generate_file_local_id(self, user_id: int) -> str:
        return f'{user_id}-{str(uuid4())}'

    async def _read_content(self, input_file: InputFile) -> bytes:
        parts = []
        async for chunk in input_file:
            parts.append(chunk)
        return b''.join(parts)

    def _get_or_create_file_unique_id(self, content: bytes) -> str:
        if content in self._content_to_unique_id:
            return self._content_to_unique_id[content]

        unique_id = self._generate_file_unique_id()
        self._content_to_unique_id[content] = unique_id
        return unique_id

    def _get_or_create_file_local_id(self, user_id: int, unique_id: str) -> str:
        unique_id_to_local_id = self._user_id_to_unique_id_to_local_id[user_id]
        if unique_id in unique_id_to_local_id:
            return unique_id_to_local_id[unique_id]

        local_id_to_unique_id = self._user_id_to_local_id_to_unique_id[user_id]
        local_id = self._generate_file_local_id(user_id)
        unique_id_to_local_id[unique_id] = local_id
        local_id_to_unique_id[local_id] = unique_id
        return local_id

    async def load_file(self, user_id: int, input_file: InputFile | str) -> Document:
        if isinstance(input_file, str):
            unique_id = self._user_id_to_local_id_to_unique_id[user_id][input_file]
            return Document(
                file_id=input_file,
                file_unique_id=unique_id,
                # need to save file_name
            )

        content = await self._read_content(input_file)
        unique_id = self._get_or_create_file_unique_id(content)
        local_id = self._get_or_create_file_local_id(user_id, unique_id)
        return Document(
            file_id=local_id,
            file_unique_id=unique_id,
            file_name=input_file.filename,
        )
