from app.ingestion import chunk_pages, extract_pages
from app.storage import SQLiteStorage, _cosine


def test_extract_txt():
    assert extract_pages(b'hello world', 'sample.txt') == [(1, 'hello world')]


def test_chunking_preserves_page_and_overlap():
    pages = [(3, ' '.join(['business policy data'] * 130))]
    chunks = list(chunk_pages(pages, size=120, overlap=25))
    assert len(chunks) > 3
    assert all(c['page'] == 3 for c in chunks)
    assert all(len(c['content']) <= 120 for c in chunks)


def test_storage_crud_retrieval(tmp_path):
    store = SQLiteStorage(str(tmp_path / 'demo.db'))
    record = store.add('handbook.txt', [{'page':1,'index':0,'content':'Annual leave is twenty days per year.'}], [])
    assert store.list()[0]['chunks'] == 1
    results = store.search('annual leave', None)
    assert results[0]['filename'] == 'handbook.txt'
    assert results[0]['page'] == 1
    assert store.delete(record['id'])
    assert store.list() == []


def test_vector_scoring():
    assert round(_cosine([1,0], [1,0]), 3) == 1
    assert round(_cosine([1,0], [0,1]), 3) == 0


def test_reject_unsupported_file():
    try:
        extract_pages(b'hello', 'untrusted.exe')
    except ValueError as e:
        assert 'PDF and TXT' in str(e)
    else:
        assert False, 'Expected ValueError'
