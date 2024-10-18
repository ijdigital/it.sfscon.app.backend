# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2023 Digital CUBE <https://digitalcube.rs>
import re
import os
import csv
import yaml
import uuid
import json
import httpx
import random
import slugify
import logging
import datetime
import xmltodict
import tortoise.timezone

from fastapi import HTTPException, status

import shared.ex as ex
import conferences.models as models

log = logging.getLogger('conference_logger')
current_file_dir = os.path.dirname(os.path.abspath(__file__))

rlog = logging.getLogger('redis_logger')


async def db_add_conference(name, acronym, source_uri):
    try:
        conference = await models.Conference.create(name=name, acronym=acronym, source_uri=source_uri)
        await models.Location.create(name='Noi Tech Park', slug='noi', conference=conference, )

    except Exception as e:
        log.critical(f'Error adding conference {name} {acronym} {source_uri} :: {str(e)}')
        raise

    try:
        entrances = os.getenv("CHECKIN_LANES", None)
        if entrances:
            entrances = json.loads(entrances)

            for entrance in entrances:
                await models.Entrance.create(name=entrance, id=entrances[entrance], conference=conference, )

    except Exception as e:
        log.critical(f'Error parsing ENTRANCES :: {str(e)}')
        raise

    return conference


async def read_xml_file(fname='sfscon2023.xml'):
    with open(fname, 'r') as f:
        content = xmltodict.parse(f.read(), encoding='utf-8')
    return content['schedule']


async def db_add_or_update_tracks(conference, content_tracks):
    order = 0

    tracks_by_name = {}
    cvt = {'#text': 'name', '@color': 'color'}

    for track in content_tracks['track']:
        order += 1
        defaults = {'conference': conference, 'order': order, 'color': 'black'}

        # TODO: Remove this after Luka fix it in XML

        if track == 'Main track - Main track':
            track = 'Main track'

        if type(track) == str:
            defaults['name'] = track
        else:
            for k, v in track.items():
                if k in cvt:
                    defaults[cvt[k]] = v

        defaults['slug'] = slugify.slugify(defaults['name'])

        try:
            db_track = await models.Track.filter(conference=conference, name=defaults['name']).first()
            if not db_track:
                db_track = await models.Track.create(**defaults)
            else:
                await db_track.update_from_dict(defaults)

        except Exception as e:
            log.critical(f'Error adding track {defaults["name"]} :: {str(e)}')
            raise

        tracks_by_name[db_track.name] = db_track

    if 'SFSCON' not in tracks_by_name:
        db_track = await models.Track.filter(conference=conference, name='SFSCON').get_or_none()
        if not db_track:
            db_track = await models.Track.create(**{'conference': conference, 'order': -1, 'name': f'SFSCON', 'slug': f'sfscon', 'color': 'black'})

        tracks_by_name['SFSCON'] = db_track

    return tracks_by_name


async def convert_xml_to_dict(xml_text):
    content = xmltodict.parse(xml_text, encoding='utf-8')
    return content['schedule']


def remove_html(text):
    # return text

    if not text:
        return None


    for t in ('<br>', '<br/>', '<br />', '<p>', '</p>'):
        text = text.replace(t, '\n')

    for t in ('<b>', '<B>'):
        if t in text:
            text = text.replace(t, '|Text style=styles.bold|')

    for t in ('<em>', '<EM>'):
        if t in text:
            text = text.replace(t, '|Text style=styles.italic|')

    for t in ('</b>', '</B>', '<em>', '<EM>'):
        if t in text:
            text = text.replace(t, '|/Text|')


    # Define a regular expression pattern to match HTML tags
    pattern = re.compile('<.*?>')

    # Use the pattern to remove all HTML tags
    clean_text = re.sub(pattern, '', text)

    clean_text = clean_text.replace('|Text style=styles.bold|', '<Text style=styles.bold>')
    clean_text = clean_text.replace('|Text style=styles.italic|', '<Text style=styles.italic>')
    clean_text = clean_text.replace('|/Text|', '</Text>')
    # Remove any extra whitespace
    clean_text = ' '.join(clean_text.split())

    return clean_text


