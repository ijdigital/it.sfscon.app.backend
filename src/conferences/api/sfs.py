# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2023 Digital CUBE <https://digitalcube.rs>
import jwt
import os
import uuid
import datetime
import pydantic
from fastapi import Query

from typing import Optional, Union

from fastapi import HTTPException

from app import get_app
from fastapi.middleware.cors import CORSMiddleware
import conferences.controller as controller

app = get_app()

from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends


def verify_token(token):
    try:
        JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
        decoded = jwt.decode(token, JWT_SECRET_KEY, algorithms=['HS256'])
        return decoded
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid token")


class ConferenceImportRequestResponse(pydantic.BaseModel):
    id: str
    created: bool
    changes: dict


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/sfs2024/authorize")

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
)


@app.get('/api/authorize')
async def create_authorization():
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'secret')

    id_user = await controller.authorize_user()

    payload = {
        'id_user': id_user,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=2 * 365),
    }

    encoded_jwt = jwt.encode(payload, JWT_SECRET_KEY, algorithm='HS256')

    return {'token': encoded_jwt}


@app.get('/api/me')
async def get_me(token: str = Depends(oauth2_scheme)):
    return verify_token(token)


class ImportConferenceRequest(pydantic.BaseModel):
    # use_local_xml: Optional[Union[bool, None]] = False
    use_local_xml: Optional[bool] = False


@app.post('/api/import-xml', response_model=ConferenceImportRequestResponse, )
async def import_conference_xml_api(request: ImportConferenceRequest = None):
    if request is None:
        request = ImportConferenceRequest()

    content = await controller.fetch_xml_content(request.use_local_xml)
    XML_URL = os.getenv("XML_URL", None)

    try:
        res = await controller.add_conference(content, XML_URL, force=True)
    except Exception as e:
        raise
    conference = res['conference']

    return ConferenceImportRequestResponse(id=str(conference.id), created=res['created'], changes=res['changes'])


@app.get('/api/conference')
async def get_current_conference(last_updated: Optional[str] = Query(default=None), token: str = Depends(oauth2_scheme)):
    # return verify_token(token)

    decoded = verify_token(token)
    return await controller.opencon_serialize_anonymouse(decoded['id_user'], await controller.get_current_conference(), last_updated=last_updated)


class RateRequest(pydantic.BaseModel):
    rating: int


@app.post('/api/sessions/{id_session}/rate')
async def rate_session(id_session: uuid.UUID, request: RateRequest, token: str = Depends(oauth2_scheme)):
    decoded = verify_token(token)
    return await controller.rate_session(id_user=decoded['id_user'], id_session=id_session, rate=request.rating)


@app.post('/api/sessions/{id_session}/bookmarks/toggle')
async def toggle_bookmark_for_session(id_session: uuid.UUID, token: str = Depends(oauth2_scheme)):
    decoded = verify_token(token)
    return await controller.bookmark_session(id_user=decoded['id_user'], id_session=id_session)
