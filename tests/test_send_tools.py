from QvQChat.tools_builtin import erispulse


from fakes import FakeSendChain, make_ctx


import pytest


@pytest.fixture(autouse=True)
def _zh_texts():
    """独立运行时也注册中文文案（修复对其它测试文件注册顺序的依赖）。"""
    from ErisPulse.Core import i18n
    from QvQChat import texts as _texts

    _texts.register_texts()
    i18n.set_language("zh-CN")
    yield
    i18n.reset_language()



def test_markdown_to_text_cleanup():
    md = "## ⚠️ 风险评估\n1. **QQ 风控**：高频\n2. *斜体* 与 ~~删除~~\n```py\nprint(1)\n```"
    out = __import__("QvQChat.utils", fromlist=["markdown_to_text"]).markdown_to_text(md)
    assert "##" not in out and "**" not in out and "*" not in out and "~~" not in out and "```" not in out
    assert "风险评估" in out and "QQ 风控" in out and "print(1)" in out


def test_pick_send_method():
    assert erispulse.pick_send_method(["Text", "Markdown"]) == "Markdown"
    assert erispulse.pick_send_method(["Html", "Text"]) == "Html"
    assert erispulse.pick_send_method(["Voice"]) == "Text"
    assert erispulse.pick_send_method([]) == "Markdown"


async def test_send_message_auto_selects_markdown():
    chain = FakeSendChain(sends=("Markdown", "Text"))
    main = __import__("fakes").FakeMain()
    main.sdk.adapter.add("onebot11", chain, sends=("Markdown", "Text"))
    out = await erispulse.send_message(
        make_ctx(main), platform="onebot11", target_type="group", target_id="1",
        text="## 标题\n**加粗**内容",
    )
    methods = [name for name, _, _ in chain.calls]
    assert methods[0] == "To"
    assert "Markdown" in methods
    raw = [a for name, a, _ in chain.calls if name == "Markdown"][0][0]
    assert raw == "## 标题\n**加粗**内容"
    assert "Markdown" in out


async def test_send_message_falls_back_to_plain_text():
    chain = FakeSendChain(sends=("Markdown", "Text"), fail_on=("Markdown",))
    main = __import__("fakes").FakeMain()
    main.sdk.adapter.add("onebot11", chain, sends=("Markdown", "Text"))
    out = await erispulse.send_message(
        make_ctx(main), platform="onebot11", target_type="group", target_id="1",
        text="**加粗**内容",
    )
    methods = [name for name, _, _ in chain.calls]
    assert methods == ["To", "Markdown", "Text"]
    fallback_arg = chain.calls[-1][1][0]
    assert fallback_arg == "加粗内容"
    assert "Text" in out


async def test_send_message_forced_method_validated():
    chain = FakeSendChain(sends=("Text",))
    main = __import__("fakes").FakeMain()
    main.sdk.adapter.add("onebot11", chain, sends=("Text",))
    out = await erispulse.send_message(
        make_ctx(main), platform="onebot11", target_type="group", target_id="1",
        text="hi", method="Markdown",
    )
    assert "不支持" in out
    out = await erispulse.send_message(
        make_ctx(main), platform="onebot11", target_type="group", target_id="1",
        text="hi", method="Text",
    )
    assert "[发送方式: Text]" in out


async def test_send_message_unknown_platform():
    out = await erispulse.send_message(
        make_ctx(), platform="nope", target_type="user", target_id="1", text="x"
    )
    assert "nope" in out


async def test_send_dsl_full_chain():
    chain = FakeSendChain(sends=("Markdown", "Text"))
    main = __import__("fakes").FakeMain()
    main.sdk.adapter.add("onebot11", chain, sends=("Markdown", "Text"))
    out = await erispulse.send_dsl(
        make_ctx(main),
        platform="onebot11", target_type="group", target_id="42",
        method="Markdown", params={"content": "# hello"},
        account="bot2",
        modifies=[{"Reply": "m1"}, {"At": "u1"}, "AtAll"],
        rules={"retry": 2, "timeout": 9, "defer": 3, "priority": [3, False]},
    )
    names = [name for name, _, _ in chain.calls]
    assert names[0] == "Using" and chain.calls[0][1] == ("bot2",)
    assert names[1] == "To" and chain.calls[1][1] == ("group", "42")
    assert "Retry" in names and "Timeout" in names and "Defer" in names and "Priority" in names
    assert "Reply" in names and "At" in names and "AtAll" in names
    assert names[-1] == "Markdown"
    assert chain.calls[-1][2] == {"content": "# hello"}
    assert '"sent": "Markdown"' in out


