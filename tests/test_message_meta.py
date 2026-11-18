"""assistant 条目记录回复出处（model + token 计数）。"""

import asyncio
import time

from fakes import FakeMain

from QvQChat.conversation.service import ConversationService


def test_finalize_stores_model_meta():
    main = FakeMain()
    manager = ConversationService(main)
    key = "s-meta"
    manager.append_user(key, "你好")
    manager.finalize(
        key, "喵～",
        usage={"prompt_tokens": 120, "completion_tokens": 34, "total_tokens": 154, "cost": 0.001},
        model="deepseek-chat",
    )
    entry = manager.get_contexts(key)[-1]
    assert entry["role"] == "assistant"
    assert entry["meta"]["model"] == "deepseek-chat"
    assert entry["meta"]["usage"] == {"prompt_tokens": 120, "completion_tokens": 34, "total_tokens": 154}
    # 聚合记账照旧发生（record_usage 路径不受影响）
    today = main.sdk.storage.get(f"QvQChat:usage:{time.strftime('%Y-%m-%d')}", {})
    assert today.get("by_model", {}).get("deepseek-chat") == {"tokens": 154, "in": 120, "out": 34}


def test_finalize_without_model_has_no_meta():
    main = FakeMain()
    manager = ConversationService(main)
    key = "s-meta0"
    manager.finalize(key, "嗯")
    entry = manager.get_contexts(key)[-1]
    assert "meta" not in entry


def test_append_meta_passthrough():
    main = FakeMain()
    manager = ConversationService(main)
    key = "s-meta1"
    manager.append(key, "assistant", "带出处的回复", meta={"model": "glm-5"})
    entry = manager.get_contexts(key)[-1]
    assert entry["meta"] == {"model": "glm-5"}
