### Changes in the 2024 version

- All API calls have been deleted and grouped in sfs.py, as we've discontinued most of the functionality

- The remaining functionalities are:

1. Database update

This is an unauthorized API call that needs to be restricted to local calls. Currently, it's not restricted and will be called every 5 minutes from crontab.

```
POST: http://localhost:8000/api/import-xml (without body)
```

2. User authorization

When a user first accesses the application, they need to log in. As we don't have user accounts here, they log in without any information.

```
GET: http://localhost:8000/api/authorize
```

This will return a JWT token that the mobile application needs to remember. All subsequent calls to the system must include this token for authorization.

3. Authorization check

```
GET: http://localhost:8000/api/me
```

This is an authorized call where the previously obtained token must be added in the Header.

The response is of the type:

```json
{
    "username": "e9363b95-8443-4375-b033-2bf36375bae8",
    "exp": 1791726787
}
```

The username is anonymous but will remain the same for this device.

Fetching conference data
```
GET http://localhost:8000/api/conference
```

This will return:

```json
{
    "last_updated": "2024-10-11 13:47:54.643012",
    "ratings": {
        "rates_by_session": {}
    }, 
    "bookmarks": [],
    "next_try_in_ms": 3000000,
    "conference": {
        ...
```

The content under the "conference" key is what should be displayed.

This content should be cross-referenced with avg_ratings.

Whenever we request the conference without the last_updated parameter, we'll get this.

The application should remember this parameter:

```
{
    "last_updated": "2024-10-11 13:47:54.643012",
}
```

And use it for the next call:

```
GET http://localhost:8000/api/conference?last_updated=2024-10-11%20%13:47:54.643012
```

If there have been no changes, the result will be different:

```json
{
  "last_updated": "2024-10-11 13:47:54.643012",
  "ratings": {
    "rates_by_session": {}
  },
  "bookmarks": [],
  "next_try_in_ms": 3000000,
  "conference": null
}
```

The conference content, which is usually a few hundred kilobytes, won't be sent, but the ratings will be.

The next_try_in_ms information represents a time below which the frontend shouldn't contact the backend for this call.

When next_try_in_ms milliseconds have elapsed, the frontend should make the call with the remembered last update.

If nothing has changed, the same response will be returned.

If something has changed, the conference will be full, and of course, the last_update will be modified and greater, and the frontend needs to remember this new value.

##### Rejtovanje sesije

za postojecu sesiju ulogovani korisnik moze da izvrsi ocenjivanje ili promenu svoje ocene

```
POST http://localhost:8000/api/sessions/ac0e9812-f704-4bc1-adbc-b0c0d3553bff/rate

BODY:
{
    "rating": 5
}
```

kao odgovor dobice trenutni ukupan rating te sesije zajedno sa brojem reteova

```
{
    "rating": 3.0,
    "total_rates": 15
}
```

##### Bookmarking

```
POST http://localhost:8000/api/sessions/c4b183d7-02d1-4b03-ac10-e85ca632dcb9/bookmarks/toggle
```

kao odgovor dobicete trenutni status tog bookmarka

```
{
    "bookmarked": true
}
```

##### odgovor u sesiji u vezi bookmarka i rating-a

ukoliko imate aktivan bookmark za sesiju ili sesija ima ocenu te informacije cete saznati u odgovoru /api/conference

```json
{
    "last_updated": "2024-10-11 15:41:09.349194",
    "ratings": {
        "rates_by_session": {
            "c4b183d7-02d1-4b03-ac10-e85ca632dcb9": [
                3.0,
                2
            ]
        }
    },
    "next_try_in_ms": 3000000,
    "bookmarks": [
        "c4b183d7-02d1-4b03-ac10-e85ca632dcb9"
    ],
    "conference": {
        "acronym": "sfscon-2024",
        "db": {
          ...
        }
      ...

```

u ratings se nalazi ocena po sesiji i moja ocena po sesiji

