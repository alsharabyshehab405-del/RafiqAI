import uuid
def test_register_login_refresh(client):
 email=f"{uuid.uuid4().hex}@example.com"
 r=client.post('/auth/register',json={'email':email,'password':'password123'});assert r.status_code==200;data=r.json();assert data['access_token'] and data['refresh_token']
 r=client.post('/auth/refresh',json={'refresh_token':data['refresh_token']});assert r.status_code==200;new=r.json();assert new['refresh_token']!=data['refresh_token']
 assert client.post('/auth/refresh',json={'refresh_token':data['refresh_token']}).status_code==401
