from pathlib import Path
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)
FIXTURES = Path(__file__).parent / 'fixtures'


def upload(name):
    return client.post('/extract-pdf', content=(FIXTURES / name).read_bytes(),
                       headers={'Content-Type': 'application/pdf'})


def test_table_cells_keep_rows_columns_and_page_reference():
    response = upload('table.pdf')
    assert response.status_code == 200
    data = response.json()
    assert data['page_count'] == 1
    assert 'Synthetic syllabus' in data['text']
    assert 'Inventory management' in data['text']
    assert data['pages'][0]['tables'][0] == [
        ['Week', 'Topic', 'Hours'], ['1', 'Inventory management', '4'],
        ['2', 'Demand forecasting', '6']]
    assert '[Page 1]' in data['text']
    assert data['warnings']
    comparison = client.post('/match', json={'home_syllabus': data['text'],
        'bocconi_syllabus': 'Inventory management and demand forecasting.'})
    assert comparison.status_code == 200
    assert comparison.json()['evidence']
    assert all(item['home']['page'] == 1 for item in comparison.json()['evidence'])


def test_image_only_pdf_requires_ocr():
    response = upload('image-only.pdf')
    assert response.status_code == 422
    assert 'OCR' in response.json()['detail']


def test_mixed_pdf_warns_about_unreadable_page():
    data = upload('mixed.pdf').json()
    assert data['page_count'] == 2
    assert any('2' in warning and 'OCR' in warning for warning in data['warnings'])


def test_encrypted_pdf_has_actionable_error():
    response = upload('encrypted.pdf')
    assert response.status_code == 422
    assert 'password' in response.json()['detail'].lower()


def test_bad_uploads_are_rejected():
    for content in [b'', b'not a PDF', b'%PDF-broken']:
        assert client.post('/extract-pdf', content=content,
            headers={'Content-Type': 'application/pdf'}).status_code == 422
    assert client.post('/extract-pdf', content=b'%PDF-1.7',
        headers={'Content-Type': 'text/plain'}).status_code == 415


def test_size_and_page_limits():
    assert client.post('/extract-pdf', content=b'%PDF-' + b'0' * (10*1024*1024),
        headers={'Content-Type': 'application/pdf'}).status_code == 413
    response = upload('too-many-pages.pdf')
    assert response.status_code == 422
    assert '30 pages' in response.json()['detail']


def test_page_and_table_markers_are_not_comparison_evidence():
    response = client.post('/match', json={
        'home_syllabus': '[Page 1]\n[Table 1]\nPainting sculpture',
        'bocconi_syllabus': '[Page 1]\n[Table 1]\nAlgebra calculus'})
    assert response.json()['shared_terms'] == []
