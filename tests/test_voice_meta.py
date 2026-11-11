import asyncio

from QvQChat import utils
from QvQChat.Main import Main
from QvQChat.tools_builtin import erispulse


from fakes import FakeChatEvent, FakeMain, FakeSendChain, make_ctx


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


class VoiceChangeChain(FakeSendChain):
    """模拟 SnowLuma 型适配器：Send 链上挂需 character+text 的 AI 变声接口（不是 TTS）。"""

    async def AIRecord(self, character, text):
        self.calls.append(("AIRecord", (character, text), {}))
        return {"status": "ok", "sent": "AIRecord"}


class GhostChain(FakeSendChain):
    """签名探测失败的保守路径：__signature__ 置 None 时 inspect.signature 返回 None（拿不到签名）。"""

    def __init__(self, sends=("Text", "Ghost")):
        super().__init__(sends=sends)

        async def ghost(content):
            return {"status": "ok", "sent": "Ghost"}

        ghost.__signature__ = None
        self.Ghost = ghost


def test_strip_fake_media_claims_variants():
    # 各种整行假声明形态：声明行剥掉，正文保留
    for line in ("（语音已发）", "语音已发！", "（声音已发送）", "[voice sent]",
                 "(audio sent)", "发出去啦~", "已发送。", "【语音已发】", "（已发）"):
        assert utils.strip_fake_media_claims(f"喵呜一声\n{line}\n正文继续") == "喵呜一声\n正文继续"


def test_strip_fake_media_claims_synthesis_variants():
    # 线上新增形态：语音合成类声明行（整行仅为声明才删）
    for line in ("（合成语音后发送）", "（语音合成后发送）", "合成语音中", "语音合成中！",
                 "（录好后再发）", "稍后语音发送。"):
        assert utils.strip_fake_media_claims(f"喵呜\n{line}\n正文") == "喵呜\n正文"


def test_strip_fake_media_claims_bare_label_lines():
    # 裸标签行（分段器把"标记+正文"切成孤行的 [语音]）：整行只有标记 → 删
    assert utils.strip_fake_media_claims("[语音]") == ""
    assert utils.strip_fake_media_claims("【voice】") == ""
    assert utils.strip_fake_media_claims("喵呜\n（语音）\n正文") == "喵呜\n正文"
    assert utils.strip_fake_media_claims("[声音]：\n喵呜") == "喵呜"
    # 行内带正文的不删（那是 strip_fake_media_prefix 的职责，claims 不越界）
    assert utils.strip_fake_media_claims("[语音] 喵？！") == "[语音] 喵？！"
    assert utils.strip_fake_media_claims("（语音）喵呜") == "（语音）喵呜"


def test_strip_fake_media_claims_claim_only_reply():
    # 整条回复只剩声明行：剥成空串（由调用方兜底成"无内容"文案）
    assert utils.strip_fake_media_claims("（语音已发）") == ""
    assert utils.strip_fake_media_claims("语音已发！\n（语音已发）") == ""


def test_strip_fake_media_claims_keeps_lines_with_content():
    # 行内带正文的不是整行声明，不能误删（封闭集锚定整行的意义所在）
    for keep in ("（语音已发）喵？！", "我想想啊（语音已发）", "语音已发送了消息给对方"):
        assert utils.strip_fake_media_claims(keep) == keep


def test_strip_fake_media_claims_normal_text_untouched():
    # 正常正文不受影响
    text = "今天天气不错。\n我发的是文字消息，不是语音。\n语音功能维护中，改天再发。"
    assert utils.strip_fake_media_claims(text) == text


def test_fake_media_composition_strip():
    # on_intermediate 的组合顺序：先剥整行假声明，再剥行首假标记
    text = utils.strip_fake_media_prefix(utils.strip_fake_media_claims("[语音] 喵？！"))
    assert text == "喵？！"
    text = utils.strip_fake_media_prefix(utils.strip_fake_media_claims("（语音已发）\n[语音] 喵呜"))
    assert text == "喵呜"


