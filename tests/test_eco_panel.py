"""生态面板贡献（qvq_extensions.panel）：卡与动作收集、只读视图。"""
from QvQChat.bridge.ecosystem import EcosystemBridge

from fakes import FakeMain


async def test_panel_cards_and_actions_collected():
    """panel.cards/actions 收集：空标题卡与空动作被过滤，module 归属保留。"""
    main = FakeMain(catalog={"PanelMod": [{"name": "status", "signature": "()"}]})
    main.sdk.module.handlers[("PanelMod", "qvq_extensions")] = {
        "panel": {
            "cards": [{"title": "服务器状态", "text": "3 台在线"}, {"title": "", "text": "脏卡"}],
            "actions": [
                {"label": "打开监控", "kind": "url", "target": "https://example.com"},
                {"label": "去编排页", "kind": "page", "target": "orchestrate"},
                {"label": ""},
            ],
        }
    }
    bridge = EcosystemBridge(main)
    await bridge.refresh()
    panels = bridge.external_panel()
    assert len(panels) == 1
    p = panels[0]
    assert p["module"] == "PanelMod"
    assert [c["title"] for c in p["cards"]] == ["服务器状态"]
    assert [a["label"] for a in p["actions"]] == ["打开监控", "去编排页"]
