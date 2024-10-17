# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2023 Digital CUBE <https://digitalcube.rs>

import os
import pprint
import unittest
import uuid
import json

import dotenv
import logging
from httpx import AsyncClient
from base_test_classes import BaseAPITest

os.environ["TEST_MODE"] = "true"

dotenv.load_dotenv()

logging.disable(logging.CRITICAL)


def get_local_xml_content():
    try:
        with open(f'{os.path.dirname(os.path.realpath(__file__))}/assets/sfscon2024.xml', 'r') as f:
            return f.read()
    except Exception as e:
        raise


class TestAPIBasic(BaseAPITest):

    async def setup(self):
        self.import_modules(['src.conferences.api'])

    async def test_get_conference_as_non_authorized_user_expect_401(self):
        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            response = await ac.get("/api/conference")
        assert response.status_code == 401

    async def test_authorize_user_and_get_conference_expect_404(self):
        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            response = await ac.get("/api/authorize")
            assert response.status_code == 200
            token = response.json()['token']

            response = await ac.get("/api/conference", headers={"Authorization": f"Bearer {token}"})
            assert response.status_code == 404

    async def test_import_xml(self):
        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            response = await ac.post("/api/import-xml") #, json={'use_local_xml': False})
            assert response.status_code == 200


    async def test_import_xml_mockuped_result(self):
        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            response = await ac.post("/api/import-xml", json={'use_local_xml': True})
            assert response.status_code == 200

    async def test_add_conference_authorize_user_and_get_conference_expect_200(self):
        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            response = await ac.post("/api/import-xml", json={'use_local_xml': True})
            assert response.status_code == 200

            response = await ac.get("/api/authorize")
            assert response.status_code == 200
            token = response.json()['token']

            response = await ac.get("/api/conference", headers={"Authorization": f"Bearer {token}"})
            assert response.status_code == 200



