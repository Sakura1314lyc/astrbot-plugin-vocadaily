import os
import socket
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import aiohttp
from aiohttp import web

_IMPORT_CWD = os.getcwd()
_ASTRBOT_IMPORT_DIR = tempfile.TemporaryDirectory()
os.chdir(_ASTRBOT_IMPORT_DIR.name)
try:
    import main
finally:
    os.chdir(_IMPORT_CWD)


class PluginRuntimeTests(unittest.IsolatedAsyncioTestCase):
    def test_review_cautions_detect_version_content_and_short_clip(self):
        cautions = main._derive_review_cautions(
            {
                "title": "【AI翻唱／猎奇慎入】测试曲",
                "tags": ["cover", "恐怖", "血腥"],
                "duration": 34,
                "search_match": "metadata",
                "search_score": 110,
            }
        )

        self.assertTrue(any("翻唱" in item for item in cautions))
        self.assertTrue(any("不适" in item for item in cautions))
        self.assertTrue(any("不足 50 秒" in item for item in cautions))
        self.assertTrue(any("不确定性" in item for item in cautions))

    def test_review_cautions_recognize_known_sexual_theme_titles(self):
        for title in (
            "【原版】威風堂々",
            "【官方 MV/中字版】惊喜爱/哦吼爱 オッホ愛",
        ):
            with self.subTest(title=title):
                cautions = main._derive_review_cautions(
                    {
                        "title": title,
                        "tags": ["VOCALOID"],
                        "duration": 180,
                        "search_match": "title",
                        "search_score": 190,
                    }
                )
                self.assertTrue(any("性暗示" in item for item in cautions))

    async def test_known_sensitive_song_review_cannot_stay_generic_positive(self):
        provider = SimpleNamespace(
            text_chat=AsyncMock(
                side_effect=[
                    SimpleNamespace(
                        completion_text="节奏充满活力，华丽电子编曲特别抓耳，值得循环。"
                    ),
                    SimpleNamespace(
                        completion_text="这首的电子编排很抓耳，我挺喜欢；不过喘息拟声和性暗示也是核心表达，题材接受度会因人而异。"
                    ),
                ]
            )
        )
        plugin = object.__new__(main.JRSQPlugin)
        plugin.review_config = {"enabled": True, "max_chars": 100}
        plugin.context = SimpleNamespace(get_using_provider=lambda _origin: provider)

        review = await plugin._generate_review(
            SimpleNamespace(unified_msg_origin="group:test"),
            "威风堂堂",
            {
                "title": "【原版】威風堂々",
                "tags": ["VOCALOID"],
                "duration": 213,
            },
            "B站",
        )

        self.assertIn("性暗示", review)
        self.assertIn("挺喜欢", review)
        self.assertEqual(provider.text_chat.await_count, 2)

    async def test_problematic_review_is_retried_when_model_only_praises(self):
        provider = SimpleNamespace(
            text_chat=AsyncMock(
                side_effect=[
                    SimpleNamespace(completion_text="旋律甜美可爱，听完心情都会变好。"),
                    SimpleNamespace(
                        completion_text="这是翻唱版本，调声显得生硬，不能替代原曲本家的表达。"
                    ),
                ]
            )
        )
        plugin = object.__new__(main.JRSQPlugin)
        plugin.review_config = {"enabled": True, "max_chars": 100}
        plugin.context = SimpleNamespace(get_using_provider=lambda _origin: provider)
        event = SimpleNamespace(unified_msg_origin="group:test")

        review = await plugin._generate_review(
            event,
            "测试曲",
            {
                "title": "【AI翻唱】测试曲",
                "tags": ["cover"],
                "duration": 180,
            },
            "B站",
        )

        self.assertIn("翻唱", review)
        self.assertIn("生硬", review)
        self.assertEqual(provider.text_chat.await_count, 2)
        self.assertIn("上一版短评需要校正", provider.text_chat.await_args_list[1].kwargs["prompt"])

    async def test_problematic_review_uses_fallback_after_two_evasive_answers(self):
        provider = SimpleNamespace(
            text_chat=AsyncMock(
                side_effect=[
                    SimpleNamespace(completion_text="真是一首可爱又治愈的作品。"),
                    SimpleNamespace(completion_text="听起来很甜，特别值得推荐。"),
                ]
            )
        )
        plugin = object.__new__(main.JRSQPlugin)
        plugin.review_config = {"enabled": True, "max_chars": 100}
        plugin.context = SimpleNamespace(get_using_provider=lambda _origin: provider)

        review = await plugin._generate_review(
            SimpleNamespace(unified_msg_origin="group:test"),
            "测试曲",
            {
                "title": "【猎奇慎入】测试曲",
                "tags": ["恐怖", "血腥"],
                "duration": 180,
            },
            "B站",
        )

        self.assertIn("需要说清楚", review)
        self.assertIn("不适", review)
        self.assertEqual(provider.text_chat.await_count, 2)

    async def test_normal_song_length_cannot_be_used_as_forced_criticism(self):
        provider = SimpleNamespace(
            text_chat=AsyncMock(
                side_effect=[
                    SimpleNamespace(
                        completion_text=(
                            "轻快编曲有淡淡情感，不过短短的时长限制让情绪显得仓促，"
                            "调声没有亮点，整体略显平淡。"
                        )
                    ),
                    SimpleNamespace(
                        completion_text=(
                            "轻快的编曲和清爽调声很贴合月色主题，我会把它当作一首耐听的小品曲。"
                        )
                    ),
                ]
            )
        )
        plugin = object.__new__(main.JRSQPlugin)
        plugin.review_config = {"enabled": True, "max_chars": 100}
        plugin.context = SimpleNamespace(get_using_provider=lambda _origin: provider)

        review = await plugin._generate_review(
            SimpleNamespace(unified_msg_origin="group:test"),
            "好想听你说月色真美",
            {
                "title": "【本家】月が綺麗ねと言われたい！ - 初音ミク",
                "tags": ["VOCALOID", "初音ミク", "原创曲"],
                "duration": 147,
                "search_match": "title",
                "search_score": 220,
                "search_original": True,
            },
            "B站",
        )

        self.assertIn("耐听", review)
        self.assertNotIn("仓促", review)
        self.assertEqual(provider.text_chat.await_count, 2)
        retry_prompt = provider.text_chat.await_args_list[1].kwargs["prompt"]
        self.assertIn("属于正常单曲范围", retry_prompt)
        self.assertIn("语气失衡", retry_prompt)

    def test_invalid_config_section_falls_back_to_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "plugin_config.json"
            config_path.write_text(
                '{"bilibili": "broken", "review": {"enabled": false}, '
                '"push": {"target_umos": "not-a-list"}}',
                encoding="utf-8",
            )
            with patch.object(main, "CONFIG_PATH", config_path):
                config = main.load_plugin_config()

        self.assertIsInstance(config["bilibili"], dict)
        self.assertTrue(config["bilibili"]["enabled"])
        self.assertFalse(config["review"]["enabled"])
        self.assertEqual(config["push"]["target_umos"], [])

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

    async def test_daily_history_avoids_recent_song_when_possible(self):
        with tempfile.TemporaryDirectory() as directory:
            db = main.SongDB(Path(directory) / "daily.db")
            await db.init()
            await db.add("BV0000000101", 1, "昨天的歌")
            await db.add("BV0000000102", 2, "今天的新歌")

            song = await db.random({"BV0000000101"})
            await db.record_daily(song, "今天的新歌")
            history = await db.recent_daily(14)

        self.assertEqual(song["bvid"], "BV0000000102")
        self.assertEqual(history[0]["bvid"], "BV0000000102")
        self.assertEqual(history[0]["query"], "今天的新歌")

    async def test_scheduled_push_sends_title_review_then_video(self):
        track = {
            "bvid": "BV1nk9fBTEkE",
            "title": "角色T (Character T) / 重音teto",
            "author": "Atenaアテナ",
            "duration": 182,
        }
        context = SimpleNamespace(
            send_message=AsyncMock(),
            get_using_provider=lambda _origin: None,
        )
        db = SimpleNamespace(
            recent_daily=AsyncMock(return_value=[]),
            random=AsyncMock(return_value=track),
            record_daily=AsyncMock(),
        )
        plugin = object.__new__(main.JRSQPlugin)
        plugin.context = context
        plugin.db = db
        plugin.push_config = {
            "target_umos": ["aiocqhttp:GroupMessage:123"],
            "recent_history_size": 14,
        }
        plugin._bili_chain = AsyncMock(return_value=["VIDEO"])
        plugin._generate_review = AsyncMock(return_value="合成声部很有张力，我会想再听一遍。")

        with patch.object(main, "MessageChain", side_effect=lambda value: value):
            await plugin.scheduled_push()

        messages = [call.args[1] for call in context.send_message.await_args_list]
        self.assertEqual(len(messages), 3)
        self.assertIn("今日推荐：角色T", messages[0][0].text)
        self.assertIn("合成声部很有张力", messages[1][0].text)
        self.assertEqual(messages[2], ["VIDEO"])
        db.record_daily.assert_awaited_once_with(track, "")

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

    async def test_direct_bvid_normalizes_lowercase_prefix(self):
        service = main.BiliMediaService({}, {})
        service.enrich = AsyncMock(
            return_value={
                "bvid": "BV1CK4y1Y7r1",
                "title": "天ノ弱／164 feat.GUMI【Official】",
            }
        )

        await service.find_candidates("bv1CK4y1Y7r1")

        self.assertEqual(service.enrich.await_args.args[0]["bvid"], "BV1CK4y1Y7r1")

    async def test_search_api_bootstraps_anonymous_cookie(self):
        async def homepage(_request):
            response = web.Response(text="ok")
            response.set_cookie("buvid3", "anonymous-session")
            return response

        async def search(request):
            if request.cookies.get("buvid3") != "anonymous-session":
                return web.Response(status=412)
            return web.json_response(
                {
                    "code": 0,
                    "data": {
                        "result": [
                            {
                                "bvid": "BV0000000015",
                                "title": "测试术曲 / 初音ミク",
                                "author": "测试P",
                                "duration": "03:00",
                                "tag": "初音ミク,VOCALOID",
                            }
                        ]
                    },
                }
            )

        app = web.Application()
        app.router.add_get("/", homepage)
        app.router.add_get("/search", search)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        try:
            with (
                patch.object(main, "BILI_HOME", f"http://localhost:{port}/"),
                patch.object(
                    main, "BILI_SEARCH_API", f"http://localhost:{port}/search"
                ),
            ):
                tracks = await main.BiliMediaService({}, {})._search_api("测试术曲")
            self.assertEqual(tracks[0]["bvid"], "BV0000000015")
        finally:
            await runner.cleanup()

    async def test_find_candidates_retries_with_derived_title(self):
        service = main.BiliMediaService(
            {"search_suffix": "", "search_min_score": 90}, {}
        )
        first = [
            {
                "bvid": "BV0000000016",
                "title": "【音质提升】《请批准吧灯神先生!》 / 重音テト・音街ウナ",
                "tags": ["VOCALOID", "重音テト"],
                "duration": 203,
            }
        ]
        original = [
            {
                "bvid": "BV0000000017",
                "title": "【本家投稿】请批准吧灯神先生! / 重音テト・音街ウナ",
                "author": "TRAP CHICK",
                "tags": ["重音テト", "音街ウナ", "原创曲"],
                "duration": 203,
                "copyright": 1,
            }
        ]

        async def fake_search(query):
            return original if "请批准" in query else first

        service.search = AsyncMock(side_effect=fake_search)
        service.enrich = AsyncMock(side_effect=lambda track: track)

        tracks = await service.find_candidates("帮帮我吧神灯先生")

        self.assertEqual(tracks[0]["bvid"], "BV0000000017")
        self.assertTrue(
            any("请批准" in call.args[0] for call in service.search.await_args_list)
        )

    async def test_find_candidates_does_not_stop_before_original_suffix_search(self):
        service = main.BiliMediaService(
            {"search_suffix": "VOCALOID 原曲 MV", "search_min_score": 90}, {}
        )
        live = [
            {
                "bvid": "BV0000000026",
                "title": "世界第一公主殿下 Magical Mirai 2018",
                "tags": ["初音未来", "VOCALOID", "演唱会"],
                "duration": 302,
            }
        ]
        original = [
            {
                "bvid": "BV0000000027",
                "title": "[原版PV]初音未来《世界第一公主殿下 World is Mine》",
                "author": "ryo",
                "tags": ["初音未来", "VOCALOID", "原曲"],
                "duration": 254,
                "copyright": 1,
            }
        ]

        async def fake_search(query):
            return original if "原曲" in query else live

        service.search = AsyncMock(side_effect=fake_search)
        service.enrich = AsyncMock(side_effect=lambda track: track)

        tracks = await service.find_candidates("世界第一公主殿下")

        self.assertEqual(tracks[0]["bvid"], "BV0000000027")
        self.assertTrue(
            any("原曲" in call.args[0] for call in service.search.await_args_list)
        )

    async def test_fuzzy_match_gets_canonical_title_second_pass(self):
        service = main.BiliMediaService(
            {"search_suffix": "", "search_min_score": 90}, {}
        )
        translated = [
            {
                "bvid": "BV0000000018",
                "title": "アンノウン・マザーグース / 不为人知的鹅妈妈童谣",
                "tags": ["初音ミク", "VOCALOID"],
                "duration": 269,
            }
        ]
        original = [
            {
                "bvid": "BV0000000019",
                "title": "アンノウン・マザーグース / wowaka feat. 初音ミク",
                "author": "wowaka",
                "tags": ["初音ミク", "VOCALOID", "原曲"],
                "duration": 269,
                "copyright": 1,
            }
        ]

        async def fake_search(query):
            return original if query.startswith("アンノウン") else translated

        service.search = AsyncMock(side_effect=fake_search)
        service.enrich = AsyncMock(side_effect=lambda track: track)

        tracks = await service.find_candidates("鹅妈妈的童谣")

        self.assertEqual(tracks[0]["bvid"], "BV0000000019")

    async def test_bilingual_result_allows_one_bounded_alias_hop(self):
        service = main.BiliMediaService(
            {"search_suffix": "", "search_min_score": 90}, {}
        )
        translated = [
            {
                "bvid": "BV0000000031",
                "title": "アンノウン・マザーグース / 不为人知的鹅妈妈童谣",
                "tags": ["初音ミク", "VOCALOID"],
                "duration": 269,
            }
        ]
        bilingual = [
            {
                "bvid": "BV0000000032",
                "title": "アンノウン・マザーグース / Unknown Mother Goose",
                "tags": ["初音ミク", "VOCALOID"],
                "duration": 269,
            }
        ]
        original = [
            {
                "bvid": "BV0000000033",
                "title": "【本家】Unknown Mother-Goose【wowaka feat. 初音ミク】",
                "tags": ["初音ミク", "VOCALOID", "原曲"],
                "duration": 269,
                "copyright": 1,
            }
        ]

        async def fake_search(query):
            if query.startswith("Unknown Mother"):
                return original
            if query.startswith("アンノウン"):
                return bilingual
            return translated

        service.search = AsyncMock(side_effect=fake_search)
        service.enrich = AsyncMock(side_effect=lambda track: track)

        tracks = await service.find_candidates("鹅妈妈的童谣")

        self.assertEqual(tracks[0]["bvid"], "BV0000000033")
        self.assertTrue(
            any(
                call.args[0].startswith("Unknown Mother")
                for call in service.search.await_args_list
            )
        )

    async def test_ranking_enriches_best_candidate_beyond_first_batch(self):
        service = main.BiliMediaService(
            {"detail_count": 1, "search_min_score": 90}, {}
        )
        tracks = [
            {
                "bvid": f"BV{i:010d}",
                "title": f"普通视频 {i}",
                "duration": 180,
            }
            for i in range(12)
        ]
        tracks[-1]["title"] = "测试曲"

        async def enrich(track):
            return {**track, "tags": ["初音ミク", "VOCALOID"], "copyright": 1}

        service.enrich = AsyncMock(side_effect=enrich)

        ranked = await service.rank_candidates(tracks, "测试曲")

        self.assertEqual(ranked[0]["bvid"], "BV0000000011")
        self.assertEqual(service.enrich.await_args.args[0]["bvid"], "BV0000000011")

    async def test_ranking_reserves_detail_slot_for_refined_alias(self):
        service = main.BiliMediaService(
            {"detail_count": 1, "search_min_score": 90}, {}
        )
        tracks = [
            {
                "bvid": "BV0000000034",
                "title": "鹅妈妈的童谣热门字幕版",
                "tags": ["初音ミク", "VOCALOID"],
                "duration": 269,
                "best_search_position": 0,
                "search_origins": ["request:鹅妈妈的童谣"],
            },
            {
                "bvid": "BV0000000035",
                "title": "【初音ミク】Unknown Mother-Goose【wowaka】",
                "tags": ["初音ミク", "VOCALOID"],
                "duration": 269,
                "best_search_position": 0,
                "search_origins": ["refined:unknownmothergoose"],
            },
        ]

        async def enrich(track):
            if track["bvid"] == "BV0000000035":
                return {
                    **track,
                    "description": "Produced by wowaka",
                    "copyright": 2,
                }
            return track

        service.enrich = AsyncMock(side_effect=enrich)

        ranked = await service.rank_candidates(
            tracks,
            "鹅妈妈的童谣",
            derived_query_variants=["Unknown Mother Goose"],
        )

        self.assertEqual(service.enrich.await_args.args[0]["bvid"], "BV0000000035")
        self.assertEqual(ranked[0]["bvid"], "BV0000000035")

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
