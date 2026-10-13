from fastapi.testclient import TestClient
from app.api import create_app
from app.schemas import Decision

def make_client(tmp_path, classifier=None):
    return TestClient(create_app(tmp_path / "test.sqlite3", classifier=classifier))

def msg(source="synthetic-a", external_id="one", text="We need a website design for a new launch"):
    return {"source":source,"external_id":external_id,"text":text}

def test_health(tmp_path):
    with make_client(tmp_path) as client:
        assert client.get("/health").json() == {"status":"ok"}

def test_requires_review_before_any_outbound_action(tmp_path):
    with make_client(tmp_path) as client:
        result = client.post("/v1/messages",json=msg())
        assert result.status_code == 200
        item = result.json()
        assert item["label"] == "lead"
        assert item["review_status"] == "pending"
        assert item["draft"]
        accepted = client.post(f"/v1/messages/{item['id']}/review",json={"action":"approve"})
        assert accepted.json()["review_status"] == "approved"
        assert client.post(f"/v1/messages/{item['id']}/review",json={"action":"approve"}).status_code == 409

def test_idempotency(tmp_path):
    with make_client(tmp_path) as client:
        a = client.post("/v1/messages",json=msg()).json()
        b = client.post("/v1/messages",json=msg()).json()
        assert a["id"] == b["id"]
        assert b["reused"] is True
        assert len(client.get("/v1/messages").json()) == 1

def test_cross_source_content_deduplication(tmp_path):
    with make_client(tmp_path) as client:
        first = client.post("/v1/messages",json=msg()).json()
        second = client.post("/v1/messages",json=msg(source="synthetic-b",text=" we NEED a WEBSITE design for a new launch ")).json()
        assert second["label"] == "duplicate"
        assert second["duplicate_of"] == first["id"]

def test_prefilter_skips_llm(tmp_path):
    class NoCalls:
        def classify(self, text):
            raise AssertionError("LLM must not be called")

    with make_client(tmp_path,classifier=NoCalls()) as client:
        result = client.post("/v1/messages",json=msg(text="Ищу работу. Мое резюме")).json()
        assert result["label"] == "noise"
        assert result["review_status"] == "not_required"

def test_ambiguous_message(tmp_path):
    with make_client(tmp_path) as client:
        result = client.post("/v1/messages",json=msg(text="Need advice on a project; details later")).json()
        assert result["label"] == "needs_review"
        assert result["draft"] == ""
        assert result["review_status"] == "pending"

def test_provider_failure_is_safe(tmp_path):
    class Broken:
        def classify(self, text):
            raise RuntimeError("provider is down")
    with make_client(tmp_path,classifier=Broken()) as client:
        result = client.post("/v1/messages",json=msg()).json()
        assert result["label"] == "needs_review"
        assert result["review_status"] == "pending"
        assert "provider is down" not in result["reason"]

def test_noise_cannot_be_approved(tmp_path):
    with make_client(tmp_path) as client:
        row = client.post("/v1/messages",json=msg(text="A general technology discussion topic")).json()
        assert row["label"] == "noise"
        assert client.post(f"/v1/messages/{row['id']}/review",json={"action":"approve"}).status_code == 409

def test_custom_classifier(tmp_path):
    class Synthetic:
        def classify(self,text):
            return Decision(label="lead",score=92,reason="Synthetic example",draft="Hello")
    with make_client(tmp_path,classifier=Synthetic()) as client:
        assert client.post("/v1/messages",json=msg()).json()["score"] == 92

def test_bad_source_rejected(tmp_path):
    with make_client(tmp_path) as client:
        assert client.post("/v1/messages",json=msg(source="https://site/path")).status_code == 422
