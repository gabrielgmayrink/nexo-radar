"""Leitura do OpenAPI oficial para registrar os parâmetros documentados."""

from __future__ import annotations

import json
from typing import Any
from urllib.request import Request, urlopen

from radar.pncp import BASE_URL, USER_AGENT


def fetch_openapi(*, opener=urlopen, timeout: float = 20) -> dict[str, Any]:
    url = f"{BASE_URL}/v3/api-docs"
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with opener(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8-sig"))


def endpoint_contract(spec: dict[str, Any], path: str) -> list[dict[str, Any]]:
    operation = spec.get("paths", {}).get(path, {}).get("get", {})
    return [
        {
            "name": parameter.get("name"),
            "required": parameter.get("required", False),
            "description": parameter.get("description"),
            **parameter.get("schema", {}),
        }
        for parameter in operation.get("parameters", [])
    ]


def contract_snapshot(spec: dict[str, Any]) -> dict[str, Any]:
    paths = {
        "/v1/contratacoes/publicacao": endpoint_contract(spec, "/v1/contratacoes/publicacao"),
        "/v1/contratacoes/proposta": endpoint_contract(spec, "/v1/contratacoes/proposta"),
    }
    return {
        "openapi_version": spec.get("openapi"),
        "title": spec.get("info", {}).get("title"),
        "fetched_at": __import__("datetime").datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": f"{BASE_URL}/v3/api-docs",
        "endpoints": paths,
    }
