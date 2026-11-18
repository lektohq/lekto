"""Health endpoint and the OpenAPI contract."""

import base64
import hashlib
import importlib
import json
import pkgutil
import re
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import httpx2
from pydantic import BaseModel

import lekto.adapters.inbound
from lekto.adapters.inbound.rest import (
    HEALTH_PATH,
    OIDC_CALLBACK_PATH,
    PREFIX,
    schemas,
)
from lekto.adapters.inbound.rest.app import DOCS_PATH, FAVICON_PATH, SWAGGER_PATH
from lekto.adapters.inbound.schemas import RequestBody
from tests.builders import PASSWORD, SECRET_KEY
from tests.unit.adapters.rest.support import Api, api_with

PROBLEM = "application/problem+json"


async def test_health_is_ok_without_authentication(api: Api) -> None:
    response = await api.client.get(f"{PREFIX}/health")
    assert response.status_code == 200
    checks = {"database": "ok", "object_store": "ok", "search": "ok"}
    assert response.json() == {"status": "ok", "checks": checks}


async def docs(ui_directory: Path | None) -> httpx2.Response:
    async with api_with(ui_directory=ui_directory) as api:
        return await api.client.get(DOCS_PATH)


async def test_the_api_documentation_comes_with_the_web_ui_not_a_cdn(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<!doctype html>", encoding="utf-8")
    response = await docs(tmp_path)
    assert response.status_code == 200
    page = response.text
    assert f'href="{FAVICON_PATH}"' in page
    assert f"url: '{PREFIX}/openapi.json'" in page
    assert "oauth2RedirectUrl" not in page
    assert f'src="{SWAGGER_PATH}/swagger-ui-bundle.js"' in page
    assert f'href="{SWAGGER_PATH}/swagger-ui.css"' in page
    assert "cdn." not in page
    # Only the page's own inline script runs, by its hash.
    (script,) = re.findall(r"<script>(.*?)</script>", page, re.DOTALL)
    digest = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
    policy = response.headers["content-security-policy"]
    assert f"script-src 'self' 'sha256-{digest}';" in policy
    assert "default-src 'none'" in policy
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["x-content-type-options"] == "nosniff"


async def test_without_the_web_ui_there_is_no_api_documentation() -> None:
    response = await docs(None)
    assert response.status_code == 404
    assert f"{PREFIX}/openapi.json" in response.text
    assert "<script" not in response.text


def test_the_description_names_the_scopes_and_the_tools_of_today(api: Api) -> None:
    description = api.app.openapi()["info"]["description"]
    for scope in ("`read`", "`upload`", "`read_write`"):
        assert scope in description
    for tool in ("`documents_search`", "`inbox_confirm`"):
        assert tool in description
    for gone in ("get_document", "get_text", "update_metadata", "list_tags"):
        assert gone not in description


def test_the_paths_known_outside_the_routes_are_routes(api: Api) -> None:
    """The access log filters and the OIDC redirect URI name these paths."""
    assert {HEALTH_PATH, OIDC_CALLBACK_PATH} <= set(api.app.openapi()["paths"])


async def test_a_failing_check_makes_the_api_unavailable() -> None:
    async def ok() -> None:
        pass

    async def broken() -> None:
        raise OSError("connection refused")

    async with api_with(health_checks={"database": broken, "object_store": ok}) as api:
        response = await api.client.get(f"{PREFIX}/health")
    assert response.status_code == 503
    assert response.json() == {
        "status": "unavailable",
        "checks": {"database": "failed", "object_store": "ok"},
    }


async def test_a_failing_search_only_degrades_the_api() -> None:
    async def ok() -> None:
        pass

    async def broken() -> None:
        raise OSError("connection refused")

    async def health(checks: dict[str, Callable[[], Awaitable[None]]]) -> httpx2.Response:
        async with api_with(health_checks=checks) as api:
            return await api.client.get(f"{PREFIX}/health")

    degraded = await health({"database": ok, "search": broken})
    assert degraded.status_code == 200
    assert degraded.json() == {
        "status": "degraded",
        "checks": {"database": "ok", "search": "failed"},
    }
    down = await health({"database": broken, "search": broken})
    assert (down.status_code, down.json()["status"]) == (503, "unavailable")


async def openapi(api: Api) -> dict[str, Any]:
    response = await api.client.get(f"{PREFIX}/openapi.json")
    assert response.status_code == 200
    schema: dict[str, Any] = response.json()
    return schema


async def test_every_list_in_a_request_body_has_a_limit(api: Api) -> None:
    """Pydantic finds an error for every bad item of a list: a list without `maxItems` would let
    a body of a megabyte make a hundred thousand of them."""
    schema = await openapi(api)
    components = schema["components"]["schemas"]
    unbounded: set[str] = set()

    def walk(node: dict[str, Any], where: str, seen: frozenset[str]) -> None:
        if "$ref" in node:
            name = node["$ref"].rsplit("/", 1)[-1]
            if name not in seen:
                walk(components[name], name, seen | {name})
            return
        for key in ("anyOf", "oneOf", "allOf"):
            for item in node.get(key, []):
                walk(item, where, seen)
        if node.get("type") == "array":
            if "maxItems" not in node:
                unbounded.add(where)
            walk(node.get("items", {}), f"{where}[]", seen)
        for name, item in node.get("properties", {}).items():
            walk(item, f"{where}.{name}", seen)
        if isinstance(node.get("additionalProperties"), dict):
            walk(node["additionalProperties"], f"{where}{{}}", seen)

    for path, methods in schema["paths"].items():
        for method, operation in methods.items():
            for content in operation.get("requestBody", {}).get("content", {}).values():
                if "schema" in content:
                    walk(content["schema"], f"{method.upper()} {path}", frozenset())
    assert not unbounded


async def test_every_object_in_a_request_body_refuses_unknown_keys(api: Api) -> None:
    """`extra="forbid"` ([[security-baseline]]): a mistyped key is refused (422), not dropped,
    also in an object within a body (RA-02, RB-06)."""
    schema = await openapi(api)
    components = schema["components"]["schemas"]
    lenient: set[str] = set()

    def walk(node: dict[str, Any], where: str, seen: frozenset[str]) -> None:
        if "$ref" in node:
            name = node["$ref"].rsplit("/", 1)[-1]
            if name not in seen:
                walk(components[name], name, seen | {name})
            return
        for key in ("anyOf", "oneOf", "allOf"):
            for item in node.get(key, []):
                walk(item, where, seen)
        if node.get("properties") and node.get("additionalProperties") is not False:
            lenient.add(where)
        if "items" in node:
            walk(node["items"], f"{where}[]", seen)
        for name, item in node.get("properties", {}).items():
            walk(item, f"{where}.{name}", seen)
        if isinstance(node.get("additionalProperties"), dict):
            walk(node["additionalProperties"], f"{where}{{}}", seen)

    for path, methods in schema["paths"].items():
        for method, operation in methods.items():
            content = operation.get("requestBody", {}).get("content", {})
            if "application/json" in content:
                walk(content["application/json"]["schema"], f"{method.upper()} {path}", frozenset())
    assert not lenient


async def test_one_response_model_per_shape(api: Api) -> None:
    """Two answers of the same fields share one model, so the generated client has one type
    for them; what a copy would describe goes to the field that uses it (RA-12)."""
    components = (await openapi(api))["components"]["schemas"]
    loose = {"description", "title", "examples", "default"}
    shapes: dict[str, list[str]] = {}
    for name, schema in components.items():
        if name.endswith("Out") and schema.get("properties"):
            fields = {
                key: {k: v for k, v in value.items() if k not in loose}
                for key, value in schema["properties"].items()
            }
            shape = json.dumps([fields, sorted(schema.get("required", []))], sort_keys=True)
            shapes.setdefault(shape, []).append(name)
    assert [names for names in shapes.values() if len(names) > 1] == []


def _models() -> dict[str, list[type[BaseModel]]]:
    found: dict[str, list[type[BaseModel]]] = {}
    for info in pkgutil.walk_packages(lekto.adapters.inbound.__path__, "lekto.adapters.inbound."):
        module = importlib.import_module(info.name)
        for item in vars(module).values():
            if (
                isinstance(item, type)
                and issubclass(item, BaseModel)
                and item.__module__ == info.name
            ):
                found.setdefault(item.__name__, []).append(item)
    return found


async def test_every_json_body_of_the_api_is_a_request_body(api: Api) -> None:
    """So no route's body is left without the checks of `RequestBody` (RB-08)."""
    models = _models()
    names: set[str] = set()
    for methods in (await openapi(api))["paths"].values():
        for operation in methods.values():
            content = operation.get("requestBody", {}).get("content", {})
            if "application/json" in content:
                schema = content["application/json"]["schema"]
                refs = [schema, *schema.get("anyOf", []), *schema.get("oneOf", [])]
                names.update(ref["$ref"].rsplit("/", 1)[-1] for ref in refs if "$ref" in ref)
    assert names
    lenient = {name for name in names if not all(issubclass(m, RequestBody) for m in models[name])}
    assert not lenient


async def test_errors_are_documented_as_problems_with_examples(api: Api) -> None:
    schema = await openapi(api)
    for path, item in schema["paths"].items():
        for method, operation in item.items():
            assert operation.get("summary"), (path, method)
            for status, response in operation["responses"].items():
                if not status.startswith(("4", "5")) or path.endswith("/health"):
                    continue
                content = response["content"]
                assert list(content) == [PROBLEM], (path, method, status)
                assert content[PROBLEM]["schema"] == {"$ref": "#/components/schemas/Problem"}
                assert content[PROBLEM]["example"]["status"] == int(status)
    upload = schema["paths"][f"{PREFIX}/documents"]["post"]
    statuses = {"202", "400", "401", "403", "404", "409", "413", "415", "422", "500"}
    assert set(upload["responses"]) == statuses
    problem = schema["components"]["schemas"]["Problem"]["properties"]
    assert {"type", "title", "status", "detail", "existing_document_id"} <= set(problem)
    assert "HTTPValidationError" not in schema["components"]["schemas"]
    assert "HTTPValidationError" not in str(schema["paths"])


async def test_the_upload_body_is_multipart(api: Api) -> None:
    body = (await openapi(api))["paths"][f"{PREFIX}/documents"]["post"]["requestBody"]
    form = body["content"]["multipart/form-data"]["schema"]
    assert form["required"] == ["file"]
    assert form["properties"]["file"] == {
        "type": "string",
        "format": "binary",
        "description": "PDF, JPEG, PNG, TIFF or a mail (`.eml`); recognised by content.",
    }
    assert form["properties"]["space_id"]["format"] == "uuid"


async def test_schemas_of_status_log_and_events(api: Api) -> None:
    schema = await openapi(api)
    schemas = schema["components"]["schemas"]
    assert {"DocumentDetails", "DocumentAccepted", "LogEntry", "EventMessage", "Health"} <= set(
        schemas
    )
    reprocess = schemas["ReprocessRequest"]["properties"]["from_node"]
    node = schemas[reprocess["$ref"].rsplit("/", 1)[1]]
    assert "receive" not in node["enum"]
    resume = schemas["ConfirmRequest"]["properties"]["resume_at"]
    resume_at = schemas[resume["$ref"].rsplit("/", 1)[1]]
    assert resume_at["enum"] == ["fields", "apply_rules"]
    events = schema["paths"][f"{PREFIX}/events"]["get"]["responses"]["200"]["content"]
    stream = events["text/event-stream"]
    assert stream["schema"]["type"] == "string"
    data = stream["itemSchema"]["properties"]["data"]
    assert data["contentSchema"] == {"$ref": "#/components/schemas/EventMessage"}
    assert "$ref" not in stream["itemSchema"]


async def test_every_operation_declares_its_security(api: Api) -> None:
    schema = await openapi(api)
    schemes = schema["components"]["securitySchemes"]
    assert schemes["session"]["type"] == "apiKey" and schemes["session"]["in"] == "cookie"
    assert schemes["token"] == {
        "type": "http",
        "scheme": "bearer",
        "description": schemes["token"]["description"],
    }
    allowed: list[list[dict[str, list[str]]]] = [
        [],
        [{"session": []}],
        [{"session": []}, {"token": []}],
        [{"taskToken": []}],  # answering a task
        [{"fileSignature": []}],  # a file of a model call's document
    ]
    for path, item in schema["paths"].items():
        for method, operation in item.items():
            security = operation["security"]
            assert security in allowed, (path, method)
            responses = operation["responses"]
            if security:
                assert "401" in responses, (path, method)
            if security == [{"session": []}]:
                assert "403" in responses, (path, method)
            assert "500" in responses or path.endswith("/health"), (path, method)
            assert operation.get("summary"), (path, method)


async def test_bodies_and_answers_are_described(api: Api) -> None:
    schema = await openapi(api)
    components = schema["components"]["schemas"]
    for name in ("LoginRequest", "SessionOut", "Me", "TokenCreated", "DocumentDetails"):
        assert name in components, name
    for path, item in schema["paths"].items():
        for method, operation in item.items():
            for status, response in operation["responses"].items():
                assert response.get("description"), (path, method, status)
    login = schema["paths"][f"{PREFIX}/auth/login"]["post"]
    assert set(login["responses"]) >= {"200", "401", "413", "415", "422", "429", "500"}
    for path, item in schema["paths"].items():
        for method, operation in item.items():
            if "requestBody" in operation:
                assert "413" in operation["responses"], (path, method)
    assert login["requestBody"]["content"]["application/json"]


async def test_refusals_are_described(api: Api) -> None:
    """Every protected change may be refused (a `read` token, no CSRF header): 403. A task's
    token answers its task only."""
    schema = await openapi(api)
    for path, item in schema["paths"].items():
        for method, operation in item.items():
            if operation["security"] not in ([], [{"taskToken": []}]) and method != "get":
                assert "403" in operation["responses"], (path, method)
    me = schema["paths"][f"{PREFIX}/auth/tokens"]["get"]
    assert "403" in me["responses"]  # session only


async def test_request_bodies_have_examples(api: Api) -> None:
    schema = await openapi(api)
    components = schema["components"]["schemas"]
    for path, item in schema["paths"].items():
        for method, operation in item.items():
            content = operation.get("requestBody", {}).get("content", {})
            if "application/json" in content:
                body = content["application/json"]["schema"]
                # An optional body (deleting a user) is any of the model or nothing.
                ref = body.get("$ref") or next(
                    item["$ref"] for item in body.get("anyOf", []) if "$ref" in item
                )
                name = ref.rsplit("/", 1)[-1]
                assert components[name].get("examples"), (path, method, name)


def test_examples_are_valid_bodies() -> None:
    modules = [
        importlib.import_module(f"{schemas.__name__}.{name}")
        for _, name, _ in pkgutil.iter_modules(schemas.__path__)
    ]
    models = {
        model
        for module in modules
        for model in vars(module).values()
        if isinstance(model, type) and issubclass(model, BaseModel) and model is not BaseModel
    }
    for model in models:
        extra = model.model_config.get("json_schema_extra")
        examples = extra.get("examples", []) if isinstance(extra, dict) else []
        assert isinstance(examples, list), model
        for example in examples:
            model.model_validate(example)


async def test_no_secrets_in_the_contract(api: Api) -> None:
    """Examples are placeholders; nothing of the test configuration leaks into the document."""
    text = json.dumps(await openapi(api))
    for secret in (PASSWORD, SECRET_KEY):
        assert secret not in text
    assert not re.search(r"lekto_[A-Za-z0-9_-]{20,}", text)
    assert "BEGIN" not in text and "PRIVATE" not in text
    assert (
        "password"
        not in json.dumps(
            [
                example
                for item in json.loads(text)["paths"].values()
                for operation in item.values()
                for response in operation["responses"].values()
                for content in response.get("content", {}).values()
                for example in [content.get("example")]
                if example
            ]
        ).lower()
    )