def test_strip_fake_media_prefix_all_media_tags():
    # 词表扩面：行首标记从语音系扩到表情包/图片/视频/文件系，一律剥标记留正文
    assert utils.strip_fake_media_prefix("[表情包] 喵呜！") == "喵呜！"
    assert utils.strip_fake_media_prefix("（图片）看看这个") == "看看这个"
    assert utils.strip_fake_media_prefix("【video】来了") == "来了"
    assert utils.strip_fake_media_prefix("[File] 报告内容") == "报告内容"
    assert utils.strip_fake_media_prefix("正常文本") == "正常文本"


def test_strip_fake_media_claims_all_media_labels_and_claims():
    # 裸标签行扩面：整行仅 [表情包]/（图片）/【video】等 → 删行
    assert utils.strip_fake_media_claims("[表情包]") == ""
    assert utils.strip_fake_media_claims("喵呜\n（图片）\n正文") == "喵呜\n正文"
    assert utils.strip_fake_media_claims("【video】") == ""
    assert utils.strip_fake_media_claims("[sticker]：\n喵呜") == "喵呜"
    # 声明行动词集合不变，媒介词可自由组合（表情包已发/图片已发送/[video sent]）
    assert utils.strip_fake_media_claims("表情包已发") == ""
    assert utils.strip_fake_media_claims("喵呜\n图片已发送。\n正文") == "喵呜\n正文"
    assert utils.strip_fake_media_claims("[video sent]") == ""
    assert utils.strip_fake_media_claims("（贴图已发）") == ""


def test_fake_media_red_line_normal_sentences():
    # 红线：带正文的普通句子（无括号标记结构）绝不误删——扩词表后也不得误伤
    for text in ("发你个表情包", "这个表情包太好笑了", "表情包见附件", "图片已经发到群里了",
                 "视频文件已发出去了吗？", "我想把这个文件发给你"):
        assert utils.strip_fake_media_prefix(text) == text
        assert utils.strip_fake_media_claims(text) == text


def test_collapse_spaces():
    # 去重规范化：只比内容不比排版（换行/空白差异不算新发言）
    assert utils.collapse_spaces("  喵呜\n\n 喵呜  ") == "喵呜 喵呜"
    assert utils.collapse_spaces("同一句话") == "同一句话"
    assert utils.collapse_spaces("") == ""


async def test_send_message_rejects_method_needing_extra_params():
    # 线上事故回归：method=AIRecord（腾讯 AI 变声接口，需 character+text）不是 TTS——
    # 应在发送前拦截并给出参数清单，不发送、不入待发队列
    chain = VoiceChangeChain(sends=("Text", "AIRecord"))
    main = FakeMain()
    main.sdk.adapter.add("snowluma", chain, sends=("Text", "AIRecord"))
    out = await erispulse.send_message(
        make_ctx(main), platform="snowluma", target_type="group", target_id="1",
        text="喵呜", method="AIRecord",
    )
    assert "character, text" in out
    assert "未发送" in out
    assert all(name != "AIRecord" for name, _, _ in chain.calls)
    assert not main.sdk.storage.get("QvQChat:pending_send:test:private:1")


async def test_send_message_single_text_method_still_sends():
    # 单文本方法（Text）不受防护影响，正常发送
    chain = FakeSendChain(sends=("Text",))
    main = FakeMain()
    main.sdk.adapter.add("onebot11", chain, sends=("Text",))
    out = await erispulse.send_message(
        make_ctx(main), platform="onebot11", target_type="user", target_id="1",
        text="hi", method="Text",
    )
    assert "Text" in [name for name, _, _ in chain.calls]
    assert "Text" in out


async def test_send_message_signature_probe_failure_passes_through():
    # 探测拿不到签名（内置函数）时保守放行，不拦截
    chain = GhostChain(sends=("Text", "Ghost"))
    main = FakeMain()
    main.sdk.adapter.add("onebot11", chain, sends=("Text", "Ghost"))
    out = await erispulse.send_message(
        make_ctx(main), platform="onebot11", target_type="user", target_id="1",
        text="hi", method="Ghost",
    )
    assert "Ghost" in out
    assert "需要额外参数" not in out


