# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2023 Digital CUBE <https://digitalcube.rs>
import jwt

import os
import uuid
import logging
import datetime
import pydantic

from typing import Optional
from fastapi import HTTPException

from app import get_app
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import conferences.controller as controller

app = get_app()

from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/sfs2024/authorize")

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
)

@app.get('/api/authorize')
async def create_authorization():

    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'secret')

    payload = {
        'username': str(uuid.uuid4()),
        'iat': datetime.datetime.utcnow(),
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=31),
    }

    encoded_jwt = jwt.encode(payload, JWT_SECRET_KEY, algorithm='HS256')

    return {'jwt': encoded_jwt}



@app.get('/api/conferences/sfs2024/me')
async def get_me(token: str = Depends(oauth2_scheme)):
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
    decoded = jwt.decode(token, JWT_SECRET_KEY, algorithms=['HS256'])
    return decoded
    

@app.get('/api/conferences', )
async def get_conferences():
    return await controller.get_all_conferences()


@app.get('/api/conferences-x/{id_conference}', )
async def get_single_conference(id_conference: uuid.UUID):
    return await controller.opencon_serialize(await controller.get_conference(id_conference=id_conference))


class ConferenceImportRequest(pydantic.BaseModel):
    default: Optional[bool] = True
    xml_content: Optional[str] = None
    force: Optional[bool] = False


class ConferenceImportRequestResponse(pydantic.BaseModel):
    id: str


@app.post('/api/conferences', response_model=ConferenceImportRequestResponse)
async def create_conference(request: ConferenceImportRequest):
    if request.default:
        content = await controller.fetch_xml_content()
        XML_URL = os.getenv("XML_URL", None)
    else:
        content = await controller.convert_xml_to_dict(request.xml_content)
        XML_URL = 'local-file'

    res = await controller.add_conference(content, XML_URL, force=True)

    rlog = logging.getLogger('redis_logger')
    if res['created']:
        rlog.info(f'Conference {res["conference"].id} created')
    elif res['changes']:
        rlog.info(f'Conference {res["conference"].id} updated')
    else:
        rlog.info(f'No need for update for conference {res["conference"].id} / nothing changed in XML file')

    conference = res['conference']
    x = ConferenceImportRequestResponse(id=str(conference.id))
    return x


@app.get('/api/conferences/acronym/{acronym}', )
async def get_conference_by_acronym(acronym: str):
    conference = await controller.get_conference_by_acronym(acronym=acronym)
    return {'id': conference.id}


@app.get('/api/conferences/health')
async def health_check():
    return {"health": True, 'service': 'conferences'}


@app.get('/api/conferences/{acronym}/get-csv')
async def getcsv(acronym: str):
    csv_file = await controller.get_csv(acronym)
    return FileResponse(csv_file, media_type='text/csv')


@app.get('/api/conferences/{acronym}/talks.csv')
async def getcsv(acronym: str):
    csv_file = await controller.get_csv_talks(acronym)
    return FileResponse(csv_file, media_type='text/csv')


@app.get('/api/conferences/{acronym}/attendees.csv')
async def getcsv(acronym: str):
    csv_file = await controller.get_csv_attendees(acronym)
    return FileResponse(csv_file, media_type='text/csv')


class ConferenceNotify5MinRequest(pydantic.BaseModel):
    now_time: Optional[datetime.datetime] = None
    test_only: Optional[bool] = True


@app.post('/api/conferences/{acronym}/notify-5-minutes-before-start')
async def notify_5_minutes_before_start(acronym: str, request: ConferenceNotify5MinRequest):
    try:
        conference = await controller.get_conference_by_acronym(acronym=acronym)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

    return await controller.send_notifications_5_minute_before_start(conference=conference, now_time=request.now_time, test_only=request.test_only)



