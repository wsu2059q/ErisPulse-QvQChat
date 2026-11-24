"""M6-8 storage_aupdate 键级 RMW：并发读改写不丢更新。"""
import asyncio

from fakes import FakeSDK

from QvQChat.utils import storage_aupdate


async def test_storage_aupdate_serializes_concurrent_writers():
    sdk = FakeSDK()
    key = "QvQChat:rmw-test"
    await sdk.storage.aset(key, [])

    def _append(entries):
        if not isinstance(entries, list):
            entries = []
        entries.append(1)
        return entries

    await asyncio.gather(*(storage_aupdate(sdk, key, _append, []) for _ in range(8)))

    result = await sdk.storage.aget(key, [])
    assert isinstance(result, list)
    # 8 个写者各追加 1 条：无锁 RMW 会互相覆盖只剩 1~8 条不等
    assert len(result) == 8


async def test_storage_aupdate_repairs_corrupt_shape():
    sdk = FakeSDK()
    key = "QvQChat:rmw-test-2"
    await sdk.storage.aset(key, "not-a-list")  # 存储值损坏（形状不对）

    def _append(entries):
        if not isinstance(entries, list):
            entries = []
        entries.append("x")
        return entries

    result = await storage_aupdate(sdk, key, _append, [])
    assert result == ["x"]


async def test_storage_aupdate_returns_new_value():
    sdk = FakeSDK()
    key = "QvQChat:rmw-test-3"

    def _bump(d):
        d = d if isinstance(d, dict) else {}
        d["n"] = int(d.get("n", 0) or 0) + 1
        return d

    out = await storage_aupdate(sdk, key, _bump, {})
    assert out == {"n": 1}
    assert await sdk.storage.aget(key, {}) == {"n": 1}
