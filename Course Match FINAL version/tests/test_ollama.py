"""Offline local-provider integration tests; no model download or network."""
import json
from contextlib import contextmanager
from unittest.mock import patch
import httpx
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)
HOME = '[Page 1]\nStudents learn inventory management.'
HOST = '[Page 2]\nThe course covers stock control.'
PAYLOAD = {'home_syllabus': HOME, 'bocconi_syllabus': HOST, 'mode': 'ollama'}


def output():
    return {'findings': [{'kind': 'similarity', 'title': 'Inventory',
        'explanation': 'Both descriptions discuss managing stock.',
        'home_quote': 'Students learn inventory management.',
        'bocconi_quote': 'The course covers stock control.'}],
        'gaps': [], 'insufficient_evidence': False}


@contextmanager
def provider(handler, model='qwen3:0.6b'):
    with patch.dict('os.environ', {'OLLAMA_MODEL': model}, clear=True), \
         patch('backend.llm.load_dotenv'), \
         patch('backend.llm._local_client', side_effect=lambda: httpx.Client(
             transport=httpx.MockTransport(handler))), \
         patch('backend.llm._provider_client', side_effect=AssertionError('No cloud calls')):
        yield


def test_local_comparison_uses_loopback_schema_and_no_key():
    calls = []
    def handler(request):
        calls.append(request)
        assert str(request.url) == 'http://127.0.0.1:11434/api/chat'
        assert 'authorization' not in request.headers
        body = json.loads(request.content)
        assert body['model'] == 'qwen3:0.6b'
        assert body['stream'] is False and body['think'] is False
        assert body['format']['type'] == 'object'
        assert json.loads(body['messages'][1]['content'])['home_syllabus'] == HOME
        return httpx.Response(200, json={'done': True, 'done_reason': 'stop',
            'message': {'content': json.dumps(output())}})
    with provider(handler):
        response = client.post('/match', json=PAYLOAD)
    assert response.status_code == 200
    data = response.json()
    assert data['provider'] == 'ollama' and data['method'] == 'ai'
    assert data['decision'] == 'ask_your_advisor'
    assert data['findings'][0]['home']['page'] == 1
    assert data['warnings']
    assert len(calls) == 1


def test_local_errors_give_instructions_and_never_echo_diagnostics():
    for status, expected, text in [(404, 503, 'ollama run'), (500, 502, 'memory')]:
        with provider(lambda request: httpx.Response(status, text='private diagnostic')):
            response = client.post('/match', json=PAYLOAD)
        assert response.status_code == expected
        assert text in response.json()['detail']
        assert 'private diagnostic' not in response.text


def test_local_connection_and_timeout_errors():
    for error, status in [(httpx.ConnectError, 503), (httpx.ReadTimeout, 504)]:
        def handler(request):
            raise error('private diagnostic', request=request)
        with provider(handler):
            response = client.post('/match', json=PAYLOAD)
        assert response.status_code == status
        assert 'private diagnostic' not in response.text


def test_local_rejects_incomplete_bad_json_and_fabricated_quotes():
    for body in [{'done': False}, {'done': True, 'done_reason': 'length'},
        {'done': True, 'done_reason': 'stop', 'message': {'content': '{}'}}]:
        with provider(lambda request: httpx.Response(200, json=body)):
            assert client.post('/match', json=PAYLOAD).status_code == 502
    data = output()
    data['findings'][0]['home_quote'] = 'This sentence was invented by a model.'
    with provider(lambda request: httpx.Response(200, json={'done': True,
        'done_reason': 'stop', 'message': {'content': json.dumps(data)}})):
        result = client.post('/match', json=PAYLOAD).json()
    assert result['findings'] == []
    assert result['insufficient_evidence'] is True


def test_local_limits_do_not_silently_truncate_or_call_cloud():
    with provider(lambda request: (_ for _ in ()).throw(AssertionError('No request allowed'))):
        response = client.post('/match', json={**PAYLOAD, 'home_syllabus': 'a' * 6001})
        assert response.status_code == 422
        assert '6,000' in response.json()['detail']
    with provider(lambda request: (_ for _ in ()).throw(AssertionError('No request allowed')),
                  model='some-model:cloud'):
        assert client.post('/match', json=PAYLOAD).status_code == 503