async def fetch_xml_content(use_local_xml=False):
    if use_local_xml:
        current_file_folder = os.path.dirname(os.path.realpath(__file__))
        if use_local_xml:
            with open(current_file_folder + '/../../tests/assets/sfscon2024.xml', 'r') as f:
                return await convert_xml_to_dict(f.read())

    XML_URL = os.getenv("XML_URL", None)

    if not XML_URL:
        raise ex.AppException('XML_URL_NOT_SET', 'XML_URL not set')

    async with httpx.AsyncClient() as client:
        try:
            res = await client.get(XML_URL)

            if res.status_code != 200:
                raise ex.AppException('ERROR_FETCHING_XML', XML_URL)

            # for debugging purposes
            with open('/tmp/last_saved_xml.xml', 'wt') as f:
                f.write(res.text)

            dict_content = await convert_xml_to_dict(res.text)
            with open('/tmp/last_saved_json.json', 'wt') as f:
                f.write(json.dumps(dict_content, ensure_ascii=False, indent=1))

            return dict_content
        except Exception as e:
            log.critical(f'Error fetching XML from {XML_URL} :: {str(e)}')
            raise


async def add_sessions(conference, content, tracks_by_name):
    db_location = await models.Location.filter(conference=conference, slug='noi').get_or_none()

    changes = {}

    await models.ConferenceLecturer.filter(conference=conference).delete()

    def get_or_raise(key, obj):

        if key == '@unique_id' and not '@unique_id' in obj:
            return None

        return obj[key]

        # # TODO: Ubi ovo kad srede unique  - id obrisi od 143-145 linije
        # if key == '@unique_id':
        #     # if key not in obj:
        #     return obj['@id']
        #
        # if key not in obj:
        #     raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE,
        #                         detail=f"{key.upper()}_NOT_FOUND")
        # return obj[key]

    # test for duplicated unique_id

    events_by_unique_id = {}

    all_uids = set()
    for day in content['day']:

        for room in day['room']:
            room_event = room['event']
            if type(room_event) == dict:
                room_event = [room_event]
            for event in room_event:
                if type(event) != dict:
                    continue
                unique_id = get_or_raise('@unique_id', event)
                if not unique_id:
                    continue

                if unique_id in all_uids:
                    continue

                all_uids.add(unique_id)

                if unique_id == '2023day1event5':
                    ...
                if unique_id in events_by_unique_id:
                    raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail=f"EVENT_UNIQUE_ID_ALREADY_EXISTS:{unique_id}")
                events_by_unique_id[unique_id] = unique_id

    all_uids = set()
    for day in content['day']:

        date = day.get('@date', None)
        if not date:
            raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE,
                                detail="DAY_DATE_NOT_VALID")

        room_by_name = {}

        for room in day['room']:

            room_name = room.get('@name', None)

            if not room_name:
                raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE,
                                    detail="ROOM_NAME_NOT_VALID")

            room_slug = slugify.slugify(room_name)

            db_room = await models.Room.filter(conference=conference,
                                               location=db_location,
                                               slug=room_slug).first()

            if not db_room:
                db_room = await models.Room.create(conference=conference,
                                                   location=db_location,
                                                   name=room_name, slug=room_slug)

            if db_room.name not in room_by_name:
                room_by_name[db_room.name] = db_room

            room_event = room['event']
            if type(room_event) == dict:
                room_event = [room_event]
            for event in room_event:

                # try:
                #     if event['@id'] == '654a0e4cbd1d807a6ed7109ee6dc4ddb16ef4048a852e':
                #         print("\nFIND FSFE\n")
                # except Exception as e:
                #     ...
                # else:
                #     ...
                # print(event['title'])

                if type(event) != dict:
                    continue
                unique_id = get_or_raise('@unique_id', event)
                if not unique_id:
                    continue

                if unique_id in all_uids:
                    continue

                all_uids.add(unique_id)

                title = get_or_raise('title', event)
                try:
                    url = get_or_raise('url', event)
                except Exception as e:
                    url = None

                slug = slugify.slugify(title)
                track_name = event.get('track', None)
                if type(track_name) == dict:
                    track_name = track_name['#text']

                # TODO: Remove this after Luka fix it in XML

                if track_name in ('SFSCON - Main track', 'Main track - Main track'):
                    track_name = 'SFSCON'  # 'Main track'

                track = tracks_by_name[track_name] if track_name and track_name in tracks_by_name else None
                # event_type = event.get('@type', None)
                event_start = event.get('start', None)
                description = event.get('description', None)
                abstract = event.get('abstract', None)

                no_bookmark = event.get('@no_bookmark', False)
                bookmarkable = not no_bookmark
                rateable = bookmarkable

                if not bookmarkable:
                    ...

                if event_start and len(event_start) == 5:
                    event_start = datetime.datetime(year=int(date[0:4]),
                                                    month=int(date[5:7]),
                                                    day=int(date[8:10]),
                                                    hour=int(event_start[0:2]),
                                                    minute=int(event_start[3:5]))
                else:
                    event_start = None

                event_duration = event.get('duration', None)
                if event_duration and len(event_duration) == 5:
                    event_duration = int(event_duration[0:2]) * 60 * 60 + int(event_duration[3:5]) * 60
                else:
                    event_duration = None

                try:
                    track_name = track.name
                    room_name = db_room.name

                    if room_name == 'Seminar 2':
                        event_start += datetime.timedelta(milliseconds=1)
                    if room_name == 'Seminar 3':
                        event_start += datetime.timedelta(milliseconds=2)
                    if room_name == 'Seminar 4':
                        event_start += datetime.timedelta(milliseconds=3)
                    if room_name.startswith('Auditorium'):
                        event_start += datetime.timedelta(milliseconds=4)

                    db_event = await models.EventSession.filter(conference=conference, unique_id=unique_id).first()
                    # print("db_event", db_event)
                    if unique_id == '2023day1event5':
                        ...

                    str_start_time = event_start.strftime('%Y-%m-%d %H:%M:%S') if event_start else None

                    if not db_event:
                        db_event = await models.EventSession.create(conference=conference,
                                                                    title=title,
                                                                    url=url,
                                                                    abstract=abstract,
                                                                    description=remove_html(description),
                                                                    unique_id=unique_id,
                                                                    bookmarkable=bookmarkable,
                                                                    rateable=rateable,
                                                                    track=track,
                                                                    room=db_room,
                                                                    str_start_time=str_start_time,
                                                                    start_date=event_start,
                                                                    duration=event_duration,
                                                                    end_date=event_start + datetime.timedelta(seconds=event_duration) if event_start and event_duration else None,
                                                                    )

                        # await models.StarredSession.create(event_session=db_event,
                        #                                    nr_votes=0,
                        #                                    total_stars=0,
                        #                                    avg_stars=0)
                    else:

                        event_start = tortoise.timezone.make_aware(event_start)
                        if event_start != db_event.start_date:
                            changes[str(db_event.id)] = {'old_start_timestamp': db_event.start_date,
                                                         'new_start_timestamp': event_start}

                        await db_event.update_from_dict({'title': title, 'abstract': abstract,
                                                         'description': description,
                                                         'unique_id': unique_id,
                                                         'bookmarkable': bookmarkable,
                                                         'rateable': rateable,
                                                         'track': track,
                                                         'db_room': db_room,
                                                         'str_start_time': str_start_time,
                                                         'start_date': event_start,
                                                         'end_date': event_start + datetime.timedelta(seconds=event_duration) if event_start and event_duration else None})

                        await db_event.save()

                except Exception as e:
                    log.critical(f'Error adding event {title} :: {str(e)}')
                    raise

                persons = event.get('persons', [])

                if persons:
                    persons = persons['person']

                    if type(persons) == dict:
                        persons = [persons]

                    event_persons = []

                    for person in persons:

                        try:
                            db_person = await models.ConferenceLecturer.filter(conference=conference, external_id=person['@id']).get_or_none()
                        except Exception as e:
                            log.critical(f'Error adding person {person["#text"]} :: {str(e)}')
                            raise

                        display_name = person['#text']
                        # bio = person.get('@bio', None)

                        bio = models.ConferenceLecturer.fix_bio(person.get('@bio', None))

                        pid = person.get('@id', None)
                        organization = person.get('@organization', None)
                        thumbnail_url = person.get('@thumbnail', None)
                        first_name = display_name.split(' ')[0].capitalize()
                        last_name = ' '.join(display_name.split(' ')[1:]).capitalize()
                        social_networks = person.get('@socials', None)
                        social_networks = json.loads(social_networks) if social_networks else []

                        if not db_person:
                            try:
                                db_person = await models.ConferenceLecturer.create(conference=conference,
                                                                                   external_id=pid,
                                                                                   bio=remove_html(bio),
                                                                                   social_networks=social_networks,
                                                                                   first_name=first_name,
                                                                                   last_name=last_name,
                                                                                   display_name=display_name,
                                                                                   thumbnail_url=thumbnail_url,
                                                                                   slug=slugify.slugify(display_name),
                                                                                   organization=organization,
                                                                                   )
                            except Exception as e:
                                log.critical(f'Error adding person {person["#text"]} :: {str(e)}')
                                raise
                        else:
                            await db_person.update_from_dict({'bio': remove_html(bio),
                                                              'social_networks': social_networks,
                                                              'first_name': first_name,
                                                              'last_name': last_name,
                                                              'display_name': display_name,
                                                              'thumbnail_url': thumbnail_url,
                                                              'slug': slugify.slugify(display_name),
                                                              'organization': organization,
                                                              })

                            await db_person.save()

                        event_persons.append(db_person)

                    if event_persons:
                        await db_event.fetch_related('lecturers')
                        await db_event.lecturers.add(*event_persons)

    return changes


