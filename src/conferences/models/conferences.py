# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2023 Digital CUBE <https://digitalcube.rs>

import bs4

from typing import Dict
from tortoise.models import Model
from tortoise import fields


class UserAnonymous(Model):
    class Meta:
        table = "conferences_users_anonymous"

    id = fields.UUIDField(pk=True)
    created = fields.DatetimeField(auto_now_add=True)


class AnonymousBookmark(Model):
    class Meta:
        table = "conferences_anonymous_bookmarks"
        unique_together = (('user', 'session'),)

    id = fields.UUIDField(pk=True)
    user = fields.ForeignKeyField('models.UserAnonymous', related_name='bookmarks')
    session = fields.ForeignKeyField('models.EventSession', related_name='anonymous_bookmarks')


class AnonymousRate(Model):
    class Meta:
        table = "conferences_anonymous_rates"
        unique_together = (('user', 'session'),)

    id = fields.UUIDField(pk=True)
    user = fields.ForeignKeyField('models.UserAnonymous', related_name='rates')
    session = fields.ForeignKeyField('models.EventSession', related_name='anonymous_rates')

    rate = fields.IntField()


class Conference(Model):
    class Meta:
        table = "conferences"

    id = fields.UUIDField(pk=True)
    name = fields.TextField()
    # start_date = fields.DateField()
    # end_date = fields.DateField()
    acronym = fields.TextField(null=True)

    tracks = fields.ReverseRelation['Track']
    event_sessions = fields.ReverseRelation['EventSession']
    locations = fields.ReverseRelation['Location']

    created = fields.DatetimeField(auto_now_add=True)
    last_updated = fields.DatetimeField(auto_now=True)

    source_uri = fields.TextField(null=True)
    source_document_checksum = fields.CharField(max_length=128, null=True)

    def serialize(self):
        return {
            'id': str(self.id),
            'name': self.name,
            'acronym': self.acronym,
        }


class Track(Model):
    class Meta:
        table = "conferences_tracks"

    id = fields.UUIDField(pk=True)
    name = fields.TextField()
    slug = fields.TextField()
    color = fields.TextField()
    order = fields.IntField()
    conference = fields.ForeignKeyField('models.Conference', related_name='tracks')

    def serialize(self):
        return {'name': self.name,
                'color': self.color
                }


class Location(Model):
    class Meta:
        table = "conferences_locations"

    id = fields.UUIDField(pk=True)
    name = fields.TextField()
    slug = fields.TextField()
    conference = fields.ForeignKeyField('models.Conference', related_name='locations')

    def serialize(self):
        return {'name': self.name,
                'slug': self.slug}


class Room(Model):
    class Meta:
        table = "conferences_rooms"

    id = fields.UUIDField(pk=True)
    name = fields.TextField()
    slug = fields.TextField()
    conference = fields.ForeignKeyField('models.Conference', related_name='rooms')
    location = fields.ForeignKeyField('models.Location', related_name='rooms')

    def serialize(self):
        return {'name': self.name,
                'slug': self.slug,
                "location": str(self.location_id)
                }


class EventSession(Model):
    class Meta:
        table = "conferences_event_sessions"
        unique_together = (('unique_id', 'conference'),)
        ordering = ['start_date']

    id = fields.UUIDField(pk=True)
    unique_id = fields.CharField(max_length=255)
    title = fields.TextField()
    duration = fields.IntField(null=True)
    abstract = fields.TextField(null=True)
    description = fields.TextField(null=True)

    bookmarkable = fields.BooleanField(default=True)
    rateable = fields.BooleanField(default=True)

    start_date = fields.DatetimeField()
    end_date = fields.DatetimeField()

    str_start_time = fields.CharField(max_length=20, null=True)

    track = fields.ForeignKeyField('models.Track', related_name='event_sessions')
    room = fields.ForeignKeyField('models.Room', related_name='event_sessions')
    conference = fields.ForeignKeyField('models.Conference', related_name='event_sessions')
    lecturers = fields.ManyToManyRelation['ConferenceLecturer']
    bookmarks = fields.ReverseRelation['Bookmark']

    notification5min_sent = fields.BooleanField(default=None, null=True)

    def serialize(self, streaming_links: Dict[str, str] = None):
        # import tortoise.timezone

        return {
            'id': str(self.id),
            'unique_id': self.unique_id,
            'share_link': "https://sfscon.it",
            "date": self.start_date.strftime("%Y-%m-%d"),
            "start": self.start_date.strftime("%Y-%m-%d %H:%M:%S"),
            "duration": self.duration,
            "title": self.title,
            "abstract": None,
            "description": self.description,
            "bookmarkable": self.bookmarkable,
            "can_share": True,
            "can_ask_question": True,
            "rateable": self.rateable,
            "id_track": str(self.track_id),
            "id_room": str(self.room_id),
            "id_location": "TODO",
            "id_lecturers": [str(l.id) for l in self.lecturers],
            "stream_link": streaming_links[self.track.name] if streaming_links and self.track and self.track.name in streaming_links else None
        }