async def test_list_platforms_send_signatures():
    # sends 带签名：模型能看出哪些方法需要额外参数（FakeSendChain 的通用壳保持裸名）
    chain = VoiceChangeChain(sends=("Text", "AIRecord"))
    main = FakeMain()
    main.sdk.adapter.add("snowluma", chain, sends=("Text", "AIRecord"))
    out = await erispulse.list_platforms(make_ctx(main))
    assert '"platform": "snowluma"' in out
    assert "AIRecord(character, text)" in out


async def test_list_platforms_truncates_huge_send_lists():
    # 单平台方法很多时截断清单，防 token 爆炸
    main = FakeMain()
    sends = tuple(f"Method{'X' * 40}{i}" for i in range(80))
    main.sdk.adapter.add("bulk", FakeSendChain(sends=sends), sends=sends)
    out = await erispulse.list_platforms(make_ctx(main))
    assert "bulk" in out
    assert out.count("Method") <= 30


def _make_pipeline_main(**overrides):
    """复用 test_aggregate.make_main：绑定真实 Main 方法，驱动完整收件箱管线（含 on_intermediate）。"""
    from test_aggregate import make_main

    return make_main(**overrides)


async def _run_pipeline(main, prompt):
    ev = FakeChatEvent(text=prompt, group=True, group_id="1", user_id="u2", user_name="群主", at=True)
    await Main._on_message(main, ev)
    await asyncio.sleep(0.15)
    return ev


async def test_intermediate_speech_dedup_same_round():
    # 同回合去重：模型每轮工具重试都复述同一句话 → brief 档也只投一次（线上连发 3 遍回归）
    main = _make_pipeline_main(aggregate_window=0.05, tool_notice_mode="brief")

    class RepeatRunner:
        async def run(self, *, on_intermediate=None, **kwargs):
            if on_intermediate is not None:
                for _ in range(3):
                    result = on_intermediate("喵呜，我正在处理")
                    if asyncio.iscoroutine(result):
                        await result
            return type("R", (), {"text": "处理完了", "usage": {}, "tool_trace": [], "rounds": []})()

    main.runner = RepeatRunner()
    ev = await _run_pipeline(main, "帮我处理一下")
    hits = [r for r in ev.replies if "我正在处理" in str(r)]
    assert len(hits) == 1, ev.replies
    assert any("处理完了" in str(r) for r in ev.replies)


async def test_final_reply_duplicate_of_intermediate_skipped():
    # 双胞胎防护：最终回复与已投递阶段发言规范化后相同 → 最终条不再重复投递
    # （会话历史/回执时间照常走，只少发一条重复消息）
    main = _make_pipeline_main(aggregate_window=0.05, tool_notice_mode="brief")

    class TwinRunner:
        async def run(self, *, on_intermediate=None, **kwargs):
            if on_intermediate is not None:
                result = on_intermediate("喵呜")
                if asyncio.iscoroutine(result):
                    await result
            return type("R", (), {"text": "喵呜", "usage": {}, "tool_trace": [], "rounds": []})()

    main.runner = TwinRunner()
    ev = await _run_pipeline(main, "叫一声")
    hits = [r for r in ev.replies if "喵呜" in str(r)]
    assert len(hits) == 1, ev.replies
    assert main._last_reply_ts  # 跳过投递后管线照常收束（合并窗口起点已记录）


async def test_final_reply_distinct_from_intermediate_still_delivered():
    # 反向护栏：最终回复与阶段发言不同 → 照常投递，去重不误伤正常结论
    main = _make_pipeline_main(aggregate_window=0.05, tool_notice_mode="brief")

    class NormalRunner:
        async def run(self, *, on_intermediate=None, **kwargs):
            if on_intermediate is not None:
                result = on_intermediate("我先查一下")
                if asyncio.iscoroutine(result):
                    await result
            return type("R", (), {"text": "查到了：404", "usage": {}, "tool_trace": [], "rounds": []})()

    main.runner = NormalRunner()
    ev = await _run_pipeline(main, "查一下他的GitHub")
    assert any("我先查一下" in str(r) for r in ev.replies), ev.replies
    assert any("404" in str(r) for r in ev.replies), ev.replies
