"""S3 analysis pack store + Redis TPM gates."""

from __future__ import annotations

import json

import pytest

from services.artifact_s3 import (
    apply_pack_attrs,
    clear_bulky_pack_attrs,
    ensure_pack_loaded,
    pack_dict_from_mapping,
    pack_uri_for_key,
    parse_pack_uri,
    upload_pack,
)
from services.llm_tpm import (
    RedisTpmBucket,
    TpmBucket,
    acquire_tpm,
    reset_tpm_buckets_for_tests,
)
from services.redis_client import reset_redis_client_for_tests


class _FakeS3:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    def put_object(self, *, Bucket, Key, Body, ContentType=None):
        self.objects[(Bucket, Key)] = Body if isinstance(Body, bytes) else bytes(Body)
        return {}

    def get_object(self, *, Bucket, Key):
        body = self.objects[(Bucket, Key)]

        class _Body:
            def __init__(self, data: bytes):
                self._data = data

            def read(self):
                return self._data

        return {"Body": _Body(body)}


class _FakeRedis:
    def __init__(self) -> None:
        self.zsets: dict[str, dict[str, float]] = {}

    def pipeline(self):
        return _FakePipe(self)

    def zrange(self, key, start, end, withscores=False):
        items = sorted((self.zsets.get(key) or {}).items(), key=lambda kv: kv[1])
        if end == -1:
            sliced = items[start:]
        else:
            sliced = items[start : end + 1]
        if withscores:
            return [(m, s) for m, s in sliced]
        return [m for m, _ in sliced]


class _FakePipe:
    def __init__(self, r: _FakeRedis):
        self.r = r
        self.ops: list = []

    def zremrangebyscore(self, key, min_s, max_s):
        self.ops.append(("zrem", key, min_s, max_s))
        return self

    def zrange(self, key, start, end, withscores=False):
        self.ops.append(("zrange", key, start, end, withscores))
        return self

    def zadd(self, key, mapping):
        self.ops.append(("zadd", key, mapping))
        return self

    def expire(self, key, ttl):
        self.ops.append(("expire", key, ttl))
        return self

    def execute(self):
        out = []
        for op in self.ops:
            if op[0] == "zrem":
                _, key, _min_s, max_s = op
                z = self.r.zsets.setdefault(key, {})
                drop = [m for m, s in z.items() if s <= max_s]
                for m in drop:
                    del z[m]
                out.append(len(drop))
            elif op[0] == "zrange":
                _, key, start, end, withscores = op
                out.append(self.r.zrange(key, start, end, withscores=withscores))
            elif op[0] == "zadd":
                _, key, mapping = op
                z = self.r.zsets.setdefault(key, {})
                z.update(mapping)
                out.append(len(mapping))
            elif op[0] == "expire":
                out.append(True)
        self.ops.clear()
        return out


def test_parse_pack_uri():
    assert parse_pack_uri("s3://bucket/a/b.json") == ("bucket", "a/b.json")
    assert parse_pack_uri("https://x") is None


def test_upload_and_hydrate_pack(monkeypatch):
    fake = _FakeS3()
    monkeypatch.setenv("ANALYZE_ARTIFACT_STORE", "s3")
    monkeypatch.setenv("ANALYZE_S3_BUCKET", "centropic-test")
    monkeypatch.setenv("ANALYZE_ARTIFACT_DB_LEAN", "1")
    monkeypatch.setenv("ANALYZE_ARTIFACT_PREVIEW_CHARS", "8")
    monkeypatch.setattr("services.artifact_s3._client", lambda: fake)

    pack = pack_dict_from_mapping(
        {
            "llms.txt": "# Brand long content here",
            "organization.jsonld.html": "<script>ORG</script>",
            "robots.txt": "User-agent: *\n",
        }
    )
    uri = upload_pack(pack, user_id=1, site_id=2, run_id=3)
    assert uri == pack_uri_for_key(
        "centropic-test", "analyze-packs/u1/s2/r3/pack.json"
    )
    assert ("centropic-test", "analyze-packs/u1/s2/r3/pack.json") in fake.objects

    class _Ent:
        pack_uri = uri
        llms_txt = ""
        json_ld_artifact = ""
        faq_artifact = ""
        meta_pack_artifact = ""
        robots_artifact = ""
        checklist_artifact = ""
        before_after_artifact = ""

    ent = _Ent()
    clear_bulky_pack_attrs(ent, llms_preview=pack["llms.txt"])
    assert ent.llms_txt == "# Brand "
    assert ent.json_ld_artifact == ""
    ensure_pack_loaded(ent)
    assert "ORG" in ent.json_ld_artifact
    assert ent.llms_txt.startswith("# Brand")