async def add_conference(content: dict, source_uri: str, force: bool = False):
    conference = await models.Conference.filter(source_uri=source_uri).get_or_none()

    created = False
    if not conference:
        created = True
        conference = await db_add_conference(content['conference']['title'],
                                             content['conference']['acronym'],
                                             source_uri=source_uri
                                             )

    import shared.utils as utils
    checksum = utils.calculate_md5_checksum_for_dict(content)

    if not force and conference.source_document_checksum == checksum:
        return {'conference': conference,
                'created': False,
                'changes': {},
                'checksum_matches': True,
                }
    else:
        conference.source_document_checksum = checksum
        await conference.save()

    content_tracks = content.get('tracks', [])

    tracks_by_name = await db_add_or_update_tracks(conference, content_tracks)
    try:
        changes = await add_sessions(conference, content, tracks_by_name)
    except Exception as e:
        raise

    if created:
        changes = {}

    changes_updated = None
    if changes:
        from conferences.controller import send_changes_to_bookmakers
        changes_updated = await send_changes_to_bookmakers(conference, changes, test=True)

    return {'conference': conference,
            'created': created,
            'checksum_matches': False,
            'changes': changes,
            'changes_updated': changes_updated
            }


async def get_conference_sessions(conference_acronym):
    conference = await models.Conference.filter(acronym=conference_acronym).get_or_none()
    if not conference:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="CONFERENCE_NOT_FOUND")

    conference = await get_conference(conference.id)
    serialized = await opencon_serialize(conference)

    sessions = []

    bookmark_per_event = {}
    for bpe in await models.Bookmark.filter(pretix_order__conference=conference).prefetch_related('pretix_order').all():
        if str(bpe.event_session_id) not in bookmark_per_event:
            bookmark_per_event[str(bpe.event_session_id)] = 0
        bookmark_per_event[str(bpe.event_session_id)] += 1

    rate_per_event = {}
    for rpe in await models.StarredSession.filter(event_session__conference=conference).prefetch_related('event_session').all():
        rate_per_event[str(rpe.event_session_id)] = rpe.total_stars / rpe.nr_votes if rpe.nr_votes else ' '

    for day in serialized['conference']['idx']['ordered_sessions_by_days']:
        for id_session in serialized['conference']['idx']['ordered_sessions_by_days'][day]:
            session = serialized['conference']['db']['sessions'][id_session]

            sessions.append({
                'event': session['title'],
                'speakers': ', '.join([serialized['conference']['db']['lecturers'][id_lecturer]['display_name'] for id_lecturer in session['id_lecturers']]),
                'date': session['date'],
                'bookmarks': bookmark_per_event[str(id_session)] if id_session in bookmark_per_event else 0,
                'rating': rate_per_event[str(id_session)] if str(id_session) in rate_per_event else ' '

                # 'bookmarks': random.randint(0, 100),
                # 'rating': round(random.randint(0, 500) / 100, 2)
            })

    return {'header': [
        {'name': 'Event', 'key': 'event', 'width': '100px'},
        {'name': 'Speakers', 'key': 'speakers', 'width': '100px'},
        {'name': 'Date', 'key': 'date', 'width': '100px'},
        {'name': 'Bookmarks', 'key': 'bookmarks', 'width': '100px'},
        {'name': 'Rating', 'key': 'rating', 'width': '100px'},
    ], 'data': sessions}


