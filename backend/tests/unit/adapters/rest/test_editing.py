"""`POST /documents/{id}/edit`: parts of the document's pages and of added files; the part that
replaces it is its next version, the others new documents, the document gone without one."""

import json
from typing import Any

from lekto.adapters.outbound.memory import fake_pdf
from tests.api import auth
from tests.unit.adapters.rest.support import DOCUMENTS, Api, file_part, upload


def form(parts: Any, *files: tuple[str, bytes], **fields: str) -> dict[str, Any]:
    """The multipart request: `parts` as JSON (text as it is), `files` as file parts, and other
    `fields` (`documents`, `target`) as they are."""
    text = parts if isinstance(parts, str) else json.dumps(parts)
    return {
        "files": [
            ("parts", (None, text)),
            *((name, (None, value)) for name, value in fields.items()),
            *(("files", (name, content, "application/octet-stream")) for name, content in files),
        ],
    }


async def test_a_part_replaces_the_document_another_becomes_one(api: Api) -> None:
    owner = await api.user()
    id = await upload(api, auth(owner))
    url = f"{DOCUMENTS}/{id}"
    parts = [
        {"pages": [{"page": 1}], "replaces": True},
        {"pages": [{"source": 1, "page": 1, "rotate": 90}]},
    ]
    response = await api.client.post(
        f"{url}/edit",
        **form(parts, ("forgotten.pdf", fake_pdf(1, "forgotten"))),
        headers=auth(owner),
    )
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["deleted"] is False
    edited, new = body["documents"]
    assert edited["id"] == id and new["id"] != id
    assert new["original_filename"] == "Bill 2026 (2).pdf"
    await api.drain()
    files = (await api.client.get(f"{url}/files", headers=auth(owner))).json()
    assert [(item["kind"], item["detail"].get("added")) for item in files["versions"]] == [
        ("received", None),
        ("edited", ["forgotten.pdf"]),
    ]
    split = (await api.client.get(f"{DOCUMENTS}/{new['id']}/files", headers=auth(owner))).json()
    [first] = split["versions"]
    assert (first["kind"], first["detail"]["document"]) == ("split", id)


async def test_without_a_part_that_replaces_it_the_document_is_gone(api: Api) -> None:
    owner = await api.user()
    id = await upload(api, auth(owner))
    parts = [{"pages": [{"page": 1}]}, {"pages": [{"source": 1, "page": 1}]}]
    response = await api.client.post(
        f"{DOCUMENTS}/{id}/edit",
        **form(parts, ("more.pdf", fake_pdf(1, "more"))),
        headers=auth(owner),
    )
    assert response.status_code == 202, response.text
    assert response.json()["deleted"] is True
    assert len(response.json()["documents"]) == 2
    gone = await api.client.get(f"{DOCUMENTS}/{id}", headers=auth(owner))
    assert gone.status_code == 404


async def test_documents_are_merged_into_the_target(api: Api) -> None:
    owner = await api.user()
    stack = await upload(api, auth(owner))
    scan = await upload(api, auth(owner), content=fake_pdf(2, "scan"), filename="scan_0412.pdf")
    url = f"{DOCUMENTS}/{stack}/edit"
    merge = [{"pages": [{"page": 1}, {"source": 1, "page": 1}], "replaces": True}]
    for fields in ({"documents": "[1]"}, {"documents": json.dumps([scan]), "target": "nope"}):
        refused = await api.client.post(url, **form(merge, **fields), headers=auth(owner))
        assert refused.status_code == 422, refused.text
    alone = [{"pages": [{"page": 1}]}, {"pages": [{"source": 1, "page": 1}]}]
    response = await api.client.post(
        url, **form(alone, documents=json.dumps([scan])), headers=auth(owner)
    )
    assert response.status_code == 422  # a merge needs a part that continues the target
    response = await api.client.post(
        url, **form(merge, documents=json.dumps([scan]), target=scan), headers=auth(owner)
    )
    assert response.status_code == 202, response.text
    body = response.json()
    assert (body["deleted"], body["merged"]) == (False, [stack])
    [target] = body["documents"]
    assert target["id"] == scan
    gone = await api.client.get(f"{DOCUMENTS}/{stack}", headers=auth(owner))
    assert gone.status_code == 404
    await api.drain()
    files = (await api.client.get(f"{DOCUMENTS}/{scan}/files", headers=auth(owner))).json()
    kinds = [(item["number"], item["kind"]) for item in files["versions"]]
    assert kinds == [(1, "received"), (2, "received"), (3, "merged")]
    assert files["versions"][1]["detail"]["moved"]["document"] == stack


async def test_parts_that_do_not_fit_are_refused(api: Api) -> None:
    owner, stranger = await api.user(), await api.user()
    busy = await upload(api, auth(owner), drain=False)
    url = f"{DOCUMENTS}/{busy}/edit"
    turned = [{"pages": [{"page": 1, "rotate": 90}], "replaces": True}]
    processed = await api.client.post(url, **form(turned), headers=auth(owner))
    assert processed.status_code == 409
    assert processed.json()["reason"]["code"] == "being_processed"
    await api.drain()
    cases: list[tuple[Any, int]] = [
        ("not json", 422),
        ([{"pages": [{"page": 1, "rotate": 45}]}], 422),
        ([{"pages": []}], 422),
        ([{"pages": [{"page": 1}], "replaces": True}], 422),  # nothing changed
        ([{"pages": [{"page": 1}]}, {"pages": [{"page": 1}]}], 422),  # a page twice
        ([{"pages": [{"page": 2}]}], 422),  # a page it does not have
    ]
    for parts, status in cases:
        response = await api.client.post(url, **form(parts), headers=auth(owner))
        assert response.status_code == status, (parts, response.text)
    missing = await api.client.post(
        url, files=[("files", ("a.pdf", b"%PDF", "x"))], headers=auth(owner)
    )
    assert missing.status_code == 422
    [error] = missing.json()["errors"]
    assert (error["field"], error["reason"]["code"]) == ("parts", "input_missing")
    mail = b"From: a@example.org\r\nSubject: Hi\r\n\r\nHello\r\n"
    added = [{"pages": [{"page": 1}, {"source": 1, "page": 1}], "replaces": True}]
    refused = await api.client.post(url, **form(added, ("m.eml", mail)), headers=auth(owner))
    assert refused.status_code == 415
    hidden = await api.client.post(url, **form(turned), headers=auth(stranger))
    assert hidden.status_code == 404


async def test_the_pages_of_a_file_to_add_are_shown_not_stored(api: Api) -> None:
    owner, stranger = await api.user(), await api.user()
    id = await upload(api, auth(owner))
    url = f"{DOCUMENTS}/{id}/edit/pages"
    before = api.container.object_store.keys()  # type: ignore[attr-defined]
    response = await api.client.post(
        url, files=file_part("more.pdf", fake_pdf(1, "more")), headers=auth(owner)
    )
    assert response.status_code == 200, response.text
    [page] = response.json()["pages"]
    assert page.startswith("data:image/webp;base64,")
    assert api.container.object_store.keys() == before  # type: ignore[attr-defined]
    mail = b"From: a@example.org\r\nSubject: Hi\r\n\r\nHello\r\n"
    refused = await api.client.post(url, files=file_part("m.eml", mail), headers=auth(owner))
    assert refused.status_code == 415
    hidden = await api.client.post(
        url, files=file_part("more.pdf", fake_pdf(1, "more")), headers=auth(stranger)
    )
    assert hidden.status_code == 404
