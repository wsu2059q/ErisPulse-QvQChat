from QvQChat.tools_builtin import erispulse

from fakes import FakeSendChain, make_ctx


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
