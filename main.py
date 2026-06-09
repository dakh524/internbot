import asyncio
from bot.main import main

if __name__ == "__main__":
    # Python 3.10+ no longer auto-creates an event loop via get_event_loop().
    # Explicitly create and set one to ensure compatibility across all versions.
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    main()
