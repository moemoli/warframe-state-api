"""warframe-api HTTP 客户端封装。

错误统一转 ApiError，.message 为可直接展示给用户文案。
"""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp


class ApiError(Exception):
    """上游/网络错误。str(e) 即用户可读文案。"""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ApiClient:
    """单例客户端；terminate() 时 close()。不做自动重试（上游已有缓存兜底）。"""

    def __init__(self, base: str, timeout: int = 15):
        self.base = base.rstrip("/")
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: aiohttp.ClientSession | None = None

    async def _ensure(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=self._timeout,
                headers={"User-Agent": "astrbot-plugin-warframe-helper/0.1"},
            )
        return self._session

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        """通用请求。2xx→json；error 字段/非2xx/网络错误 → ApiError。

        ServerDisconnectedError / ClientOSError：自动重建 session 重试一次。
        """
        import logging
        logger = logging.getLogger("wf.api")
        if not logger.handlers:
            try:
                _h = logging.FileHandler("/tmp/wf_api.log", encoding="utf-8")
                _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
                logger.addHandler(_h)
                logger.setLevel(logging.INFO)
            except OSError:
                pass
        url = f"{self.base}{path}"
        params = kwargs.pop("params", None)
        if params:
            params = {k: v for k, v in params.items() if v is not None}
        logger.info("%s %s params=%r extra=%r", method, path, params,
                    {k: ('***' if k.lower().endswith('key') else v)
                     for k, v in kwargs.items() if k != 'headers'})
        data = None
        status = 0
        last_err: Exception | None = None
        for attempt in range(2):
            try:
                session = aiohttp.ClientSession(timeout=self._timeout)
                try:
                    async with session.request(method, url, params=params, **kwargs) as resp:
                        status = resp.status
                        try:
                            data = await resp.json(content_type=None)
                        except Exception:
                            data = None
                        logger.info("resp status=%s len=%s", status,
                                    len(str(data)) if data is not None else "None")
                finally:
                    await session.close()
            except (aiohttp.ServerDisconnectedError, aiohttp.ClientOSError) as e:
                logger.warning("disconnect attempt=%s err=%r", attempt, e)
                last_err = e
                continue
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.warning("client err attempt=%s err=%r", attempt, e)
                raise ApiError(f"warframe-api 服务不可达（{e.__class__.__name__}）") from e
            break
        else:
            raise ApiError("warframe-api 连接断开（重试失败）") from last_err

        if isinstance(data, dict) and data.get("error"):
            raise ApiError(str(data["error"]))
        if status >= 400:
            raise ApiError(f"请求失败（HTTP {status}）")
        return data

    async def get(self, path: str, **params: Any) -> Any:
        """GET {base}{path}。"""
        q = {k: v for k, v in params.items() if v is not None}
        return await self._request("GET", path, params=q)

    async def post(self, path: str, json: Any = None, headers: dict | None = None) -> Any:
        """POST {base}{path}，JSON body。"""
        kw: dict[str, Any] = {"json": json}
        if headers:
            kw["headers"] = headers
        return await self._request("POST", path, **kw)

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
