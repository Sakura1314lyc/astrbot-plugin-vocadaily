import os
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

import aiohttp

_IMPORT_CWD = os.getcwd()
_ASTRBOT_IMPORT_DIR = tempfile.TemporaryDirectory()
os.chdir(_ASTRBOT_IMPORT_DIR.name)
try:
    import main
finally:
    os.chdir(_IMPORT_CWD)


class PluginRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_search_falls_back_to_html_and_caches_result(self):
        service = main.BiliMediaService(
            {
                "search_count": 20,
                "search_cache_minutes": 10,
            },
            {},
        )
        service._search_api = AsyncMock(side_effect=main.MediaError("HTTP 412"))
        expected = [
            {
                "bvid": "BV0000000001",
                "title": "天ノ弱／164 feat.GUMI【Official】",
            }
        ]
        service._search_html = AsyncMock(return_value=expected)

        first = await service.search("天ノ弱")
        second = await service.search("天ノ弱")

        self.assertEqual(first, expected)
        self.assertEqual(second, expected)
        service._search_api.assert_awaited_once()
        service._search_html.assert_awaited_once()

    async def test_direct_bvid_bypasses_search(self):
        service = main.BiliMediaService({}, {})
        service.enrich = AsyncMock(
            return_value={
                "bvid": "BV1CK4y1Y7r1",
                "title": "天ノ弱／164 feat.GUMI【Official】",
            }
        )
        service.search = AsyncMock()

        tracks = await service.find_candidates("https://b23.tv/BV1CK4y1Y7r1")

        self.assertEqual(tracks[0]["search_match"], "bvid")
        service.search.assert_not_awaited()

    async def test_internal_media_server_serves_cache_file(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]

        plugin = object.__new__(main.JRSQPlugin)
        plugin.media_config = {
            "delivery_mode": "url",
            "serve_host": "127.0.0.1",
            "serve_port": port,
            "public_base_url": f"http://127.0.0.1:{port}",
        }
        plugin._media_runner = None
        plugin._media_token = "test-token"
        plugin._media_public_base_url = ""
        test_file = main.CACHE_DIR / "runtime-test.mp4"
        test_file.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"0" * 2048)
        try:
            await plugin._start_media_server()
            url = plugin._media_url(Path(test_file))
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"http://127.0.0.1:{port}/jrsq-health"
                ) as health_response:
                    health = await health_response.json()
                async with session.get(url) as response:
                    body = await response.read()
            self.assertEqual(health_response.status, 200)
            self.assertEqual(health["status"], "ok")
            self.assertEqual(response.status, 200)
            self.assertEqual(body, test_file.read_bytes())
        finally:
            await plugin._stop_media_server()
            test_file.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
