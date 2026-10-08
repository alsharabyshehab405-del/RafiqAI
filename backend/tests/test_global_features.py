import uuid

def auth(client):
    r=client.post('/auth/register',json={'email':f'{uuid.uuid4().hex}@example.com','password':'password123'})
    return {'Authorization':'Bearer '+r.json()['access_token']}

def test_profile_search_sync_and_ownership(client):
    h=auth(client)
    p=client.get('/me',headers=h); assert p.status_code==200
    p=client.patch('/me',headers=h,json={'display_name':'Rafiq User','locale':'en'}); assert p.status_code==200 and p.json()['locale']=='en'
    c=client.post('/conversations',headers=h,json={'title':'Searchable'}).json(); cid=c['id']
    # AI call is isolated in the AI contract test; create a message directly through the database.
    from app.db import SessionLocal
    from app.models import Message
    with SessionLocal() as db:
        db.add(Message(conversation_id=cid,role='user',content='unique-search-term'))
        db.commit()
    assert client.get('/search',headers=h,params={'q':'unique-search-term'}).status_code==200
    assert client.get('/sync',headers=h).status_code==200

def test_refresh_logout_revokes(client):
    email=f'{uuid.uuid4().hex}@example.com'
    r=client.post('/auth/register',json={'email':email,'password':'password123'}); assert r.status_code==200
    token=r.json()['refresh_token']
    assert client.post('/auth/logout',json={'refresh_token':token}).status_code==200
    assert client.post('/auth/refresh',json={'refresh_token':token}).status_code==401