class Test2024(BaseAPITest):

    async def setup(self):
        self.import_modules(['src.conferences.api'])

        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            response = await ac.post("/api/import-xml", json={'use_local_xml': True})
            assert response.status_code == 200

            response = await ac.get("/api/authorize")
            assert response.status_code == 200
            self.token = response.json()['token']

            response = await ac.get("/api/authorize")
            assert response.status_code == 200
            self.token2 = response.json()['token']

            response = await ac.get("/api/authorize")
            assert response.status_code == 200
            self.token3 = response.json()['token']

        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            response = await ac.get("/api/conference", headers={"Authorization": f"Bearer {self.token}"})
            assert response.status_code == 200
            self.last_updated = response.json()['last_updated']

            self.sessions = response.json()['conference']['db']['sessions']

    async def test_get_conference(self):
        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            response = await ac.get("/api/conference", headers={"Authorization": f"Bearer {self.token}"})
            assert response.status_code == 200

        r = response.json()
        assert 'conference' in r
        assert 'acronym' in r['conference']
        assert r['conference']['acronym'] == 'sfscon-2024'

    async def test_get_conference_with_last_updated_time(self):
        # inicijalno uzimamo konferenciju bez last updated time

        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            response = await ac.get("/api/conference", headers={"Authorization": f"Bearer {self.token}"})
            assert response.status_code == 200

        r = response.json()
        assert 'conference' in r and r['conference']

        # uzimamo last updated time
        last_updated = r['last_updated']

        # sledeci put pozivamo get conferencije za tim vremenom

        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            response = await ac.get(f"/api/conference?last_updated={last_updated}", headers={"Authorization": f"Bearer {self.token}"})
            assert response.status_code == 200

        r = response.json()

        # i sada za razliku od prethodnog puta imacemo raznu konferenciju jer nema izmena
        # od strane organizatora, medjutim ostali parametri su bitni kao sto su
        # bookmarci i rateovi

        assert 'conference' in r and not r['conference']

    async def test_bookmarks(self):
        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            response = await ac.get(f"/api/conference?last_updated={self.last_updated}", headers={"Authorization": f"Bearer {self.token}"})
            assert response.status_code == 200

            res = response.json()

            assert 'bookmarks' in res
            assert res['bookmarks'] == []

            id_1st_session = list(self.sessions.keys())[0]
            response = await ac.post(f"/api/sessions/{id_1st_session}/bookmarks/toggle", headers={"Authorization": f"Bearer {self.token}"})
            assert response.status_code == 200
            assert response.json() == {'bookmarked': True}

            response = await ac.get(f"/api/conference?last_updated={self.last_updated}", headers={"Authorization": f"Bearer {self.token}"})
            assert response.status_code == 200

            res = response.json()

            assert 'bookmarks' in res
            assert res['bookmarks'] == [id_1st_session]

            response = await ac.post(f"/api/sessions/{id_1st_session}/bookmarks/toggle", headers={"Authorization": f"Bearer {self.token}"})
            assert response.status_code == 200

            assert response.json() == {'bookmarked': False}
            response = await ac.get(f"/api/conference?last_updated={self.last_updated}", headers={"Authorization": f"Bearer {self.token}"})
            assert response.status_code == 200

            res = response.json()

            assert 'bookmarks' in res
            assert res['bookmarks'] == []

    async def test_rating(self):
        # ...
        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            response = await ac.get(f"/api/conference?last_updated={self.last_updated}", headers={"Authorization": f"Bearer {self.token}"})
            assert response.status_code == 200

            res = response.json()

            assert 'ratings' in res
            assert res['ratings'] == {'my_rate_by_session': {}, 'rates_by_session': {}}

            id_1st_session = list(self.sessions.keys())[0]

            response = await ac.post(f"/api/sessions/{id_1st_session}/rate", json={'rating': 5}, headers={"Authorization": f"Bearer {self.token}"})

            assert response.status_code == 200
            assert response.json() == {'avg_rate': 5, 'total_rates': 1}

            # ako isti korisnik glasa ponovo desice se samo da se azurira ocena

            response = await ac.post(f"/api/sessions/{id_1st_session}/rate", json={'rating': 2}, headers={"Authorization": f"Bearer {self.token}"})

            assert response.status_code == 200
            assert response.json() == {'avg_rate': 2, 'total_rates': 1}

            # ocenu takodje mozemo proveriti uzimanjem konferencije

            response = await ac.get(f"/api/conference?last_updated={self.last_updated}", headers={"Authorization": f"Bearer {self.token}"})
            assert response.status_code == 200

            res = response.json()

            assert 'ratings' in res
            assert res['ratings'] == {'rates_by_session': {id_1st_session: [2.0, 1]}, 'my_rate_by_session': {id_1st_session: 2}}

            # uvecemo drugog korisnika da glasa

            response = await ac.post(f"/api/sessions/{id_1st_session}/rate", json={'rating': 5}, headers={"Authorization": f"Bearer {self.token2}"})

            assert response.status_code == 200
            assert response.json() == {'avg_rate': (2 + 5) / 2, 'total_rates': 2}

            # glasace sada i treci korisnik

            response = await ac.post(f"/api/sessions/{id_1st_session}/rate", json={'rating': 5}, headers={"Authorization": f"Bearer {self.token3}"})

            assert response.status_code == 200
            assert response.json() == {'avg_rate': (2 + 5 + 5) / 3, 'total_rates': 3}

            # ocenu takodje mozemo proveriti uzimanjem konferencije

            response = await ac.get(f"/api/conference?last_updated={self.last_updated}", headers={"Authorization": f"Bearer {self.token}"})
            assert response.status_code == 200

            res = response.json()

            assert 'ratings' in res
            assert res['ratings'] == {'my_rate_by_session': {id_1st_session: 2},
                                      'rates_by_session': {id_1st_session: [4.0,
                                                                            3]}}

            # dodacemo i glasanje za drugu sesiju

            id_2nd_session = list(self.sessions.keys())[1]

            response = await ac.post(f"/api/sessions/{id_2nd_session}/rate", json={'rating': 1}, headers={"Authorization": f"Bearer {self.token3}"})

            assert response.status_code == 200
            assert response.json() == {'avg_rate': 1, 'total_rates': 1}

            response = await ac.get(f"/api/conference?last_updated={self.last_updated}", headers={"Authorization": f"Bearer {self.token3}"})
            assert response.status_code == 200

            res = response.json()

            assert 'ratings' in res
            assert res['ratings']['rates_by_session'] == {id_1st_session: [4.0, 3],
                                                          id_2nd_session: [1.0, 1]}

            assert res['ratings']['my_rate_by_session'] == {id_1st_session: 5, id_2nd_session: 1}

            # ukoliko drugi user zahteva isto dobice iste rate ali my rate ce biti razlicit

            response = await ac.get(f"/api/conference?last_updated={self.last_updated}", headers={"Authorization": f"Bearer {self.token}"})
            assert response.status_code == 200

            res = response.json()
            assert 'ratings' in res
            assert res['ratings']['rates_by_session'] == {id_1st_session: [4.0, 3],
                                                          id_2nd_session: [1.0, 1]}

            assert res['ratings']['my_rate_by_session'] == {id_1st_session: 2}

    async def test_abstract(self):

        nr_abstracts = 0
        for id_session in self.sessions:
            session = self.sessions[id_session]
            assert 'abstract' in session
            if session['abstract']:
                nr_abstracts += 1

        assert nr_abstracts > 0
        print(nr_abstracts)

    async def test_title(self):

        for id_session in self.sessions:
            session = self.sessions[id_session]
            assert 'title' in session
            assert session['title']
            print(session['title'])

class TestJsonData(BaseAPITest):
    async def setup(self):

        current_file_path = os.path.dirname(os.path.realpath(__file__))
        with open(current_file_path + '/assets/sfs2024.10.14.json', 'r') as f:
            self.data = json.load(f)
        assert self.data

        assert 'day' in self.data
        self.sessions = []
        for day in self.data['day']:
            assert 'room' in day
            assert isinstance(day['room'], list)
            for room in day['room']:
                assert 'event' in room
                assert isinstance(room['event'], list) or isinstance(room['event'], dict)

                if isinstance(room['event'], list):
                    for event in room['event']:
                        self.sessions.append(event)
                else:
                    self.sessions.append(room['event'])

    async def test(self):
        ...
        unique_ids = set()
        print()
        print('-'*100)

        for session in self.sessions:
            if '@unique_id' not in session:
                print('NO UNQIUE_ID:', session['title'])
                continue
            if session['@unique_id'] in unique_ids:
                print('DUPLICATE:', session['title'])

            unique_ids.add(session['@unique_id'])