async def find_event_by_unique_id(conferece, unique_id):
    return await models.EventSession.filter(conference=conferece, unique_id=unique_id).get_or_none()


async def get_all_conferences():
    try:

        logger = logging.getLogger('redis_logger')
        logger.info('This is a test log message')

        x = [conference.serialize() for conference in await models.Conference.all()]
        return x
    except Exception as e:
        log.critical(f'Error getting all conferences :: {str(e)}')
        raise


async def get_pretix_order(conference: models.Conference, id_pretix_order: str):
    try:
        return await models.PretixOrder.filter(conference=conference, id_pretix_order=id_pretix_order).get_or_none()
    except Exception as e:
        log.critical(f'Error getting pretix order {id_pretix_order} :: {str(e)}')
        raise


async def get_current_conference():
    conference = await models.Conference.filter().prefetch_related('tracks',
                                                                   'locations',
                                                                   'event_sessions',
                                                                   'event_sessions__track',
                                                                   'event_sessions__room',
                                                                   # 'event_sessions__room__location',
                                                                   'event_sessions__lecturers',
                                                                   'rooms',
                                                                   # 'rooms__location',
                                                                   'lecturers',
                                                                   'lecturers__event_sessions',
                                                                   # 'event_sessions__starred_session',

                                                                   'event_sessions__anonymous_bookmarks',
                                                                   'event_sessions__anonymous_rates',

                                                                   ).order_by('-created').first()

    if not conference:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="CONFERENCE_NOT_FOUND")
    return conference