def test_apply_pack_attrs_roundtrip():
    class _E:
        llms_txt = ""
        json_ld_artifact = ""
        faq_artifact = ""
        meta_pack_artifact = ""
        robots_artifact = ""
        checklist_artifact = ""
        before_after_artifact = ""

    e = _E()
    apply_pack_attrs(e, {"llms.txt": "x", "robots.txt": "y"})
    assert e.llms_txt == "x"
    assert e.robots_artifact == "y"


def test_tpm_memory_blocks_when_exhausted():
    reset_tpm_buckets_for_tests()
    bucket = TpmBucket(100, name="t")
    assert bucket.acquire(60, block=False) is True
    assert bucket.acquire(50, block=False) is False
    assert bucket.acquire(40, block=False) is True


def test_tpm_redis_shared(monkeypatch):
    reset_redis_client_for_tests()
    reset_tpm_buckets_for_tests()
    fake = _FakeRedis()
    monkeypatch.setenv("LLM_TPM_BACKEND", "redis")
    monkeypatch.setenv("OPENAI_TPM", "100")
    monkeypatch.setenv("LLM_TPM_RESERVE_TOKENS", "40")
    monkeypatch.setattr("services.redis_client.get_redis", lambda ping=True: fake)

    assert acquire_tpm("openai", 40, block=False) is True
    assert acquire_tpm("openai", 40, block=False) is True
    assert acquire_tpm("openai", 40, block=False) is False

    bucket = RedisTpmBucket(100, name="openai", redis_client=fake)
    # Already near cap from acquire_tpm above — non-blocking reject
    assert bucket.acquire(30, block=False) is False
    reset_tpm_buckets_for_tests()
    reset_redis_client_for_tests()


def test_persist_analysis_offloads_to_s3(monkeypatch):
    from app import AnalysisRun, SiteAnalysis, User, app, db, ensure_schema
    from services.analysis_store import persist_analysis

    fake = _FakeS3()
    monkeypatch.setenv("ANALYZE_ARTIFACT_STORE", "s3")
    monkeypatch.setenv("ANALYZE_S3_BUCKET", "centropic-test")
    monkeypatch.setenv("ANALYZE_ARTIFACT_DB_LEAN", "1")
    monkeypatch.setattr("services.artifact_s3._client", lambda: fake)

    with app.app_context():
        ensure_schema()
        user = User(email="s3pack@example.com", name="S3 Pack", password_hash="x")
        db.session.add(user)
        db.session.commit()

        pack = {
            "llms.txt": "# Hello pack",
            "organization.jsonld.html": "<script type='application/ld+json'>{}</script>",
            "faq.jsonld.html": "",
            "meta-pack.html": "<meta />",
            "robots.txt": "User-agent: *\nAllow: /\n",
            "fix-this-week.md": "- a",
            "before-after.md": "before",
        }
        result = {
            "aio_score": 70,
            "geo_score": 65,
            "findings": [{"id": "x", "title": "t"}],
            "notes": "n",
            "scraped": {"domain": "example.com", "title": "Ex"},
            "pages": [],
            "pages_analyzed": 1,
            "competitors": [],
            "signals": {},
            "probes": {},
        }
        analysis = persist_analysis(
            db.session,
            SiteAnalysis=SiteAnalysis,
            AnalysisRun=AnalysisRun,
            user_id=user.id,
            url="https://example.com/",
            result=result,
            pack=pack,
            source="job",
        )
        assert analysis.pack_uri.startswith("s3://centropic-test/")
        assert analysis.json_ld_artifact == ""
        assert analysis.aio_score == 70
        run = AnalysisRun.query.filter_by(site_id=analysis.id).order_by(AnalysisRun.id.desc()).first()
        assert run is not None
        assert run.pack_uri == analysis.pack_uri
        raw = fake.objects[("centropic-test", analysis.pack_uri.split("s3://centropic-test/", 1)[1])]
        loaded = json.loads(raw.decode("utf-8"))
        assert loaded["llms.txt"] == "# Hello pack"
        ensure_pack_loaded(analysis)
        assert "application/ld+json" in analysis.json_ld_artifact
