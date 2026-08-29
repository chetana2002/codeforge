"""Seeds a demo account with a couple of projects and files, so a fresh
`docker compose up` has something to look at immediately instead of an empty
dashboard.

Usage:
    python -m app.seed          # inside the api container, or with the venv active

Idempotent: re-running it when the demo user already exists is a no-op (it
prints the existing account's email and returns) rather than erroring or
creating duplicates.
"""

import asyncio

from sqlalchemy import select

from app.application.services.file_service import FileService
from app.application.services.project_service import ProjectService
from app.core.platform import ensure_windows_selector_event_loop
from app.core.security import hash_password
from app.domain.enums.file_type import FileType
from app.domain.enums.language import Language
from app.domain.models.user import User
from app.infrastructure.database.session import AsyncSessionLocal
from app.schemas.file import FileCreate
from app.schemas.project import ProjectCreate

DEMO_EMAIL = "demo@codeforge.dev"
DEMO_PASSWORD = "demo-password-123"

_PYTHON_SAMPLE = """\
def fibonacci(n: int) -> int:
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


if __name__ == "__main__":
    for i in range(10):
        print(f"fib({i}) = {fibonacci(i)}")
"""

_NODE_SAMPLE = """\
function isPrime(n) {
  if (n < 2) return false;
  for (let i = 2; i * i <= n; i++) {
    if (n % i === 0) return false;
  }
  return true;
}

const primes = Array.from({ length: 30 }, (_, i) => i + 1).filter(isPrime);
console.log("Primes up to 30:", primes.join(", "));
"""


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        existing = await db.scalar(select(User).where(User.email == DEMO_EMAIL))
        if existing is not None:
            print(f"Demo account already exists: {DEMO_EMAIL}")
            return

        user = User(email=DEMO_EMAIL, hashed_password=hash_password(DEMO_PASSWORD))
        db.add(user)
        await db.flush()
        await db.refresh(user)

        project_service = ProjectService(db)
        file_service = FileService(db)

        fib_project = await project_service.create(
            user.id,
            ProjectCreate(
                name="Fibonacci Sequence",
                description="A classic warm-up: the first ten Fibonacci numbers.",
                language=Language.PYTHON,
            ),
        )
        await file_service.create(
            fib_project.id,
            FileCreate(name="main.py", type=FileType.FILE, content=_PYTHON_SAMPLE),
        )

        primes_project = await project_service.create(
            user.id,
            ProjectCreate(
                name="Prime Finder",
                description="Finds every prime number up to 30.",
                language=Language.JAVASCRIPT,
            ),
        )
        await file_service.create(
            primes_project.id,
            FileCreate(name="main.js", type=FileType.FILE, content=_NODE_SAMPLE),
        )

        await db.commit()

        print("Seeded demo account:")
        print(f"  email:    {DEMO_EMAIL}")
        print(f"  password: {DEMO_PASSWORD}")
        print("  projects: Fibonacci Sequence (Python), Prime Finder (JavaScript)")


def main() -> None:
    ensure_windows_selector_event_loop()
    asyncio.run(seed())


if __name__ == "__main__":
    main()
