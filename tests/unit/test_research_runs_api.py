from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.main import app
from app.api.routes.research_runs import get_research_run_service
from data_layer.repositories.base import Base
from data_layer.repositories.research_run_repository import ResearchRunRepository
from services.research_run_service import ResearchRunService


def _payload() -> dict:
    return {
        "template_key": "a_share_deep_research",
        "subject": {
            "subject_type": "security",
            "subject_id": "600519.SH",
            "display_name": "贵州茅台",
            "market": "A-share",
        },
        "as_of": "2026-08-10T00:00:00Z",
        "question": "增长叙事是否有证据支持？",
        "evidence_inputs": [
            {
                "evidence_id": f"ev-{kind}",
                "source_ref": f"doc-{kind}",
                "source_name": "测试来源",
                "evidence_kind": kind,
                "summary": f"{kind} 证据摘要",
                "claim_text": f"{kind} 研究观点",
            }
            for kind in ("financial", "industry", "valuation", "risk", "consensus")
        ],
    }


def test_research_run_api_creates_executes_and_exposes_traceable_outputs():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    service = ResearchRunService(ResearchRunRepository(session))
    app.dependency_overrides[get_research_run_service] = lambda: service
    try:
        client = TestClient(app)
        created = client.post("/api/research-runs", json=_payload())

        assert created.status_code == 201
        run_id = created.json()["run_id"]
        assert created.json()["status"] == "draft"
        assert created.json()["subject"]["display_name"] == "贵州茅台"

        executed = client.post(f"/api/research-runs/{run_id}/execute")
        outputs = client.get(f"/api/research-runs/{run_id}/outputs")

        assert executed.status_code == 200
        assert executed.json()["status"] == "completed"
        assert outputs.status_code == 200
        assert outputs.json()["decision_card"]["target_id"] == "600519.SH"
        assert outputs.json()["report_markdown"]
        assert all(item["evidence_refs"] for item in outputs.json()["claims"])
    finally:
        app.dependency_overrides.pop(get_research_run_service, None)
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_research_template_catalog_and_validation_are_exposed_by_api():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    service = ResearchRunService(ResearchRunRepository(session))
    app.dependency_overrides[get_research_run_service] = lambda: service
    try:
        client = TestClient(app)
        catalog = client.get("/api/research-templates")

        assert catalog.status_code == 200
        templates = catalog.json()
        assert [item["template_key"] for item in templates] == [
            "a_share_deep_research",
            "macro_research",
            "commodity_research",
            "index_research",
            "industry_research",
        ]
        assert [item["available"] for item in templates] == [True, False, False, False, False]

        unavailable = client.post(
            "/api/research-runs",
            json={
                **_payload(),
                "template_key": "macro_research",
                "subject": {
                    "subject_type": "macro",
                    "subject_id": "china-macro",
                    "display_name": "中国宏观",
                },
            },
        )
        incompatible = client.post(
            "/api/research-runs",
            json={
                **_payload(),
                "subject": {
                    "subject_type": "index",
                    "subject_id": "000300.SH",
                    "display_name": "沪深300",
                },
            },
        )

        assert unavailable.status_code == 422
        assert incompatible.status_code == 422
        assert client.get("/api/research-runs").json() == []
    finally:
        app.dependency_overrides.pop(get_research_run_service, None)
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_research_run_api_exports_markdown_and_word_only_after_completion():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    service = ResearchRunService(ResearchRunRepository(session))
    app.dependency_overrides[get_research_run_service] = lambda: service
    try:
        client = TestClient(app)
        run_id = client.post("/api/research-runs", json=_payload()).json()["run_id"]

        blocked_download = client.get(f"/api/research-runs/{run_id}/downloads/markdown")
        assert blocked_download.status_code == 409

        client.post(f"/api/research-runs/{run_id}/execute")
        markdown = client.get(f"/api/research-runs/{run_id}/downloads/markdown")
        word = client.get(f"/api/research-runs/{run_id}/downloads/word")

        assert markdown.status_code == 200
        assert markdown.headers["content-type"].startswith("text/markdown")
        assert markdown.content.startswith(b"#")
        assert word.status_code == 200
        assert word.headers["content-type"].startswith(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        assert word.content.startswith(b"PK")
    finally:
        app.dependency_overrides.pop(get_research_run_service, None)
        session.close()
        Base.metadata.drop_all(bind=engine)
