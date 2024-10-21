from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "conferences_users_anonymous" ADD "push_notification_token" VARCHAR(64);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "conferences_users_anonymous" DROP COLUMN "push_notification_token";"""