#
# async def get_conference(id_conference: uuid.UUID):
#     conference = await models.Conference.filter(id=id_conference).prefetch_related('tracks',
#                                                                                    'locations',
#                                                                                    'event_sessions',
#                                                                                    'event_sessions__track',
#                                                                                    'event_sessions__room',
#                                                                                    # 'event_sessions__room__location',
#                                                                                    'event_sessions__lecturers',
#                                                                                    'rooms',
#                                                                                    # 'rooms__location',
#                                                                                    'lecturers',
#                                                                                    'lecturers__event_sessions',
#                                                                                    # 'event_sessions__starred_session',
#
#                                                                                    'event_sessions__anonymous_bookmarks',
#                                                                                    'event_sessions__anonymous_rates',
#
#                                                                                    ).get_or_none()
#
#     return conference


async def authorize_user():
    anonymous = models.UserAnonymous()
    await anonymous.save()
    return str(anonymous.id)


async def bookmark_session(id_user, id_session):
    user = await models.UserAnonymous.filter(id=id_user).get_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="USER_NOT_FOUND")

    session = await models.EventSession.filter(id=id_session).get_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="SESSION_NOT_FOUND")

    try:
        current_bookmark = await models.AnonymousBookmark.filter(user=user, session=session).get_or_none()
    except Exception as e:
        raise

    if not current_bookmark:
        await models.AnonymousBookmark.create(user=user, session=session)
        return {'bookmarked': True}
    else:
        await current_bookmark.delete()
    return {'bookmarked': False}


async def rate_session(id_user, id_session, rate):
    if rate < 1 or rate > 5:
        raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE,
                            detail="RATE_NOT_VALID")

    user = await models.UserAnonymous.filter(id=id_user).get_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="USER_NOT_FOUND")

    session = await models.EventSession.filter(id=id_session).get_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="SESSION_NOT_FOUND")

    try:
        current_rate = await models.AnonymousRate.filter(user=user, session=session).get_or_none()
    except Exception as e:
        raise

    if not current_rate:
        await models.AnonymousRate.create(user=user, session=session, rate=rate)
    else:
        if current_rate.rate != rate:
            await current_rate.update_from_dict({'rate': rate})
            await current_rate.save()

    all_rates = await models.AnonymousRate.filter(session=session).all()
    avg_rate = sum([rate.rate for rate in all_rates]) / len(all_rates) if all_rates else 0

    return {'avg_rate': avg_rate,
            'total_rates': len(all_rates),
            }


