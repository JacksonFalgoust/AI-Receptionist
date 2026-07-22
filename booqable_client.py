from __future__ import annotations

from typing import Any

import httpx

import config


class BooqableError(Exception):
    def __init__(self, message: str, status_code: int | None = None, payload: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class BooqableClient:
    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        self.base_url = (base_url or config.BOOQABLE_BASE_URL).rstrip("/")
        self.api_key = api_key or config.BOOQABLE_API_KEY
        if not self.api_key:
            raise BooqableError("BOOQABLE_API_KEY is not configured")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.request(
                method,
                url,
                headers=self._headers(),
                params=params,
                json=json,
            )

        try:
            body = response.json()
        except Exception:
            body = {"raw": response.text}

        if response.status_code >= 400:
            detail = body.get("errors") if isinstance(body, dict) else body
            raise BooqableError(
                f"Booqable {method} {path} failed ({response.status_code}): {detail}",
                status_code=response.status_code,
                payload=body,
            )
        return body if isinstance(body, dict) else {"data": body}

    async def get(self, path: str, **kwargs: Any) -> dict[str, Any]:
        return await self.request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> dict[str, Any]:
        return await self.request("POST", path, **kwargs)

    async def put(self, path: str, **kwargs: Any) -> dict[str, Any]:
        return await self.request("PUT", path, **kwargs)

    async def list_all(
        self,
        path: str,
        *,
        page_size: int = 50,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        page = 1
        base_params = dict(params or {})
        while True:
            query = {
                **base_params,
                "page[number]": page,
                "page[size]": page_size,
            }
            payload = await self.get(path, params=query)
            data = payload.get("data") or []
            if isinstance(data, dict):
                results.append(data)
                break
            results.extend(data)
            if len(data) < page_size:
                break
            page += 1
        return results

    @staticmethod
    def resource(type_name: str, attributes: dict[str, Any], id: str | None = None) -> dict[str, Any]:
        data: dict[str, Any] = {"type": type_name, "attributes": attributes}
        if id:
            data["id"] = id
        return {"data": data}

    @staticmethod
    def attrs(resource: dict[str, Any]) -> dict[str, Any]:
        return resource.get("attributes") or {}

    @staticmethod
    def sid(resource: dict[str, Any] | None) -> str | None:
        if not resource:
            return None
        return resource.get("id")
