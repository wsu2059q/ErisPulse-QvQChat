import asyncio

from ErisPulse import sdk


async def main():
    async def late_http():
        await asyncio.sleep(5)
        try:
            from ErisPulse.Core.router import router

            await router.start(host="0.0.0.0", port=8010)
            print("[dev] HTTP stack on http://127.0.0.1:8010")
        except Exception as e:
            print("[dev] late http failed:", e)

    asyncio.get_running_loop().create_task(late_http())
    await sdk.run(keep_running=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
