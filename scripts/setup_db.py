"""Run all SQL migrations in db/migrations/ in filename order."""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from src.db.connection import get_pool, close_pool

MIGRATIONS_DIR = pathlib.Path(__file__).parent.parent / "src" / "db" / "migrations"


async def main() -> None:
    pool = await get_pool()
    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not migration_files:
        print("No migration files found.")
        return

    async with pool.acquire() as conn:
        for path in migration_files:
            print(f"Applying {path.name} …")
            sql = path.read_text()
            await conn.execute(sql)
            print(f"  ✓ {path.name}")

    await close_pool()
    print("All migrations applied.")


if __name__ == "__main__":
    asyncio.run(main())
