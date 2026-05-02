#!/usr/bin/env python3
"""Arkham API client and response normalization helpers."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional


REQUEST_TIMEOUT = 20
BASE_URL = "https://api.arkm.com"


class ArkhamError(RuntimeError):
    """Raised when the Arkham API returns an error."""


class ArkhamClient:
    def __init__(self, api_key: str, timeout: int = REQUEST_TIMEOUT):
        if not api_key:
            raise ArkhamError("Missing ARKHAM_API_KEY.")
        self.api_key = api_key
        self.timeout = timeout

    def _request(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{BASE_URL}{path}"
        if params:
            query = urllib.parse.urlencode(
                {key: value for key, value in params.items() if value is not None},
                doseq=True,
            )
            url = f"{url}?{query}"

        request = urllib.request.Request(
            url,
            headers={
                "API-Key": self.api_key,
                "Accept": "application/json",
                "User-Agent": "token-control-monitor/1.0",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise ArkhamError(f"Arkham API HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise ArkhamError(f"Arkham API connection failed: {exc.reason}") from exc

        try:
            return json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ArkhamError("Arkham API returned invalid JSON.") from exc

    def search(self, query: str) -> Dict[str, Any]:
        return self._request(
            "/intelligence/search",
            params={"query": query, "filterLimits": json.dumps({"arkhamEntities": 10, "tokens": 10})},
        )

    def get_token_addresses(self, pricing_id: str) -> Dict[str, Any]:
        return self._request(f"/token/addresses/{pricing_id}")

    def resolve_token(self, query: str) -> Dict[str, Any]:
        candidates = self.search_tokens(query)
        normalized = query.strip().lower()

        exact = [
            candidate for candidate in candidates
            if normalized in {
                str(candidate.get("symbol", "")).lower(),
                str(candidate.get("name", "")).lower(),
                str(candidate.get("pricing_id", "")).lower(),
            }
        ]

        if len(exact) == 1:
            selected = exact[0]
            addresses = selected.get("addresses", {}) or {}
            if isinstance(addresses, dict) and len(addresses) > 1:
                return {
                    "status": "ambiguous",
                    "reason": "multiple_chains",
                    "selected": selected,
                    "candidates": candidates,
                }
            return {"status": "resolved", "selected": selected, "candidates": candidates}
        if len(candidates) == 1:
            selected = candidates[0]
            addresses = selected.get("addresses", {}) or {}
            if isinstance(addresses, dict) and len(addresses) > 1:
                return {
                    "status": "ambiguous",
                    "reason": "multiple_chains",
                    "selected": selected,
                    "candidates": candidates,
                }
            return {"status": "resolved", "selected": selected, "candidates": candidates}
        if candidates:
            return {"status": "ambiguous", "selected": None, "candidates": candidates}
        return {"status": "not_found", "selected": None, "candidates": []}

    def search_tokens(self, query: str) -> List[Dict[str, Any]]:
        results = self.search(query)
        candidates: List[Dict[str, Any]] = []
        for token in results.get("tokens", []):
            identifier = token.get("identifier", {}) or {}
            candidate = {
                "name": token.get("name", ""),
                "symbol": token.get("symbol", ""),
                "pricing_id": identifier.get("pricingID", ""),
                "chain": identifier.get("chain", ""),
                "token_address": identifier.get("address", ""),
            }
            if candidate["name"] or candidate["symbol"] or candidate["token_address"] or candidate["pricing_id"]:
                if candidate["pricing_id"] and (not candidate["chain"] or not candidate["token_address"]):
                    try:
                        addresses = self.get_token_addresses(candidate["pricing_id"])
                    except ArkhamError:
                        addresses = {}
                    if isinstance(addresses, dict) and addresses:
                        preferred_chain = candidate["chain"] if candidate["chain"] in addresses else ""
                        if preferred_chain:
                            candidate["token_address"] = addresses.get(preferred_chain, candidate["token_address"])
                        else:
                            chain_name, address = next(iter(addresses.items()))
                            candidate["chain"] = chain_name
                            candidate["token_address"] = address
                        candidate["addresses"] = addresses
                candidates.append(candidate)
        return candidates

    def get_token_info(self, chain: str, token_address: str) -> Dict[str, Any]:
        return self._request(f"/intelligence/token/{chain}/{token_address}")

    def get_token_holders(self, chain: str, token_address: str, limit: int = 20) -> Dict[str, Any]:
        return self._request(
            f"/token/holders/{chain}/{token_address}",
            params={"limit": limit},
        )

    def get_recent_transfers(
        self,
        chain: str,
        token_address: str,
        time_last: str = "24h",
        usd_gte: Optional[float] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        return self._request(
            "/transfers",
            params={
                "chains": chain,
                "tokens": token_address,
                "timeLast": time_last,
                "usdGte": usd_gte,
                "limit": limit,
                "sortKey": "time",
                "sortDir": "desc",
            },
        )

    def get_address_intelligence(self, address: str) -> Dict[str, Any]:
        return self._request(f"/intelligence/address/{address}")

    def get_address_transfers(
        self,
        chain: str,
        address: str,
        limit: int = 20,
    ) -> Dict[str, Any]:
        return self._request(
            "/transfers",
            params={
                "chains": chain,
                "base": address,
                "timeLast": "24h",
                "limit": limit,
                "sortKey": "time",
                "sortDir": "desc",
            },
        )


def _extract_name(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("name", ""))
    return str(value or "")


def parse_transfer(transfer: Dict[str, Any]) -> Dict[str, Any]:
    from_data = transfer.get("from", {}) or transfer.get("fromAddress", {}) or {}
    to_data = transfer.get("to", {}) or transfer.get("toAddress", {}) or {}
    from_entity = _extract_name(from_data.get("entity") or from_data.get("arkhamEntity"))
    to_entity = _extract_name(to_data.get("entity") or to_data.get("arkhamEntity"))
    from_label = _extract_name(from_data.get("label") or from_data.get("arkhamLabel") or from_data.get("name"))
    to_label = _extract_name(to_data.get("label") or to_data.get("arkhamLabel") or to_data.get("name"))

    return {
        "tx_hash": transfer.get("txHash", "") or transfer.get("transactionHash", "") or transfer.get("id", ""),
        "blockchain": transfer.get("blockchain", "") or transfer.get("chain", ""),
        "from_address": from_data.get("address", ""),
        "from_entity": from_entity,
        "from_label": from_label,
        "to_address": to_data.get("address", ""),
        "to_entity": to_entity,
        "to_label": to_label,
        "amount": float(transfer.get("amount", 0) or transfer.get("unitValue", 0) or 0),
        "amount_usd": float(transfer.get("amountUSD", 0) or transfer.get("historicalUSD", 0) or 0),
        "timestamp": transfer.get("timestamp", "") or transfer.get("blockTimestamp", ""),
        "token_symbol": transfer.get("token", {}).get("symbol", "") or transfer.get("tokenSymbol", ""),
    }


def shorten_label(label: str, fallback: str, width: int = 10) -> str:
    if label:
        return label
    return f"{fallback[:width]}..." if fallback else "Unknown"


def normalize_token_info(info: Dict[str, Any]) -> Dict[str, Any]:
    identifier = info.get("identifier", {}) or {}
    return {
        "chain": identifier.get("chain", ""),
        "token_address": identifier.get("address", ""),
        "pricing_id": identifier.get("pricingID", ""),
        "name": info.get("name", ""),
        "symbol": info.get("symbol", ""),
        "tv_ticker": info.get("tvTicker", ""),
    }


def normalize_holders(payload: Dict[str, Any], chain: str, limit: int) -> List[Dict[str, Any]]:
    top = ((payload.get("addressTopHolders", {}) or {}).get(chain, []) or [])[:limit]
    rows: List[Dict[str, Any]] = []
    for item in top:
        address_block = item.get("address", {}) or {}
        rows.append(
            {
                "address": address_block.get("address", ""),
                "entity": _extract_name(address_block.get("arkhamEntity")),
                "label": _extract_name(address_block.get("arkhamLabel")),
                "balance": item.get("balance", 0),
                "usd": item.get("usd", 0),
                "pct_of_cap": item.get("pctOfCap", 0),
            }
        )
    return rows


def normalize_address_intelligence(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "address": payload.get("address", ""),
        "entity": _extract_name(payload.get("arkhamEntity") or payload.get("entity")),
        "label": _extract_name(payload.get("arkhamLabel") or payload.get("label")),
        "is_contract": payload.get("contract", False),
        "is_user_address": payload.get("isUserAddress", False),
        "chain": payload.get("chain", ""),
    }
