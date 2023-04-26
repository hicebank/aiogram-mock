# aiogram_mock

Tools for testing of aiogram applications

```
pip install git+https://github.com/hicebank/aiogram-mock#egg=aiogram_mock
```


Example
```python
from typing import Tuple, Generator

import pytest
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from aiogram_mock.facade_factory import private_chat_tg_control
from aiogram_mock.tg_control import PrivateChatTgControl


async def on_start(message: Message):
    await message.answer(
        'hello',
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text='ping', callback_data='ping')
                ]
            ]
        )
    )


async def on_click_me(query: CallbackQuery):
    await query.answer(text='pong')


def create_bot_and_dispatcher() -> Tuple[Bot, Dispatcher]:
    bot = Bot(token='123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11')
    dispatcher = Dispatcher()
    dispatcher.message.register(on_start, CommandStart())
    dispatcher.callback_query.register(on_click_me)
    return bot, dispatcher


@pytest.fixture()
def tg_control() -> Generator[PrivateChatTgControl, None, None]:
    bot, dispatcher = create_bot_and_dispatcher()
    with private_chat_tg_control(
        bot=bot,
        dispatcher=dispatcher,
    ) as tg_control:
        yield tg_control


async def test_start(tg_control):
    await tg_control.send("/start")
    assert tg_control.last_message.text == 'hello'

    answer = await tg_control.click(F.text == 'ping')
    assert answer.text == 'pong'
```

