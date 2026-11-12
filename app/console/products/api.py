"""/api/products -- console management of Booqable products (product groups):
list, create, edit, delete. Booqable's DELETE on a product group *archives* it
(it disappears from the catalog and the receptionist but existing orders keep
their lines), so "delete" here is that archive.

Creation-only fields (`product_type`, `tracking_type`) are sent on create and
never on update -- Booqable rejects changing them. Prices cross the API in
dollars and are converted to Booqable's cents here. Booqable 404 -> 404, 422 ->
422 (its validation message is surfaced), anything else -> 502 (never
Booqable's own 401/403, which the console would mistake for an expired session).
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, field_validator

from app import config
from app.booking.booqable_client import BooqableClient, BooqableError
from app.console.auth import sessions as auth

logger = logging.getLogger(__name__)

router = APIRouter()

ProductType = Literal["rental", "sales_item", "service"]
TrackingType = Literal["none", "bulk", "trackable"]
PricePeriod = Literal["minute", "hour", "day", "week", "month"]


class ProductOut(BaseModel):
    id: str
    name: str | None = None
    sku: str | None = None
    description: str | None = None
    productType: str | None = None
    trackingType: str | None = None
    pricePeriod: str | None = None
    price: float = 0
    deposit: float = 0
    showInStore: bool = True
    booqableUrl: str


class ProductsPageOut(BaseModel):
    items: list[ProductOut]
    page: int
    pageSize: int
    total: int


class ProductUpdate(BaseModel):
    name: str | None = None
    sku: str | None = None
    description: str | None = None
    pricePeriod: PricePeriod | None = None
    price: float | None = None
    deposit: float | None = None
    showInStore: bool | None = None

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("name is required")
        return v.strip() if v is not None else v

    @field_validator("price", "deposit")
    @classmethod
    def _non_negative(cls, v: float | None) -> float | None:
        if v is not None and v < 0:
            raise ValueError("must not be negative")
        return v


class ProductCreate(ProductUpdate):
    name: str  # type: ignore[assignment]
    productType: ProductType = "rental"
    trackingType: TrackingType = "bulk"


def _cents(dollars: float) -> int:
    return round(dollars * 100)


def _attributes(body: ProductUpdate) -> dict[str, Any]:
    """Booqable attributes for only the fields the caller actually sent."""
    sent = body.model_dump(exclude_unset=True)
    mapping = {"name": "name", "sku": "sku", "description": "description",
               "pricePeriod": "price_period", "showInStore": "show_in_store"}
    attrs: dict[str, Any] = {mapping[k]: v for k, v in sent.items() if k in mapping}
    if sent.get("price") is not None:
        attrs["flat_fee_price_in_cents"] = _cents(sent["price"])
        attrs["price_type"] = "simple"
        attrs.setdefault("price_period", "day")
    if sent.get("deposit") is not None:
        attrs["deposit_in_cents"] = _cents(sent["deposit"])
    return attrs


def _to_out(resource: dict[str, Any]) -> ProductOut:
    a = resource.get("attributes") or {}
    return ProductOut(
        id=resource["id"],
        name=a.get("name"),
        sku=a.get("sku"),
        description=a.get("description"),
        productType=a.get("product_type"),
        trackingType=a.get("tracking_type"),
        pricePeriod=a.get("price_period"),
        price=(a.get("flat_fee_price_in_cents") or 0) / 100,
        deposit=(a.get("deposit_in_cents") or 0) / 100,
        showInStore=a.get("show_in_store") is not False,
        booqableUrl=f"{config.BOOQABLE_COMPANY_URL}/products/{resource['id']}",
    )


def _http_error(exc: Exception) -> HTTPException:
    logger.exception("Booqable product request failed")
    status = getattr(exc, "status_code", None)
    if isinstance(exc, BooqableError) and status == 404:
        return HTTPException(status_code=404, detail="Product not found")
    if isinstance(exc, BooqableError) and status == 422:
        return HTTPException(status_code=422, detail=str(exc))
    return HTTPException(status_code=502, detail=str(exc))


@router.get("/api/products", response_model=ProductsPageOut)
async def list_products(
    q: str = "",
    page: int = Query(1, ge=1),
    pageSize: int = Query(25, ge=1, le=100),
    _session=Depends(auth.require_auth),
) -> ProductsPageOut:
    try:
        groups = await BooqableClient().list_all("product_groups", params={"filter[archived][eq]": "false"})
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc
    rows = [_to_out(g) for g in groups]
    term = q.strip().lower()
    if term:
        rows = [r for r in rows if term in (r.name or "").lower() or term in (r.sku or "").lower()]
    rows.sort(key=lambda r: ((r.name or "").lower(), r.id))
    start = (page - 1) * pageSize
    return ProductsPageOut(items=rows[start : start + pageSize], page=page, pageSize=pageSize, total=len(rows))


@router.post("/api/products", response_model=ProductOut, status_code=201)
async def create_product(body: ProductCreate, _session=Depends(auth.require_auth)) -> ProductOut:
    attrs = _attributes(body)
    attrs["product_type"] = body.productType
    attrs["tracking_type"] = body.trackingType
    attrs["trackable"] = body.trackingType == "trackable"
    try:
        client = BooqableClient()
        result = await client.post("product_groups", json=client.resource("product_groups", attrs))
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc
    return _to_out(result["data"])


@router.put("/api/products/{product_id}", response_model=ProductOut)
async def update_product(
    product_id: str, body: ProductUpdate, _session=Depends(auth.require_auth)
) -> ProductOut:
    try:
        client = BooqableClient()
        result = await client.put(
            f"product_groups/{product_id}",
            json=client.resource("product_groups", _attributes(body), id=product_id),
        )
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc
    return _to_out(result["data"])


@router.delete("/api/products/{product_id}", status_code=204)
async def delete_product(product_id: str, _session=Depends(auth.require_auth)) -> Response:
    try:
        await BooqableClient().delete(f"product_groups/{product_id}")
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc
    return Response(status_code=204)
