"""用量来源记账：origin 透传聚合（by_origin）与逐条流水（usageflow）截断。"""
import time

from fakes import FakeMain


async def test_by_origin_aggregated():
    """同日多来源记账：by_origin 按 origin 分桶累计 tokens/calls，日总量不重不漏。"""
    main = FakeMain()
    today = "QvQChat:usage:" + time.strftime("%Y-%m-%d")
    await main.record_usage("c:private:1", {"total_tokens": 100}, model="p:m", origin="chat")
    await main.record_usage("c:private:1", {"total_tokens": 50}, model="p:m", origin="task")
    await main.record_usage("sub:x", {"total_tokens": 30}, model="p:m", origin="subagent")
    data = main.sdk.storage.get(today)
    assert data["tokens"] == 180 and data["calls"] == 3
    assert data["by_origin"]["chat"] == {"tokens": 100, "calls": 1}
    assert data["by_origin"]["task"]["tokens"] == 50
    assert data["by_origin"]["subagent"]["tokens"] == 30


async def test_flow_records_and_truncates():
    """逐条流水带 origin/in/out；超过 usage_flow_limit 时丢最早并标 truncated。"""
    main = FakeMain(usage_flow_limit=3)
    for i in range(5):
        await main.record_usage("c:private:1", {"total_tokens": 10, "prompt_tokens": 8, "completion_tokens": 2},
                                model="p:m", origin="chat")
    flow = await main._usage_flow(1)
    assert len(flow) == 3, "流水应截断到上限"
    assert flow[0].get("truncated") is True, "截断行应带标记"
    assert flow[-1]["in"] == 8 and flow[-1]["out"] == 2
    assert all(f["origin"] == "chat" for f in flow)


async def test_one_shot_runs_record_usage():
    """persist=False 的一次性调用（定时任务/主动发言）也进用量：record_usage 直调路径。"""
    main = FakeMain()
    await main.record_usage("c:group:9", {"total_tokens": 25}, model="p:m", origin="proactive")
    today = "QvQChat:usage:" + time.strftime("%Y-%m-%d")
    data = main.sdk.storage.get(today)
    assert data["by_origin"]["proactive"]["tokens"] == 25
