import unittest

from search_logic import (
    assess_candidate,
    normalize_search_text,
    parse_duration,
    rank_search_candidates,
)


class SearchLogicTests(unittest.TestCase):
    def test_normalizes_common_title_variants(self):
        self.assertEqual(normalize_search_text("千本桜"), "千本樱")
        self.assertEqual(normalize_search_text("強風 オールバック"), "强风オールバック")

    def test_parses_duration_without_raising(self):
        self.assertEqual(parse_duration("04:21"), 261)
        self.assertEqual(parse_duration("1:02:03"), 3723)
        self.assertEqual(parse_duration("--"), 0)

    def test_original_outranks_and_filters_derivatives(self):
        tracks = [
            {
                "bvid": "BV0000000001",
                "title": "全站最快3分钟学唱《ロキ》罗马音+中文谐音",
                "author": "教学号",
                "duration": 180,
                "copyright": 1,
            },
            {
                "bvid": "BV0000000002",
                "title": "ロキ／鏡音リン・みきとP【オリジナル】",
                "author": "みきとP official",
                "tags": ["VOCALOID", "鏡音リン"],
                "duration": 230,
                "copyright": 1,
            },
            {
                "bvid": "BV0000000003",
                "title": "ロキ 钢琴演奏版",
                "author": "琴师",
                "duration": 220,
            },
        ]
        ranked = rank_search_candidates(tracks, "ロキ", minimum_score=90)
        self.assertEqual([item["bvid"] for item in ranked], ["BV0000000002"])

    def test_description_marker_does_not_hard_reject_original(self):
        result = assess_candidate(
            {
                "title": "天ノ弱／164 feat.GUMI【Official】",
                "author": "164_official",
                "description": "请勿上传翻唱或伴奏",
                "tags": ["GUMI", "VOCALOID"],
                "duration": 187,
                "copyright": 1,
            },
            "天ノ弱",
        )
        self.assertIsNone(result.rejected_reason)
        self.assertGreater(result.score, 90)

    def test_short_ascii_marker_does_not_match_inside_original(self):
        result = assess_candidate(
            {
                "title": "Example Suffering",
                "author": "someone",
                "duration": 200,
            },
            "Example Suffering",
        )
        self.assertFalse(result.song_signal)

    def test_generic_social_clip_is_below_threshold(self):
        ranked = rank_search_candidates(
            [
                {
                    "bvid": "BV0000000004",
                    "title": "当主播听到邻居在拉《千本樱》",
                    "author": "日常切片",
                    "duration": 160,
                    "copyright": 1,
                }
            ],
            "千本樱",
            minimum_score=90,
        )
        self.assertEqual(ranked, [])

    def test_deduplicates_candidates(self):
        track = {
            "bvid": "BV0000000005",
            "title": "少女レイ / 初音ミク【オリジナル】",
            "author": "みきとP official",
            "tags": ["VOCALOID"],
            "duration": 290,
        }
        ranked = rank_search_candidates([track, track], "少女レイ")
        self.assertEqual(len(ranked), 1)

    def test_game_and_dance_versions_do_not_beat_original(self):
        tracks = [
            {
                "bvid": "BV0000000006",
                "title": "ロキ (Roki) — 星乃一歌 x 初音未来 | 歌词分配 | 中字",
                "tags": ["初音未来", "世界计划"],
                "duration": 220,
                "copyright": 1,
            },
            {
                "bvid": "BV0000000007",
                "title": "【原创PV】ロキ／Roki feat.镜音铃・Mikito P",
                "author": "みきとP",
                "tags": ["VOCALOID"],
                "duration": 230,
                "copyright": 1,
            },
            {
                "bvid": "BV0000000008",
                "title": "【原创编舞】ロキ【一镜到底】",
                "duration": 230,
            },
        ]
        ranked = rank_search_candidates(tracks, "ロキ")
        self.assertEqual([item["bvid"] for item in ranked], ["BV0000000007"])

    def test_top_metadata_match_handles_translated_title(self):
        tracks = [
            {
                "bvid": "BV0000000009",
                "title": "【歌愛ユキ】强风大背头【Yukopi】",
                "description": "強風オールバック original",
                "tags": ["歌愛ユキ", "VOCALOID"],
                "duration": 142,
                "play": 3_000_000,
            },
            {
                "bvid": "BV0000000010",
                "title": "【翻弹】強風オールバック",
                "duration": 142,
            },
            {
                "bvid": "BV0000000011",
                "title": "强风大背头同人动画·搞笑·搬运",
                "description": "強風オールバック",
                "tags": ["歌愛ユキ"],
                "duration": 142,
            },
        ]
        ranked = rank_search_candidates(tracks, "強風オールバック")
        self.assertEqual([item["bvid"] for item in ranked], ["BV0000000009"])

    def test_cosplay_title_is_rejected(self):
        assessment = assess_candidate(
            {
                "title": "千本樱 初音cos",
                "tags": ["初音ミク"],
                "duration": 240,
            },
            "千本樱",
        )
        self.assertEqual(assessment.match_quality, "rejected")


if __name__ == "__main__":
    unittest.main()
