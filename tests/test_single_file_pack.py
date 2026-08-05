"""Pack ottimizzazione = un solo file HTML che consolida tutti i fix."""

from __future__ import annotations

import io
import zipfile
from types import SimpleNamespace

from services.artifacts import (
    UNIFIED_FIX_FILENAME,
    build_unified_fix_html,
    unified_fix_html_from_entity,
)
from services.export import (
    multi_site_zip,
    pack_fix_filename,
    pack_fix_html_bytes,
    pack_zip_bytes,
)


def test_unified_fix_html_contains_all_sections():
    html = build_unified_fix_html(
        url="https://acme.example/",
        domain="acme.example",
        llms_txt="# Acme\n> Brand guide",
        organization_jsonld_html='<script type="application/ld+json">{"@type":"Organization"}</script>',
        faq_jsonld_html="",
        meta_pack_html="<meta name='description' content='Acme' />",
        robots_txt="User-agent: *\nAllow: /\n",
        checklist_md="- [ ] Pubblica llms.txt",
        before_after_md="AIO 40 → target 70",
        findings=[
            {
                "severity": "critical",
                "title": "llms.txt assente",
                "detail": "manca in root",
            }
        ],
        aio_score=41,
        geo_score=38,
    )
    assert "Pack ottimizzazione — un solo file" in html
    assert "llms.txt assente" in html
    assert "# Acme" in html
    assert "User-agent: *" in html
    assert "Organization" in html
    assert "Pubblica llms.txt" in html
    assert 'id="head-fix"' in html
    assert 'id="llms-fix"' in html
    assert 'id="robots-fix"' in html


def test_pack_zip_contains_exactly_one_file():
    entity = SimpleNamespace(
        domain="acme.example",
        url="https://acme.example/",
        llms_txt="# Acme",
        json_ld_artifact="<script></script>",
        faq_artifact="",
        meta_pack_artifact="<meta />",
        robots_artifact="User-agent: *\nAllow: /\n",
        checklist_artifact="- fix",
        before_after_artifact="",
        findings=[{"severity": "warn", "title": "meta", "detail": "thin"}],
        aio_score=50,
        geo_score=50,
    )
    raw = pack_zip_bytes(entity)
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        names = zf.namelist()
        assert names == [UNIFIED_FIX_FILENAME]
        body = zf.read(UNIFIED_FIX_FILENAME).decode("utf-8")
    assert "acme.example" in body
    assert pack_fix_html_bytes(entity).decode("utf-8") == body
    assert pack_fix_filename(entity) == "centropic-acme.example-fix.html"


def test_multi_site_zip_one_html_per_folder():
    sites = [
        SimpleNamespace(
            id=1,
            domain="a.example",
            url="https://a.example/",
            llms_txt="a",
            json_ld_artifact="",
            faq_artifact="",
            meta_pack_artifact="",
            robots_artifact="",
            checklist_artifact="",
            before_after_artifact="",
            findings=[],
            aio_score=1,
            geo_score=1,
        ),
        SimpleNamespace(
            id=2,
            domain="b.example",
            url="https://b.example/",
            llms_txt="b",
            json_ld_artifact="",
            faq_artifact="",
            meta_pack_artifact="",
            robots_artifact="",
            checklist_artifact="",
            before_after_artifact="",
            findings=[],
            aio_score=2,
            geo_score=2,
        ),
    ]
    raw = multi_site_zip(sites)
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        names = sorted(zf.namelist())
    assert names == [
        f"a.example/{UNIFIED_FIX_FILENAME}",
        f"b.example/{UNIFIED_FIX_FILENAME}",
    ]


def test_unified_from_entity_uses_persisted_artifacts():
    entity = SimpleNamespace(
        domain="brand.io",
        url="https://brand.io/",
        llms_txt="HELLO_LLMS",
        json_ld_artifact="ORG_LD",
        faq_artifact="FAQ_LD",
        meta_pack_artifact="META_X",
        robots_artifact="ROBOTS_Y",
        checklist_artifact="CHECK_Z",
        before_after_artifact="BA_W",
        findings=[],
        aio_score=70,
        geo_score=65,
    )
    html = unified_fix_html_from_entity(entity)
    assert "HELLO_LLMS" in html
    assert "ORG_LD" in html
    assert "FAQ_LD" in html
    assert "META_X" in html
    assert "ROBOTS_Y" in html
    assert "CHECK_Z" in html
    assert "BA_W" in html
