moduleInfo = {
    "meta": {
        "name": "AIChat",
        "version": "1.6.0",
        "description": "AIChat 聊天模块",
        "author": "wsu2059q",
        "license": "MIT",
        "homepage": "https://github.com/wsu2059q/ErisPulse-AIChat"
    },
    "dependencies": {
        "requires": ["OpenAI"],
        "optional": [["OneBotAdapter", "YunhuAdapter", "TelegramAdapter"]],
        "pip": ["openai"]
    }
}

from .Core import Main