async def opencon_serialize_anonymouse(user_id, conference, last_updated=None):
    next_try_in_ms = 3000000
    db_last_updated = str(tortoise.timezone.make_naive(conference.last_updated))

    conference_avg_rating = {'rates_by_session': {},
                             'my_rate_by_session': {}
                             }
    for session in conference.event_sessions:
        if session.anonymous_rates.related_objects:
            all_rates_for_session = [r.rate for r in session.anonymous_rates.related_objects]
            if all_rates_for_session:
                conference_avg_rating['rates_by_session'][str(session.id)] = [sum(all_rates_for_session) / len(all_rates_for_session),
                                                                              len(all_rates_for_session)]  # [session.anonymous_rates.avg_stars,
            # session.anonymous_rates.nr_votes]

    user = await models.UserAnonymous.filter(id=user_id).prefetch_related('bookmarks', 'rates').get_or_none()

    bookmarks = [bookmark.session_id for bookmark in user.bookmarks.related_objects]
    conference_avg_rating['my_rate_by_session'] = {str(rate.session_id): rate.rate for rate in user.rates.related_objects}

    if last_updated and last_updated >= db_last_updated:
        return {'last_updated': db_last_updated,
                'ratings': conference_avg_rating,
                'bookmarks': bookmarks,
                'next_try_in_ms': next_try_in_ms,
                'conference': None
                }

    db = {}
    idx = {}

    with open(current_file_dir + '/../../tests/assets/sfs2023streaming.yaml', 'r') as f:
        streaming_links = yaml.load(f, yaml.Loader)

    idx['ordered_sponsors'] = []

    db['tracks'] = {str(track.id): track.serialize() for track in conference.tracks}
    db['locations'] = {str(location.id): location.serialize() for location in conference.locations}
    db['rooms'] = {str(room.id): room.serialize() for room in conference.rooms}
    db['sessions'] = {str(session.id): session.serialize(streaming_links) for session in conference.event_sessions}
    db['lecturers'] = {str(lecturer.id): lecturer.serialize() for lecturer in conference.lecturers}
    db['sponsors'] = {}

    days = set()
    for s in db['sessions'].values():
        days.add(s['date'])

    idx['ordered_lecturers_by_display_name'] = [l['id'] for l in sorted(db['lecturers'].values(), key=lambda x: x['display_name'])]
    idx['ordered_sessions_by_days'] = {d: [s['id'] for s in db['sessions'].values() if s['date'] == d] for d in sorted(list(days))}
    idx['ordered_sessions_by_tracks'] = {t: [s['id'] for s in db['sessions'].values() if s['id_track'] == t] for t in db['tracks'].keys()}
    idx['days'] = sorted(list(days))

    # conference_avg_rating = {'rates_by_session': {}}
    # for session in conference.event_sessions:
    #     if session.starred_session and session.starred_session.nr_votes:
    #         conference_avg_rating['rates_by_session'][str(session.id)] = [session.starred_session.avg_stars,
    #                                                                       session.starred_session.nr_votes]

    with open(current_file_dir + '/../../tests/assets/sfscon2024sponsors.yaml', 'r') as f:
        db['sponsors'] = yaml.load(f, yaml.Loader)

    re_ordered_lecturers = {}
    for l in idx['ordered_lecturers_by_display_name']:
        re_ordered_lecturers[l] = db['lecturers'][l]

    db['lecturers'] = re_ordered_lecturers

    return {'last_updated': db_last_updated,
            'ratings': conference_avg_rating,
            'next_try_in_ms': next_try_in_ms,
            'bookmarks': bookmarks,
            'conference': {'acronym': str(conference.acronym),
                           'db': db,
                           'idx': idx
                           }
            }

# REMOVE
# async def opencon_serialize(conference, last_updated=None):
#     next_try_in_ms = 3000000
#     db_last_updated = str(tortoise.timezone.make_naive(conference.last_updated))
#
#     conference_avg_rating = {'rates_by_session': {}}
#     for session in conference.event_sessions:
#         if session.starred_session and session.starred_session.nr_votes:
#             conference_avg_rating['rates_by_session'][str(session.id)] = [session.starred_session.avg_stars,
#                                                                           session.starred_session.nr_votes]
#
#     if last_updated and last_updated >= db_last_updated:
#         return {'last_updated': db_last_updated,
#                 'conference_avg_rating': conference_avg_rating,
#                 'next_try_in_ms': next_try_in_ms,
#                 'conference': None
#                 }
#
#     db = {}
#     idx = {}
#
#     with open(current_file_dir + '/../../tests/assets/sfs2023streaming.yaml', 'r') as f:
#         streaming_links = yaml.load(f, yaml.Loader)
#
#     idx['ordered_sponsors'] = []
#
#     db['tracks'] = {str(track.id): track.serialize() for track in conference.tracks}
#     db['locations'] = {str(location.id): location.serialize() for location in conference.locations}
#     db['rooms'] = {str(room.id): room.serialize() for room in conference.rooms}
#     db['sessions'] = {str(session.id): session.serialize(streaming_links) for session in conference.event_sessions}
#     db['lecturers'] = {str(lecturer.id): lecturer.serialize() for lecturer in conference.lecturers}
#     db['sponsors'] = {}
#
#     days = set()
#     for s in db['sessions'].values():
#         days.add(s['date'])
#
#     idx['ordered_lecturers_by_display_name'] = [l['id'] for l in sorted(db['lecturers'].values(), key=lambda x: x['display_name'])]
#     idx['ordered_sessions_by_days'] = {d: [s['id'] for s in db['sessions'].values() if s['date'] == d] for d in sorted(list(days))}
#     idx['ordered_sessions_by_tracks'] = {t: [s['id'] for s in db['sessions'].values() if s['id_track'] == t] for t in db['tracks'].keys()}
#     idx['days'] = sorted(list(days))
#
#     # conference_avg_rating = {'rates_by_session': {}}
#     # for session in conference.event_sessions:
#     #     if session.starred_session and session.starred_session.nr_votes:
#     #         conference_avg_rating['rates_by_session'][str(session.id)] = [session.starred_session.avg_stars,
#     #                                                                       session.starred_session.nr_votes]
#
#     with open(current_file_dir + '/../../tests/assets/sfscon2023sponsors.yaml', 'r') as f:
#         db['sponsors'] = yaml.load(f, yaml.Loader)
#
#     re_ordered_lecturers = {}
#     for l in idx['ordered_lecturers_by_display_name']:
#         re_ordered_lecturers[l] = db['lecturers'][l]
#
#     db['lecturers'] = re_ordered_lecturers
#
#     return {'last_updated': db_last_updated,
#             'conference_avg_rating': conference_avg_rating,
#             'next_try_in_ms': next_try_in_ms,
#             'conference': {'acronym': str(conference.acronym),
#                            'db': db,
#                            'idx': idx
#                            }
#             }


