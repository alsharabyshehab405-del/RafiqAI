import uuid
def auth(client):
 r=client.post('/auth/register',json={'email':f'{uuid.uuid4().hex}@example.com','password':'password123'});return {'Authorization':'Bearer '+r.json()['access_token']}
def test_conversation_and_task_crud(client):
 h=auth(client);c=client.post('/conversations',headers=h,json={'title':'اختبار'});assert c.status_code==200;cid=c.json()['id'];assert client.patch(f'/conversations/{cid}',headers=h,json={'title':'جديد'}).json()['title']=='جديد';assert client.delete(f'/conversations/{cid}',headers=h).status_code==200
 t=client.post('/tasks',headers=h,json={'title':'مهمة'});assert t.status_code==200;tid=t.json()['id'];assert client.patch(f'/tasks/{tid}',headers=h,json={'completed':True}).json()['completed'] is True;assert client.delete(f'/tasks/{tid}',headers=h).status_code==200
