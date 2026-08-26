"""html_render: template -> t2i -> QQ CDN chunked upload -> markdown image."""

from __future__ import annotations

import time
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from astrbot.api import logger
from astrbot.api.message_components import Image
from astrbot.core.message.message_event_result import MessageEventResult


class RenderBreaker:
    def __init__(self, threshold: int = 3, cooldown: int = 300):
        self.threshold = threshold
        self.cooldown = cooldown
        self._fails = 0
        self._until = 0.0

    def fail(self):
        self._fails += 1
        if self._fails >= self.threshold:
            self._until = time.time() + self.cooldown
            logger.warning(f"[wf] breaker: {self._fails} fails, cooldown {self.cooldown}s")

    def ok(self):
        self._fails = 0
        self._until = 0.0

    def tripped(self) -> bool:
        if self._until and time.time() < self._until:
            return True
        if self._until:
            self._until = 0.0
            self._fails = 0
        return False


class Renderer:
    """Jinja2 -> t2i -> QQ CDN chunked upload -> markdown image.

    QQ markdown image URL must be on QQ CDN whitelist (raw_url).
    We use QQ file upload chunked flow to obtain raw_url:
      1. upload_prepare -> upload_id + pre-signed URLs
      2. PUT chunks to pre-signed URLs
      3. upload_part_finish for each chunk
      4. merge with upload_id -> raw_url
    """

    def __init__(self, tmpl_dir: Path | str, mode: str = "auto", theme: str = "dark"):
        self.base_dir = Path(tmpl_dir)
        self.mode = (mode or "auto").lower()
        self.theme = (theme or "dark").lower()
        self.breaker = RenderBreaker()
        self._tmpl_dir = self.base_dir / self.theme
        if not self._tmpl_dir.is_dir():
            self._tmpl_dir = self.base_dir
        self._env = Environment(
            loader=FileSystemLoader(str(self._tmpl_dir)),
            autoescape=select_autoescape(["html"]),
        )

    def render_sync(self, tpl_name: str, vm: dict) -> str | None:
        name = tpl_name if tpl_name.endswith(".html") else f"{tpl_name}.html"
        try:
            tmpl = self._env.get_template(name)
            return tmpl.render(theme=self.theme, **vm)
        except Exception as e:
            logger.error(f"[wf] template failed {name}: {e}")
            return None


    async def render(self, star, context, event, tpl_name: str, vm: dict, flags):
        """Render template -> t2i -> image message.

        QQ official bot markdown image URLs are whitelist-restricted to
        Tencent's own resource buckets.  Bot-uploaded files (raw_url from the
        file upload API) are served as application/octet-stream from a bucket
        that is NOT whitelisted, so ![url](...) markdown never renders.

        Therefore we return an Image-component chain: AstrBot's adapter
        uploads via file_info and sends it as a proper media message, which
        QQ always displays correctly.
        """
        if getattr(self, "mode", "auto") == "text":
            return None
        if flags.plain_text and not flags.force_image:
            return None
        if self.breaker.tripped():
            if flags.force_image:
                raise RuntimeError("render unavailable (breaker)")
            return None

        html = self.render_sync(tpl_name, vm)
        if not html:
            return None

        for attempt in (1, 2):
            try:
                t2i_url = await star.html_render(
                    html, {}, return_url=True,
                    options={"full_page": True, "type": "png", "quality": 80},
                )
                if not t2i_url:
                    raise RuntimeError("t2i empty URL")

                self.breaker.ok()

                result = MessageEventResult(chain=[Image.fromURL(t2i_url)])
                return result

            except Exception as e:
                self.breaker.fail()
                logger.warning(f"[wf] render({attempt}/2) {tpl_name}: {e}")
                if attempt == 2 and flags.force_image:
                    raise RuntimeError("render failed") from e
                if attempt == 2:
                    return None
        return None