# async def get_conference_by_acronym(acronym: str):
#     acronym = 'sfscon-2023'
#     return await models.Conference.filter(acronym=acronym).get_or_none()


# def now_timestamp():
#     return datetime.datetime.now()


# def sec2minutes(seconds):
#     mm = seconds // 60
#     ss = seconds % 60
#     return f'{mm}:{ss:02}'


# async def extract_all_session_event_which_starts_in_next_5_minutes(conference, now=None):
#     if not now:
#         try:
#             now_time = tortoise.timezone.make_aware(datetime.datetime.now())
#         except Exception as e:
#             raise
#
#     else:
#         now_time = now
#
#     sessions = await models.EventSession.filter(conference=conference,
#                                                 start_date__gte=now_time,
#                                                 start_date__lte=now_time + datetime.timedelta(minutes=5)).all()
#
#     to_notify_by_session_emails = {}
#     to_notify_by_session = {}
#     if sessions:
#         for session in sessions:
#             bookmarkers_to_notify = await models.Bookmark.filter(event_session=session,
#                                                                  pretix_order__push_notification_token__isnull=False).prefetch_related('pretix_order').all()
#
#             to_notify_by_session[str(session.id)] = [str(bookmark.pretix_order.id) for bookmark in bookmarkers_to_notify]
#             to_notify_by_session_emails[session.title] = {'start_at': str(session.start_date),
#                                                           'start_in': sec2minutes((session.start_date - now_time).seconds) + ' minutes',
#                                                           'to_notify': [bookmark.pretix_order.email for bookmark in bookmarkers_to_notify]}
#
#     return {'ids': to_notify_by_session,
#             'human_readable': to_notify_by_session_emails}


# async def get_csv_attendees(acronym: str):
#     tmp_file = f'/tmp/{uuid.uuid4()}.csv'
#
#     conference = await get_conference_by_acronym(acronym=acronym)
#     if not conference:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
#                             detail="CONFERENCE_NOT_FOUND")
#
#     attendees = await models.PretixOrder.filter(conference=conference,
#                                                 nr_printed_labels__gt=0
#                                                 ).order_by('first_name').all()
#
#     with open(tmp_file, 'wt') as f:
#
#         writer = csv.writer(f)
#         writer.writerow(['First Name', 'Last Name', 'Email', 'Organization', 'Pretix Order'])
#         for pretix_order in attendees:
#             writer.writerow([pretix_order.first_name,
#                              pretix_order.last_name,
#                              pretix_order.email,
#                              pretix_order.organization,
#                              pretix_order.id_pretix_order
#                              ])
#
#     return tmp_file


# async def get_csv_talks(acronym: str):
#     tmp_file = f'/tmp/{uuid.uuid4()}.csv'
#
#     conference = await get_conference_by_acronym(acronym=acronym)
#     if not conference:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
#                             detail="CONFERENCE_NOT_FOUND")
#
#     conference = await get_conference(conference.id)
#     serialized = await opencon_serialize(conference)
#
#     bookmark_per_event = {}
#     for bpe in await models.Bookmark.filter(pretix_order__conference=conference).prefetch_related('pretix_order').all():
#         if str(bpe.event_session_id) not in bookmark_per_event:
#             bookmark_per_event[str(bpe.event_session_id)] = 0
#         bookmark_per_event[str(bpe.event_session_id)] += 1
#
#     rate_per_event = {}
#     for rpe in await models.StarredSession.filter(event_session__conference=conference).prefetch_related('event_session').all():
#         rate_per_event[str(rpe.event_session_id)] = rpe.total_stars / rpe.nr_votes if rpe.nr_votes else ''
#
#     with open(tmp_file, 'wt') as f:
#
#         writer = csv.writer(f)
#         writer.writerow(['Event', 'Speakers', 'Date', 'Bookmarks', 'Rating'])
#         for day in serialized['conference']['idx']['ordered_sessions_by_days']:
#             for id_session in serialized['conference']['idx']['ordered_sessions_by_days'][day]:
#                 session = serialized['conference']['db']['sessions'][id_session]
#
#                 writer.writerow([session['title'],
#                                  ', '.join([serialized['conference']['db']['lecturers'][id_lecturer]['display_name'] for id_lecturer in session['id_lecturers']]),
#                                  session['date'],
#                                  bookmark_per_event[str(id_session)] if id_session in bookmark_per_event else 0,
#                                  rate_per_event[str(id_session)] if str(id_session) in rate_per_event else ''
#                                  # random.randint(0, 100),
#                                  # round(random.randint(0, 500) / 100, 2)
#                                  ])
#
#     return tmp_file


