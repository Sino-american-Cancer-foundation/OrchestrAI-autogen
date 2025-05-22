from .server import run
import os
import asyncio


def main() -> None:
    os.system("notify-send 'Parseer server started'")
    asyncio.run(run())