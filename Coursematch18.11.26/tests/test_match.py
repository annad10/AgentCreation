from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)
HOME = 'Students study inventory management and demand forecasting.'
HOST = 'This course covers inventory management and forecasting methods.'


def test_comparison_has_exact_evidence_from_both_sources():
    response = client.post('/match', json={'home_syllabus': HOME, 'bocconi_syllabus': HOST})
    assert response.status_code == 200
    result = response.json()
    assert result['method'] == 'keyword_overlap'
    assert result['decision'] == 'ask_your_advisor'
    assert 'inventory' in result['shared_terms']
    for evidence in result['evidence']:
        for field, source in [('home', HOME), ('bocconi', HOST)]:
            citation = evidence[field]
            assert source[citation['start']:citation['end']] == citation['quote']
            assert evidence['term'] in citation['quote'].lower()


def test_no_overlap_and_stopwords_do_not_become_a_match():
    result = client.post('/match', json={
        'home_syllabus': 'The course covers painting and sculpture.',
        'bocconi_syllabus': 'The course covers algebra and calculus.'
    }).json()
    assert result['shared_terms'] == []
    assert result['evidence'] == []
    assert result['decision'] == 'ask_your_advisor'


def test_empty_oversized_and_invalid_inputs_are_rejected():
    for text in ['', '   ', 'a' * 30001, 42]:
        assert client.post('/match', json={
            'home_syllabus': text, 'bocconi_syllabus': HOST
        }).status_code == 422
    assert client.post('/match', json={'home_syllabus': HOME}).status_code == 422


def test_accents_keep_valid_source_offsets():
    home = 'Économie : stratégie et développement.'
    host = 'Stratégie et économie appliquée.'
    result = client.post('/match', json={
        'home_syllabus': home, 'bocconi_syllabus': host
    }).json()
    assert 'stratégie' in result['shared_terms']
    for evidence in result['evidence']:
        for field, text in [('home', home), ('bocconi', host)]:
            item = evidence[field]
            assert text[item['start']:item['end']] == item['quote']