# async def add_flow(conference: models.Conference, pretix_order: models.PretixOrder, text: str, data: dict = None):
#     if not text and not data:
#         raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE,
#                             detail="TEXT_OR_DATA_MUST_BE_SET")
#
#     if not conference and pretix_order:
#         conference = pretix_order.conference
#
#     flow_id = uuid.uuid4()
#     await models.Flow.create(id=flow_id,
#                              conference=conference,
#                              pretix_order=pretix_order,
#                              text=text,
#                              data=data)
#
#     return {'id': flow_id}


# async def get_flows(conference: models.Conference, page: int, per_page: int, search: str):
#     offset = (page - 1) * per_page
#
#     query = models.Flow.filter(conference=conference).filter(text__icontains=search)
#
#     flows = await query.order_by('-created_at').offset(offset).limit(per_page).all()
#     count = await query.count()
#
#     summary = {
#         'page': page,
#         'per_page': per_page,
#         'total_count': count,
#         'total_pages': count // per_page + 1 if count % per_page else count // per_page,
#         'previous_page': page - 1 if page > 1 else None,
#         'next_page': page + 1 if page * per_page < count else None,
#     }
#
#     return {'summary': summary, 'items': [flow.serialize() for flow in flows],
#             'columns': [
#                 'created',
#                 'pretix_order',
#                 'text',
#             ]}


# async def get_dashboard(acronym: str):
#     conference = await get_conference_by_acronym(acronym=acronym)
#
#     organizations = set()
#     for pretix_order in await models.PretixOrder.filter(conference=conference).all():
#         if pretix_order.organization:
#             org = pretix_order.organization.strip().lower()
#             organizations.add(org)
#
#     registered_users = 'N/A'
#     async with httpx.AsyncClient() as client:
#         try:
#             PRETIX_ORGANIZER_ID = os.getenv('PRETIX_ORGANIZER_ID', None)
#             PRETIX_EVENT_ID = os.getenv('PRETIX_EVENT_ID', None)
#             PRETIX_CHECKLIST_ID = os.getenv('PRETIX_CHECKLIST_ID', None)
#             PRETIX_TOKEN = os.getenv('PRETIX_TOKEN', None)
#
#             url = f'https://pretix.eu/api/v1/organizers/{PRETIX_ORGANIZER_ID}/events/{PRETIX_EVENT_ID}/checkinlists/{PRETIX_CHECKLIST_ID}/status/'
#
#             log.debug('Creating get request to ' + url)
#
#             res = await client.get(url, headers={'Authorization': f'Token {PRETIX_TOKEN}'})
#             jres = res.json()
#
#             registered_users = jres['items'][0]['position_count'] + jres['items'][1]['position_count']
#             attendees = jres['items'][0]['checkin_count'] + jres['items'][1]['checkin_count']
#
#         except Exception as e:
#             log.critical(f'Error getting info from pretix')
#
#     from tortoise.queryset import Q
#
#     flt = Q(Q(conference=conference), Q(Q(registered_in_open_con_app=True), Q(registered_from_device_type__isnull=False), join_type='OR'), join_type='AND')
#
#     return [
#         {'name': 'Registered users', 'value': registered_users},
#         {'name': 'Attendees', 'value': attendees},
#         {'name': 'SFSCON app users', 'value': await models.PretixOrder.filter(flt).count()},
#         {'name': 'Organisations', 'value': len(organizations)},
#         {'name': 'Total bookmarks', 'value': await models.Bookmark.filter(event_session__conference=conference).prefetch_related('event_session').count()},
#         {'name': 'Ratings received', 'value': await models.Star.filter(event_session__conference=conference).prefetch_related('event_session').count()}
#     ]