async def test_send_dsl_unknown_method_reports():
    chain = FakeSendChain(sends=("Text",))
    main = __import__("fakes").FakeMain()
    main.sdk.adapter.add("onebot11", chain, sends=("Text",))
    out = await erispulse.send_dsl(
        make_ctx(main), platform="onebot11", target_type="user", target_id="1",
        method="NoSuch",
    )
    assert "SendDSL" in out


async def test_send_message_auto_forwards_long_text():
    chain = FakeSendChain(sends=("Markdown", "Text", "MergeForward"))
    main = __import__("fakes").FakeMain(forward_threshold=50)
    main.sdk.adapter.add("onebot11", chain, sends=("Markdown", "Text", "MergeForward"))
    big = "## 适配器列表\n" + "\n".join(f"| 适配器{i} | 包{i} | 1.0.0 |" for i in range(30))
    out = await erispulse.send_message(
        make_ctx(main), platform="onebot11", target_type="group", target_id="1", text=big
    )
    names = [name for name, _, _ in chain.calls]
    assert "MergeForward" in names
    assert "[已作为合并转发消息发送]" in out
    node_arg = [a for name, a, _ in chain.calls if name == "MergeForward"][0][0]
    assert isinstance(node_arg, list) and len(node_arg) >= 2
    assert not any(name == "Markdown" for name in names)


async def test_send_message_explicit_method_skips_forward():
    chain = FakeSendChain(sends=("Markdown", "Text", "MergeForward"))
    main = __import__("fakes").FakeMain(forward_threshold=50)
    main.sdk.adapter.add("onebot11", chain, sends=("Markdown", "Text", "MergeForward"))
    big = "内容" * 300
    out = await erispulse.send_message(
        make_ctx(main), platform="onebot11", target_type="user", target_id="1",
        text=big, method="Text",
    )
    names = [name for name, _, _ in chain.calls]
    assert "MergeForward" not in names
    assert "Text" in names


async def test_send_message_short_text_no_forward():
    chain = FakeSendChain(sends=("Markdown", "Text", "MergeForward"))
    main = __import__("fakes").FakeMain(forward_threshold=500)
    main.sdk.adapter.add("onebot11", chain, sends=("Markdown", "Text", "MergeForward"))
    await erispulse.send_message(
        make_ctx(main), platform="onebot11", target_type="user", target_id="1", text="你好"
    )
    names = [name for name, _, _ in chain.calls]
    assert "MergeForward" not in names


async def test_send_message_as_forward_forces():
    chain = FakeSendChain(sends=("Markdown", "Text", "MergeForward"))
    main = __import__("fakes").FakeMain(forward_threshold=500)
    main.sdk.adapter.add("onebot11", chain, sends=("Markdown", "Text", "MergeForward"))
    out = await erispulse.send_message(
        make_ctx(main), platform="onebot11", target_type="group", target_id="1",
        text="你好", as_forward=True,
    )
    names = [name for name, _, _ in chain.calls]
    assert "MergeForward" in names
    assert "[已作为合并转发消息发送]" in out


async def test_send_message_as_forward_without_forward_method_falls_back():
    chain = FakeSendChain(sends=("Markdown", "Text", "MergeForward"))
    main = __import__("fakes").FakeMain()
    main.sdk.adapter.add("yunhu", chain, sends=("Markdown", "Text"))
    out = await erispulse.send_message(
        make_ctx(main), platform="yunhu", target_type="group", target_id="1",
        text="你好", as_forward=True,
    )
    names = [name for name, _, _ in chain.calls]
    assert "MergeForward" not in names and "Markdown" in names


