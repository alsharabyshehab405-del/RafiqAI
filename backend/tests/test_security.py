def test_unauthorized(client):
 assert client.get('/conversations').status_code==401
 assert client.get('/tasks').status_code==401
def test_headers(client):
 r=client.get('/health');assert r.headers['x-content-type-options']=='nosniff';assert r.headers['x-frame-options']=='DENY'
