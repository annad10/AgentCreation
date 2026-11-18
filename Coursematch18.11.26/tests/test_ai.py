"""Offline AI integration tests: all provider requests use a mock transport."""
import json
from contextlib import contextmanager
from unittest.mock import patch
import httpx
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)
HOME = '[Page 1]\nStudents learn inventory management. Assessment is an individual exam.'
HOST = '[Page 2]\nDemand forecasting and stock control. Assessment uses group projects.'
PAYLOAD = {'home_syllabus': HOME, 'bocconi_syllabus': HOST, 'mode': 'ai', 'ai_consent': True}


def report():
    return {'findings': [{'kind': 'similarity', 'title': 'Managing inventory',
        'explanation': 'Both descriptions discuss managing stock.',
        'home_quote': 'Students learn inventory management.',
        'bocconi_quote': 'Demand forecasting and stock control.'}],
        'gaps': [{'topic': 'Demand forecasting', 'explanation': 'Coverage in the home syllabus is not established.',
            'source': 'bocconi', 'quote': 'Demand forecasting and stock control.'}],
        'insufficient_evidence': False}


def provider_response(data):
    return {'status': 'completed', 'output': [{'type': 'message', 'content': [
        {'type': 'output_text', 'text': json.dumps(data)}]}]}


@contextmanager
def provider(handler):
    with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-only-not-a-real-key',
                                   'OPENAI_MODEL': 'gpt-4.1-mini'}, clear=True), \
         patch('backend.llm.load_dotenv'), \
         patch('backend.llm._provider_client', side_effect=lambda: httpx.Client(
             transport=httpx.MockTransport(handler))):
        yield


def test_ai_requires_consent_before_any_provider_call():
    with provider(lambda request: (_ for _ in ()).throw(AssertionError('No call allowed'))):
        response = client.post('/match', json={**PAYLOAD, 'ai_consent': False})
        assert response.status_code == 422


def test_missing_key_keeps_keyword_mode_working_and_never_exposes_key():
    with patch.dict('os.environ', {}, clear=True), patch('backend.llm.load_dotenv'):
        assert client.get('/config').json()['ai_available'] is False
        response = client.post('/match', json=PAYLOAD)
        assert response.status_code == 503
        assert '.env' in response.json()['detail']
        plain = client.post('/match', json={'home_syllabus': HOME, 'bocconi_syllabus': HOST})
        assert plain.status_code == 200
        assert plain.json()['method'] == 'keyword_overlap'


def test_ai_request_and_verified_evidence():
    requests = []
    def handler(request):
        requests.append(request)
        body = json.loads(request.content)
        assert str(request.url) == 'https://api.openai.com/v1/responses'
        assert body['store'] is False
        assert body['text']['format']['strict'] is True
        assert json.loads(body['input'][0]['content']) == {
            'home_syllabus': HOME, 'bocconi_syllabus': HOST}
        return httpx.Response(200, json=provider_response(report()))
    with provider(handler):
        data = client.post('/match', json=PAYLOAD).json()
    assert len(requests) == 1
    assert data['method'] == 'ai'
    assert data['decision'] == 'ask_your_advisor'
    item = data['findings'][0]
    assert item['home']['page'] == 1
    assert item['bocconi']['page'] == 2
    for key, source in [('home', HOME), ('bocconi', HOST)]:
        evidence = item[key]
        assert source[evidence['start']:evidence['end']] == evidence['quote']
    assert data['gaps'][0]['citation']['quote'] in HOST
    assert 'test-only-not-a-real-key' not in json.dumps(data)


def test_fabricated_quotes_are_removed_with_advisor_warning():
    data = report()
    data['findings'][0]['home_quote'] = 'This invented quote does not exist.'
    data['gaps'][0]['quote'] = 'Another invented quote that is not in the syllabus.'
    with provider(lambda request: httpx.Response(200, json=provider_response(data))):
        response = client.post('/match', json=PAYLOAD)
    assert response.status_code == 200
    result = response.json()
    assert result['findings'] == [] and result['gaps'] == []
    assert result['insufficient_evidence'] is True
    assert result['warnings']


def test_provider_errors_are_actionable_without_echoing_provider_body():
    for status, expected in [(401, 503), (403, 503), (429, 429), (500, 502)]:
        with provider(lambda request: httpx.Response(status, text='secret provider diagnostic')):
            response = client.post('/match', json=PAYLOAD)
        assert response.status_code == expected
        assert 'secret provider diagnostic' not in response.text


def test_timeout_is_handled_without_retry():
    calls = []
    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout('private diagnostic', request=request)
    with provider(handler):
        response = client.post('/match', json=PAYLOAD)
    assert response.status_code == 504
    assert len(calls) == 1
    assert 'private diagnostic' not in response.text


def test_refusal_incomplete_and_invalid_output_are_not_claimed_as_results():
    cases = [
        {'status': 'incomplete', 'output': []},
        {'status': 'completed', 'output': [{'type': 'message', 'content': [{'type': 'refusal'}]}]},
        {'status': 'completed', 'output': []},
        provider_response({'unexpected': 'bad schema'})]
    for body in cases:
        with provider(lambda request: httpx.Response(200, json=body)):
            assert client.post('/match', json=PAYLOAD).status_code == 502


def test_keyword_mode_never_calls_provider_even_with_consent():
    with provider(lambda request: (_ for _ in ()).throw(AssertionError('Unexpected paid request'))):
        response = client.post('/match', json={**PAYLOAD, 'mode': 'keyword'})
        assert response.status_code == 200
        assert response.json()['method'] == 'keyword_overlap'
        assert client.get('/config').json() == {'ai_available': True}


def test_invalid_mode_or_non_boolean_consent_is_rejected():
    for changes in [{'mode': 'anything'}, {'ai_consent': 'false'}]:
        assert client.post('/match', json={**PAYLOAD, **changes}).status_code == 422
