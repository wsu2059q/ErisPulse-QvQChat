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
# build_hash="1b6b448f2864fe7d5e92a29fea7ce8bb144d9209b3174ac078a13dc81b25f190"
