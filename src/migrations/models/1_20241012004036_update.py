from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "conferences_entrances" (
    "id" UUID NOT NULL  PRIMARY KEY,
    "name" TEXT NOT NULL,
    "conference_id" UUID NOT NULL REFERENCES "conferences" ("id") ON DELETE CASCADE
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "conferences_entrances";"""
