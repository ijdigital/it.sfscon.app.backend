from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "conferences_anonymous_rates" (
    "id" UUID NOT NULL  PRIMARY KEY,
    "rate" INT NOT NULL,
    "session_id" UUID NOT NULL REFERENCES "conferences_event_sessions" ("id") ON DELETE CASCADE,
    "user_id" UUID NOT NULL REFERENCES "conferences_users_anonymous" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_conferences_user_id_0acb26" UNIQUE ("user_id", "session_id")
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "conferences_anonymous_rates";"""
