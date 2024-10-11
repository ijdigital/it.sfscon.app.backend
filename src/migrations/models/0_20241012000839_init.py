from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "conferences" (
    "id" UUID NOT NULL  PRIMARY KEY,
    "name" TEXT NOT NULL,
    "acronym" TEXT,
    "created" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "last_updated" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP,
    "source_uri" TEXT,
    "source_document_checksum" VARCHAR(128)
);
CREATE TABLE IF NOT EXISTS "conferences_lecturers" (
    "id" UUID NOT NULL  PRIMARY KEY,
    "slug" VARCHAR(255) NOT NULL,
    "external_id" VARCHAR(255) NOT NULL,
    "display_name" TEXT NOT NULL,
    "first_name" TEXT NOT NULL,
    "last_name" TEXT NOT NULL,
    "email" TEXT,
    "thumbnail_url" TEXT,
    "bio" TEXT,
    "organization" TEXT,
    "social_networks" JSONB,
    "conference_id" UUID NOT NULL REFERENCES "conferences" ("id") ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS "idx_conferences_slug_4860af" ON "conferences_lecturers" ("slug");
CREATE INDEX IF NOT EXISTS "idx_conferences_externa_b43bc9" ON "conferences_lecturers" ("external_id");
CREATE TABLE IF NOT EXISTS "conferences_locations" (
    "id" UUID NOT NULL  PRIMARY KEY,
    "name" TEXT NOT NULL,
    "slug" TEXT NOT NULL,
    "conference_id" UUID NOT NULL REFERENCES "conferences" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "conferences_rooms" (
    "id" UUID NOT NULL  PRIMARY KEY,
    "name" TEXT NOT NULL,
    "slug" TEXT NOT NULL,
    "conference_id" UUID NOT NULL REFERENCES "conferences" ("id") ON DELETE CASCADE,
    "location_id" UUID NOT NULL REFERENCES "conferences_locations" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "conferences_tracks" (
    "id" UUID NOT NULL  PRIMARY KEY,
    "name" TEXT NOT NULL,
    "slug" TEXT NOT NULL,
    "color" TEXT NOT NULL,
    "order" INT NOT NULL,
    "conference_id" UUID NOT NULL REFERENCES "conferences" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "conferences_event_sessions" (
    "id" UUID NOT NULL  PRIMARY KEY,
    "unique_id" VARCHAR(255) NOT NULL,
    "title" TEXT NOT NULL,
    "duration" INT,
    "abstract" TEXT,
    "description" TEXT,
    "bookmarkable" BOOL NOT NULL  DEFAULT True,
    "rateable" BOOL NOT NULL  DEFAULT True,
    "start_date" TIMESTAMPTZ NOT NULL,
    "end_date" TIMESTAMPTZ NOT NULL,
    "str_start_time" VARCHAR(20),
    "notification5min_sent" BOOL,
    "conference_id" UUID NOT NULL REFERENCES "conferences" ("id") ON DELETE CASCADE,
    "room_id" UUID NOT NULL REFERENCES "conferences_rooms" ("id") ON DELETE CASCADE,
    "track_id" UUID NOT NULL REFERENCES "conferences_tracks" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_conferences_unique__0ced27" UNIQUE ("unique_id", "conference_id")
);
CREATE TABLE IF NOT EXISTS "conferences_users_anonymous" (
    "id" UUID NOT NULL  PRIMARY KEY,
    "created" TIMESTAMPTZ NOT NULL  DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS "conferences_anonymous_bookmarks" (
    "id" UUID NOT NULL  PRIMARY KEY,
    "session_id" UUID NOT NULL REFERENCES "conferences_event_sessions" ("id") ON DELETE CASCADE,
    "user_id" UUID NOT NULL REFERENCES "conferences_users_anonymous" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_conferences_user_id_191340" UNIQUE ("user_id", "session_id")
);
CREATE TABLE IF NOT EXISTS "conferences_anonymous_rates" (
    "id" UUID NOT NULL  PRIMARY KEY,
    "rate" INT NOT NULL,
    "session_id" UUID NOT NULL REFERENCES "conferences_event_sessions" ("id") ON DELETE CASCADE,
    "user_id" UUID NOT NULL REFERENCES "conferences_users_anonymous" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_conferences_user_id_0acb26" UNIQUE ("user_id", "session_id")
);
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSONB NOT NULL
);
CREATE TABLE IF NOT EXISTS "conferences_lecturers_conferences_event_sessions" (
    "conferences_lecturers_id" UUID NOT NULL REFERENCES "conferences_lecturers" ("id") ON DELETE CASCADE,
    "eventsession_id" UUID NOT NULL REFERENCES "conferences_event_sessions" ("id") ON DELETE CASCADE
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """
