from collections.abc import AsyncIterator

from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from src.infrastructure.config import AppConfig
from src.infrastructure.database.base import create_engine, create_session_factory
from src.infrastructure.database.uow import SQLAlchemyUoW


class DatabaseProvider(Provider):
    @provide(scope=Scope.APP)
    async def get_engine(self, config: AppConfig) -> AsyncEngine:
        return create_engine(config.database.url)

    @provide(scope=Scope.REQUEST)
    async def get_session(self, engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
        factory = create_session_factory(engine)
        async with factory() as session:
            yield session

    @provide(scope=Scope.REQUEST)
    def get_uow(self, session: AsyncSession) -> SQLAlchemyUoW:
        return SQLAlchemyUoW(session)
