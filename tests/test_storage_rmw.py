"""M6-8 storage_update 键级 RMW：并发读改写不丢更新。"""
import threading

from fakes import FakeSDK

from QvQChat.utils import storage_update


def test_storage_update_serializes_concurrent_writers():
    sdk = FakeSDK()
    key = "QvQChat:rmw-test"
    sdk.storage.set(key, [])

    barrier = threading.Barrier(8)

    def worker():
        barrier.wait()

        def _append(entries):
            if not isinstance(entries, list):
                entries = []
            entries.append(1)
            return entries

        storage_update(sdk, key, _append, [])

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    result = sdk.storage.get(key, [])
    assert isinstance(result, list)
    # 8 个写者各追加 1 条：无锁 RMW 会互相覆盖只剩 1~8 条不等
    assert len(result) == 8


def test_storage_update_repairs_corrupt_shape():
    sdk = FakeSDK()
    key = "QvQChat:rmw-test-2"
    sdk.storage.set(key, "not-a-list")  # 存储值损坏（形状不对）

    def _append(entries):
        if not isinstance(entries, list):
            entries = []
        entries.append("x")
        return entries

    result = storage_update(sdk, key, _append, [])
    assert result == ["x"]


def test_storage_update_returns_new_value():
    sdk = FakeSDK()
    key = "QvQChat:rmw-test-3"

    def _bump(d):
        d = d if isinstance(d, dict) else {}
        d["n"] = int(d.get("n", 0) or 0) + 1
        return d

    out = storage_update(sdk, key, _bump, {})
    assert out == {"n": 1}
    assert sdk.storage.get(key, {}) == {"n": 1}
