"""Actual document files, not chat-text substitutes."""

from app.research_web.resources.research_helpers import read_pdf, write_deliverables


def test_requested_office_files_are_real_openable_documents(tmp_path):
    from docx import Document
    from openpyxl import load_workbook

    outputs = write_deliverables(
        tmp_path,
        "研究",
        [{"heading": "结论", "text": "缺少行情数据，不做估值结论"}],
        [{"metric": "PE", "value": None}],
        ["https://example.com/source"],
    )
    assert set(outputs) == {"markdown", "html", "docx", "xlsx"}
    assert Document(outputs["docx"]).paragraphs[0].text == "研究"
    workbook = load_workbook(outputs["xlsx"])
    assert workbook["analysis"]["B2"].value is None
    assert "https://example.com/source" in outputs["html"].read_text()


def test_pdf_extraction_includes_real_page_numbers(tmp_path):
    from matplotlib.figure import Figure

    path = tmp_path / "input.pdf"
    figure = Figure()
    figure.text(0.1, 0.8, "Revenue 123")
    figure.savefig(path)
    pages = read_pdf(path)
    assert pages[0]["page"] == 1
    assert "123" in pages[0]["text"]


def test_hot_helper_verifies_raw_but_returns_only_bounded_selected_evidence(tmp_path, monkeypatch):
    import hashlib, json
    from uuid import uuid4
    import pytest
    from test_hot_snapshot_publication import bundle
    from app.research_web.resources.research_helpers import read_hot_evidence
    evidence = bundle(str(uuid4()), str(uuid4()))
    did = str(uuid4()); root = tmp_path / 'inputs' / 'datasets' / did;root.mkdir(parents=True)
    (root / 'evidence-manifest.json').write_bytes(evidence['manifestBytes'])
    for item in evidence['manifest']['objects']:
        (root / item['filename']).write_bytes(evidence['objects'][item['key']])
    context = {'dataset_id': did, 'evidence_manifest': f'inputs/datasets/{did}/evidence-manifest.json',
               'evidence_manifest_hash': evidence['manifestHash'], 'logical_instance_id': evidence['manifest']['instanceId'],
               'selected_material_ids': evidence['manifest']['materialIds']}
    path = tmp_path / 'inputs/hot-context.json';path.write_text(json.dumps(context))
    monkeypatch.chdir(tmp_path)
    result = read_hot_evidence()
    assert result['manifestHash'] == evidence['manifestHash']
    assert result['materials'][0]['rawHash'] == hashlib.sha256(evidence['objects']['raw:' + evidence['manifest']['materialIds'][0]]).hexdigest()
    assert 'complete stored source response' not in json.dumps(result)
    raw = root / evidence['manifest']['objects'][0]['filename'];raw.write_bytes(b'tamper')
    with pytest.raises(ValueError, match='hot_evidence_read_failed'):
        read_hot_evidence()


def test_hot_helper_limits_large_titles_urls_and_limitations(tmp_path, monkeypatch):
    import hashlib, json
    from uuid import uuid4
    from test_hot_snapshot_publication import bundle
    from app.research_web.resources.research_helpers import read_hot_evidence
    evidence = bundle(str(uuid4()), str(uuid4()))
    normalized = next(x for x in evidence['manifest']['objects'] if x['format'] == 'application/json')
    value = json.loads(evidence['objects'][normalized['key']]);value.update(title='大' * 10000, originalUrl='https://example.com/' + 'a' * 10000)
    raw = json.dumps(value).encode();evidence['objects'][normalized['key']] = raw
    normalized.update(bytes=len(raw), contentHash=hashlib.sha256(raw).hexdigest())
    evidence['manifest'].update(totalBytes=sum(len(v) for v in evidence['objects'].values()), limitations=['缺口' * 10000])
    canonical = json.dumps(evidence['manifest']).encode();did = str(uuid4())
    root = tmp_path / 'inputs/datasets' / did;root.mkdir(parents=True)
    (root / 'evidence-manifest.json').write_bytes(canonical)
    for item in evidence['manifest']['objects']:(root / item['filename']).write_bytes(evidence['objects'][item['key']])
    (tmp_path / 'inputs/hot-context.json').write_text(json.dumps({'dataset_id':did,'evidence_manifest':f'inputs/datasets/{did}/evidence-manifest.json',
        'evidence_manifest_hash':hashlib.sha256(canonical).hexdigest(),'logical_instance_id':evidence['manifest']['instanceId'],'selected_material_ids':evidence['manifest']['materialIds']}))
    monkeypatch.chdir(tmp_path)
    result = read_hot_evidence();material = result['materials'][0]
    assert set(material['truncatedFields']) == {'title','originalUrl'}
    assert material['originalUrl'] is None and len(material['title'].encode()) <= 256
    assert result['limitationsTruncated'] and len(json.dumps(result,ensure_ascii=False).encode()) <= 32768
