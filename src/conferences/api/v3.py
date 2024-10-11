# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2023 Digital CUBE <https://digitalcube.rs>

import os
import jwt
import uuid
import logging
import pydantic
import datetime

from fastapi import Depends
from typing import Optional
from fastapi import HTTPException

import shared.ex as ex
from app import get_app
import conferences.controller as controller
from conferences.controller import decode_token

app = get_app()

from fastapi import Request

log = logging.getLogger('conference_logger')


def pretix_order(request: Request):
    token = request.headers.get('Authorization', None)

    if not token:
        log.info("Raising UNAUTHORIZED")
        raise HTTPException(status_code=403, detail="UNAUTHORIZED")

    try:
        res = decode_token(token.replace('Bearer ', ''))
        log.info(f"Accessing with pretix_order: {res['pretix_order_id']}")
        return res
    except ex.AppException as e:
        log.critical(f"Raising {e.id_message}")
        raise HTTPException(status_code=e.status_code, detail=e.id_message)
    except Exception as e:

        log.info('Trying to decode admin token')
        try:
            res = decode_admin_token(token.replace('Bearer ', ''))
            if res['username'] == os.getenv('ADMIN_USERNAME'):
                res['pretix_order_id'] = '__admin__'
                res['pretix_order_secret'] = '__admin__'
                log.info(f"Accessing with admin token")
                return res

            if res['username'].startswith('lane'):
                res['pretix_order_id'] = res['username']
                res['pretix_order_secret'] = res['username']
                log.info(f"Accessing with lane token")
                return res
            raise Exception('Invalid lane user token')

        except Exception as e:
            log.critical(f"Raising INTERNAL_SERVER_ERROR {e}")
            raise HTTPException(status_code=500, detail='INTERNAL_SERVER_ERROR')


class ConferenceImportRequest(pydantic.BaseModel):
    default: Optional[bool] = True
    xml_content: Optional[str] = None


class ConferenceImportRequestResponse(pydantic.BaseModel):
    id: str
    created: bool
    changes: dict


@app.post('/api/v3/conferences/import-xml', response_model=ConferenceImportRequestResponse, )
async def V3CLONE_import_conference_xml_api():
    content = await controller.fetch_xml_content()
    XML_URL = os.getenv("XML_URL", None)

    # print("\n"*5)
    # print(content)
    # print("\n"*5)
    # print(XML_URL)
    # print("\n"*5)
    try:
        res = await controller.add_conference(content, XML_URL, force=True)
    except Exception as e:
        raise
    conference = res['conference']
    # print(conference)
    # print("\n"*5)

    x = ConferenceImportRequestResponse(id=str(conference.id), created=res['created'], changes=res['changes'])
    return x


@app.get('/api/v3/conferences/acronym/{acronym}', )
async def V3CLONE_get_conference_by_acronym(acronym: str):
    conference = await controller.get_conference_by_acronym(acronym=acronym)
    return {'id': conference.id}


@app.get('/api/v3/conferences/users')
async def v3_users_admin_old_link():
    return await controller.get_conference_attendees(conference_acronym='sfscon2023')


@app.get('/api/v3/conferences/{id_conference}', )
async def V3CLONE_get_single_conference(id_conference: uuid.UUID):
    return await controller.opencon_serialize(await controller.get_conference(id_conference=id_conference))


class PretixRegistrationRequest(pydantic.BaseModel):
    order: str
    pushToken: Optional[str] = None


@app.post('/api/v3/conferences/{id_conference}/pretix', )
async def V3CLONE_register_pretix_order(id_conference: uuid.UUID, request: PretixRegistrationRequest):
    conference = await controller.get_conference(id_conference=id_conference)
    try:
        return await controller.register_pretix_order(conference=conference,
                                                      order_code=request.order,
                                                      push_notification_token=request.pushToken,
                                                      registered_in_open_con_app=True
                                                      )
    except Exception as e:
        raise HTTPException(status_code=406, detail="PRETIX_ORDER_NOT_FOUND")


@app.get('/api/v3/tenants/code/{tenant_code}')
async def V3_GET_ID_TENANT():
    return {'id': uuid.uuid4()}


async def tenants_me(pretix_order):
    import conferences.models as models
    try:
        if 'username' in pretix_order:
            return {
                'id': uuid.uuid4(),
                "role_code": "ADMIN",
                'first_name': 'Admin',
                'last_name': 'Admin',
                'email': 'admin@opencon.dev',
                'data': {'organization': 'Admin', 'pretix_order': '__admin__'}
            }

        db_pretix_order = await models.PretixOrder.filter(id_pretix_order=pretix_order['pretix_order_id']).get_or_none()
        return {
            'id': db_pretix_order.id,
            'first_name': db_pretix_order.first_name,
            'last_name': db_pretix_order.last_name,
            'email': db_pretix_order.email,
            'data': {'organization': db_pretix_order.organization, 'pretix_order': pretix_order['pretix_order_id']}
        }
    except Exception as e:
        raise



@app.get('/api/v3/tenants/me')
async def V3_GET_ME_DEPRECATED(pretix_order=Depends(pretix_order)):
    return await tenants_me(pretix_order=pretix_order)


@app.post('/api/v3/conferences/sessions/{id_session}/toggle-bookmark')
async def v3_toggle_bookmark(id_session, pretix_order=Depends(pretix_order)):
    return await controller.toggle_bookmark_event_session(pretix_order_id=pretix_order['pretix_order_id'], event_session_id=id_session)


@app.get("/api/v3/conferences/{id_conference}/bookmarks")
async def get_my_bookmarks(id_conference: uuid.UUID, pretix_order=Depends(pretix_order)):
    return await controller.my_bookmarks(pretix_order_id=pretix_order['pretix_order_id'])


class RateEventRequest(pydantic.BaseModel):
    rate: int


@app.post('/api/v3/conferences/sessions/{id_session}/rate')
async def v3_rate_event(id_session: uuid.UUID, request: RateEventRequest, pretix_order=Depends(pretix_order)):
    return await controller.add_stars(pretix_order_id=pretix_order['pretix_order_id'], event_session_id=id_session, stars=request.rate)


@app.get('/api/v3/conferences/sessions/{id_session}/rate')
async def v3_rate_event(id_session: uuid.UUID, pretix_order=Depends(pretix_order)):
    return await controller.get_stars(pretix_order_id=pretix_order['pretix_order_id'], event_session_id=id_session)


def generate_admin_token(username):
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'secret')

    payload = {
        'username': username,
        'iat': datetime.datetime.utcnow(),
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=31),
    }
    encoded_jwt = jwt.encode(payload, JWT_SECRET_KEY, algorithm='HS256')

    return encoded_jwt


def decode_admin_token(token):
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'secret')

    decoded_payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=['HS256'])

    return decoded_payload


class LoginRequest(pydantic.BaseModel):
    username: str
    password: str


@app.post('/api/v3/tenants/{id_tenant}/sessions')
async def v3_login_admin(id_tenant: uuid.UUID, request: LoginRequest):
    if request.username != os.getenv('ADMIN_USERNAME'):
        raise HTTPException(status_code=403, detail="UNAUTHORIZED")
    if request.password != os.getenv('ADMIN_PASSWORD'):
        raise HTTPException(status_code=403, detail="UNAUTHORIZED")

    return {"token": generate_admin_token(request.username)}