async def test_send_message_forward_splits_before_strip_on_text_only():
# D5：先按 Markdown 标题切节、仅 Text-only 平台才剥离（旧实现先剥后切导致标题切块失效）
    chain = FakeSendChain(sends=("MergeForward", "Text"))
    main = __import__("fakes").FakeMain(forward_threshold=10)
    main.sdk.adapter.add("onebot11", chain, sends=("MergeForward", "Text"))
    text = "## 标题甲\n\n第一块内容。\n\n## 标题乙\n\n第二块内容。"
    out = await erispulse.send_message(
        make_ctx(main), platform="onebot11", target_type="user", target_id="1", text=text
    )
    assert "[已作为合并转发消息发送]" in out
    nodes = [a for name, a, _ in chain.calls if name == "MergeForward"][0][0]
    texts_ = [n["data"]["content"][0]["data"]["text"] for n in nodes]
    assert len(texts_) >= 2
    assert any("标题甲" in t for t in texts_) and any("标题乙" in t for t in texts_)
# Text-only 平台：节点内容已剥离 Markdown 标记
    assert all("##" not in t for t in texts_)


async def test_send_message_forward_keeps_markdown_on_markdown_platform():
    chain = FakeSendChain(sends=("Markdown", "Text", "MergeForward"))
    main = __import__("fakes").FakeMain(forward_threshold=10)
    main.sdk.adapter.add("onebot11", chain, sends=("Markdown", "Text", "MergeForward"))
    text = "## 标题甲\n\n第一块内容。\n\n## 标题乙\n\n第二块内容。"
    await erispulse.send_message(
        make_ctx(main), platform="onebot11", target_type="user", target_id="1", text=text
    )
    nodes = [a for name, a, _ in chain.calls if name == "MergeForward"][0][0]
    texts_ = [n["data"]["content"][0]["data"]["text"] for n in nodes]
    assert any(t.startswith("## 标题甲") for t in texts_)


async def test_send_message_forward_threshold_from_platform_profile():
# D2：forward_threshold 判定纳入平台 profile（通配命中覆盖全局值）
    chain = FakeSendChain(sends=("MergeForward", "Text"))
    main = __import__("fakes").FakeMain(
        forward_threshold=5000,
        delivery_profiles={"onebot*": {"forward_threshold": 10}},
    )
    main.sdk.adapter.add("onebot11", chain, sends=("MergeForward", "Text"))
    await erispulse.send_message(
        make_ctx(main), platform="onebot11", target_type="user", target_id="1",
        text="这段文本长度超过了十个字符！",
    )
    names = [name for name, _, _ in chain.calls]
    assert "MergeForward" in names


async def test_send_message_failure_enqueued_as_pending():
# D4：方法降级后仍失败 → 入待发队列而不是静默丢弃
    chain = FakeSendChain(sends=("Text",), fail_on=("Text",))
    main = __import__("fakes").FakeMain(send_retry=0, retry_delay=0)
    main.sdk.adapter.add("onebot11", chain, sends=("Text",))
    out = await erispulse.send_message(
        make_ctx(main), platform="onebot11", target_type="user", target_id="1", text="重要消息"
    )
    assert "待发队列" in out
    data = main.sdk.storage.get("QvQChat:pending_send:test:private:1")
    assert data and data[0]["text"] == "重要消息"
    assert data[0]["platform"] == "onebot11" and data[0]["target_id"] == "1"


async def test_handle_request_accept_and_reject():
    chain = FakeSendChain()
    main = __import__("fakes").FakeMain()
    main.sdk.adapter.add("onebot11", chain)
    out = await erispulse.handle_request(make_ctx(main), platform="onebot11", request_id="r1", action="accept")
    assert "accepted" in out
    out = await erispulse.handle_request(make_ctx(main), platform="onebot11", request_id="r2", action="reject")
    assert '"accepted": false' in out
    out = await erispulse.handle_request(make_ctx(main), platform="onebot11", request_id="r3", action="bogus")
    assert "不支持" in out


async def test_list_platforms_reports_sends():
    main = __import__("fakes").FakeMain()
    main.sdk.adapter.add("onebot11", FakeSendChain(), sends=("Markdown", "Text"))
    out = await erispulse.list_platforms(make_ctx(main))
    assert "onebot11" in out and "Markdown" in out
