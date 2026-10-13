"""Mocked contract tests: zero external API requests."""
import json
import pytest
from pydantic import ValidationError
from app.classification import OpenAIClassifier

class Response:
    def __init__(self, data):
        self.data=data
    def raise_for_status(self):
        pass
    def json(self):
        return {"choices":[{"message":{"content":json.dumps(self.data)}}]}

class Client:
    calls=[]
    next_response=None
    def __init__(self,*args,**kwargs):
        pass
    def __enter__(self):
        return self
    def __exit__(self,*args):
        pass
    def post(self,url,*,headers,json):
        self.__class__.calls.append((url,headers,json))
        return self.next_response

def test_structured_schema_sent_and_validated(monkeypatch):
    monkeypatch.setattr("app.classification.httpx.Client",Client)
    Client.next_response=Response({"label":"lead","score":83,"reason":"Test case","draft":"Hello!"})
    item=OpenAIClassifier(api_key="test-placeholder").classify("We need design help")
    assert item.score==83
    url,headers,payload=Client.calls[-1]
    assert url=="https://api.openai.com/v1/chat/completions"
    assert payload["response_format"]["type"]=="json_schema"
    assert payload["response_format"]["json_schema"]["strict"] is True
    assert headers["Authorization"].startswith("Bearer ")

def test_invalid_ai_output_rejected(monkeypatch):
    monkeypatch.setattr("app.classification.httpx.Client",Client)
    Client.next_response=Response({"label":"lead","score":500,"reason":"Bad","draft":"Hi"})
    with pytest.raises(ValidationError):
        OpenAIClassifier(api_key="test-placeholder").classify("We need design help")