class ConferenceLecturer(Model):
    class Meta:
        table = "conferences_lecturers"

    id = fields.UUIDField(pk=True)
    slug = fields.CharField(max_length=255, null=False, index=True)
    external_id = fields.CharField(max_length=255, index=True)
    display_name = fields.TextField()
    first_name = fields.TextField()
    last_name = fields.TextField()
    email = fields.TextField(null=True)
    thumbnail_url = fields.TextField(null=True)
    bio = fields.TextField(null=True)
    organization = fields.TextField(null=True)
    social_networks = fields.JSONField(null=True)
    conference = fields.ForeignKeyField('models.Conference', related_name='lecturers')
    event_sessions = fields.ManyToManyField('models.EventSession', related_name='lecturers')

    @staticmethod
    def fix_bio(bio):
        if not bio:
            return ''

        bio = bio.replace("\\r\\n", "\n")
        bio = bio.encode().decode('unicode_escape')  # PRESERVE unicode

        soup = bs4.BeautifulSoup(bio, features="html.parser")
        bio = soup.get_text()
        bio = bio.strip('"')
        bio = bio.replace('\n', '<p>')
        bio = bio.replace('<\\/p>', '')

        return bio

    def serialize(self):
        return {
            "id": str(self.id),
            "share_link": f"https://www.sfscon.it/speakers/{self.slug}/",
            "company_name": self.organization,
            "display_name": self.display_name,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "profile_picture": self.thumbnail_url,
            "bio": self.bio,
            "social_networks": self.social_networks,
            "sessions": [str(s.id) for s in self.event_sessions] if self.event_sessions else []}


# class PretixOrder(Model):
#     class Meta:
#         table = "conferences_pretix_orders"
#         unique_together = (('id_pretix_order', 'conference'),)
#
#     id = fields.UUIDField(pk=True)
#     conference = fields.ForeignKeyField('models.Conference')
#     id_pretix_order = fields.CharField(max_length=32, index=True)
#
#     first_name = fields.CharField(max_length=255, null=True, index=True)
#     last_name = fields.CharField(max_length=255, null=True, index=True)
#     organization = fields.CharField(max_length=255, null=True, index=True)
#     email = fields.CharField(max_length=255, null=True, index=True)
#     secret = fields.TextField()
#     secret_per_sub_event = fields.JSONField(null=True)
#
#     push_notification_token = fields.CharField(max_length=64, null=True)
#
#     registered_in_open_con_app = fields.BooleanField(default=None, null=True)
#
#     registered_from_device_type = fields.CharField(max_length=32, null=True, index=True)
#
#     nr_printed_labels = fields.IntField(default=0)
#
#     created = fields.DatetimeField(auto_now_add=True, null=True)
#
#     def __str__(self):
#         return f"{self.first_name} {self.last_name} <{self.email}> ({self.organization})"
#
#     def serialize(self):
#         return {'first_name': self.first_name,
#                 'last_name': self.last_name,
#                 'organization': self.organization,
#                 'email': self.email,
#                 'pretix_order': self.id_pretix_order,
#                 'has_app': self.registered_in_open_con_app or self.registered_from_device_type is not None}
#
#
# class Bookmark(Model):
#     class Meta:
#         table = "conferences_bookmarks"
#         unique_together = (('pretix_order', 'event_session'),)
#
#     id = fields.UUIDField(pk=True)
#     pretix_order = fields.ForeignKeyField('models.PretixOrder')
#     event_session = fields.ForeignKeyField('models.EventSession', related_name='bookmarks')
#     created = fields.DatetimeField(auto_now_add=True)
#
#
# class StarredSession(Model):
#     class Meta:
#         table = "conferences_starred_sessions"
#
#     id = fields.UUIDField(pk=True)
#     event_session = fields.OneToOneField('models.EventSession', related_name='starred_session', index=True)
#
#     nr_votes = fields.IntField()
#     total_stars = fields.IntField()
#     avg_stars = fields.DecimalField(max_digits=3, decimal_places=2)
#
#
# class Star(Model):
#     class Meta:
#         table = "conferences_stars"
#         unique_together = (('pretix_order', 'event_session'),)
#
#     id = fields.UUIDField(pk=True)
#     pretix_order = fields.ForeignKeyField('models.PretixOrder')
#     event_session = fields.ForeignKeyField('models.EventSession')
#     created = fields.DatetimeField(auto_now_add=True)
#     stars = fields.IntField()
#
#
# class PushNotificationQueue(Model):
#     class Meta:
#         table = "conferences_push_notification_queue"
#
#     id = fields.UUIDField(pk=True)
#     created = fields.DatetimeField(auto_now_add=True)
#     sent = fields.DatetimeField(null=True)
#
#     attempt = fields.IntField(default=0)
#     last_response = fields.TextField(null=True)
#
#     pretix_order = fields.ForeignKeyField('models.PretixOrder')
#
#     subject = fields.TextField()
#     message = fields.TextField()
#

class Entrance(Model):
    class Meta:
        table = "conferences_entrances"

    id = fields.UUIDField(pk=True)
    name = fields.TextField()
    conference = fields.ForeignKeyField('models.Conference')


# class PretixQRScan(Model):
#     class Meta:
#         table = "conferences_pretix_qr_scans"
#
#     id = fields.UUIDField(pk=True)
#     created = fields.DatetimeField(auto_now_add=True)
#
#     pretix_secret = fields.TextField()
#     pretix_order = fields.ForeignKeyField('models.PretixOrder', null=True)
#
#     label_print_confirmed = fields.BooleanField(default=False)
#     label_printed = fields.DatetimeField(default=None, null=True)
#
#
# class Flow(Model):
#     class Meta:
#         table = "conferences_flows"
#
#     id = fields.UUIDField(pk=True)
#     conference = fields.ForeignKeyField('models.Conference', null=True, index=True)
#
#     created = fields.DatetimeField(auto_now_add=True)
#
#     pretix_order = fields.ForeignKeyField('models.PretixOrder', null=True, index=True)
#
#     text = fields.TextField(null=True)
#     data = fields.JSONField(null=True)
#
#     def serialize(self):
#         return {
#             # 'id': str(self.id),
#             # 'conference': str(self.conference_id) if self.conference else None,
#             'created': self.created,
#             'pretix_order': str(self.pretix_order_id) if self.pretix_order else None,
#             'text': self.text,
#             # 'data': self.data
#         }
#