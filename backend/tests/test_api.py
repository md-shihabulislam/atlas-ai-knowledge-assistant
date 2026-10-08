from pathlib import Path
from fastapi.testclient import TestClient
from app import config
from app.main import app


def test_end_to_end_offline(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'SQLITE_PATH', str(tmp_path / 'integration.db'))
    monkeypatch.setattr(config, 'DATABASE_URL', '')
    monkeypatch.setattr(config, 'API_KEY', '')
    sample = Path(__file__).parents[2] / 'sample_docs' / 'example_company_handbook.txt'
    with TestClient(app) as api:
        assert api.get('/api/health').status_code == 200
        uploaded = api.post('/api/documents', files={'file': ('handbook.txt', sample.read_bytes(), 'text/plain')})
        assert uploaded.status_code == 201, uploaded.text
        doc_id = uploaded.json()['id']
        assert len(api.get('/api/documents').json()['documents']) == 1
        result = api.post('/api/chat', json={'question': 'What is the annual leave policy?'})
        assert result.status_code == 200, result.text
        assert result.json()['mode'] == 'offline'
        assert result.json()['sources']
        assert '20 days' in ' '.join(s['content'] for s in result.json()['sources'])
        assert api.delete(f'/api/documents/{doc_id}').status_code == 200
        assert api.get('/api/documents').json()['documents'] == []
