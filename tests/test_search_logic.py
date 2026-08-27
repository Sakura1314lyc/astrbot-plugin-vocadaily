import unittest

from search_logic import (
    assess_candidate,
    derive_query_variants,
    derive_request_query_variants,
    normalize_search_text,
    parse_duration,
    rank_search_candidates,
)


class SearchLogicTests(unittest.TestCase):
    def test_derives_spoken_request_aliases_without_losing_original(self):
        variants = derive_request_query_variants("想听你说月色真美")

        self.assertEqual(variants[0], "想听你说月色真美")
        self.assertIn("你说月色真美", variants)
        self.assertIn("月色真美", variants)

    def test_extracts_quoted_title_from_polite_request(self):
        variants = derive_request_query_variants("请给我播放一下《千本樱》可以吗")

        self.assertIn("千本樱", variants)

    def test_normalizes_common_title_variants(self):
        self.assertEqual(normalize_search_text("千本桜"), "千本樱")
        self.assertEqual(normalize_search_text("強風 オールバック"), "强风オールバック")

    def test_character_t_adds_confirmed_cross_language_aliases(self):
        variants = derive_request_query_variants("角色T")

        self.assertEqual(variants[0], "角色T")
        self.assertIn("キャラクターT", variants)
        self.assertIn("Character T", variants)

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

    def test_exact_short_title_without_song_evidence_is_rejected(self):
        ranked = rank_search_candidates(
            [
                {
                    "bvid": "BV0000000020",
                    "title": "想听你说月色真美",
                    "tags": ["碧蓝档案", "日语学习"],
                    "duration": 34,
                    "play": 2_000_000,
                }
            ],
            "想听你说月色真美",
        )

        self.assertEqual(ranked, [])

    def test_original_pv_outranks_live_and_mmd_versions(self):
        tracks = [
            {
                "bvid": "BV0000000021",
                "title": "【4K】世界第一公主殿下 Magical Mirai 2018",
                "tags": ["初音未来", "VOCALOID", "演唱会"],
                "duration": 302,
                "play": 20_000_000,
            },
            {
                "bvid": "BV0000000022",
                "title": "【MMD】世界第一公主殿下 初音未来",
                "tags": ["初音未来", "VOCALOID"],
                "duration": 250,
            },
            {
                "bvid": "BV0000000023",
                "title": "[原版PV]初音未来《世界第一公主殿下 World is Mine》",
                "author": "ryo",
                "tags": ["初音未来", "VOCALOID", "原曲"],
                "duration": 254,
                "copyright": 1,
            },
        ]

        ranked = rank_search_candidates(tracks, "世界第一公主殿下")

        self.assertEqual([item["bvid"] for item in ranked], ["BV0000000023"])

    def test_moon_original_wins_across_request_aliases(self):
        tracks = [
            {
                "bvid": "BV0000000024",
                "title": "❤想听你说月色真美❤",
                "tags": ["碧蓝档案", "日语学习"],
                "duration": 34,
                "play": 2_000_000,
            },
            {
                "bvid": "BV0000000025",
                "title": "【本家】月が綺麗ねと言われたい！ - 初音ミク【カササギ】",
                "author": "カササギ_柿崎ユウタ",
                "tags": ["VOCALOID", "初音ミク", "我想被你说一句月色真美啊"],
                "duration": 147,
                "play": 11_000_000,
                "copyright": 1,
            },
        ]
        aliases = derive_request_query_variants("想听你说月色真美")

        ranked = rank_search_candidates(
            tracks,
            "想听你说月色真美",
            query_variants=aliases,
        )

        self.assertEqual([item["bvid"] for item in ranked], ["BV0000000025"])

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

    def test_character_t_beats_unrelated_official_character_song(self):
        tracks = [
            {
                "bvid": "BV0000000040",
                "title": "Character / ACAね×Rin音",
                "author": "电影音乐官方",
                "tags": ["初音未来", "音乐"],
                "duration": 302,
                "copyright": 1,
            },
            {
                "bvid": "BV1nk9fBTEkE",
                "title": "角色T (Character T) / 重音teto, 重音teto SV",
                "author": "Atenaアテナ",
                "tags": ["VOCALOID", "重音テト", "キャラクターT"],
                "duration": 182,
                "copyright": 1,
            },
        ]

        ranked = rank_search_candidates(
            tracks,
            "角色T",
            query_variants=derive_request_query_variants("角色T"),
            derived_query_variants=[],
        )

        self.assertEqual(ranked[0]["bvid"], "BV1nk9fBTEkE")
        self.assertEqual(ranked[0]["search_match_source"], "request")
        self.assertNotIn("BV0000000040", [item["bvid"] for item in ranked])

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

    def test_fuzzy_chinese_title_variant_is_accepted(self):
        ranked = rank_search_candidates(
            [
                {
                    "bvid": "BV0000000012",
                    "title": "アンノウン・マザーグース / 不为人知的鹅妈妈童谣",
                    "author": "wowaka",
                    "tags": ["初音ミク", "VOCALOID"],
                    "duration": 269,
                    "copyright": 1,
                }
            ],
            "鹅妈妈的童谣",
        )
        self.assertEqual([item["bvid"] for item in ranked], ["BV0000000012"])
        self.assertEqual(ranked[0]["search_match"], "fuzzy")

    def test_original_outranks_audio_enhancement(self):
        tracks = [
            {
                "bvid": "BV0000000013",
                "title": "【音质提升】请批准吧灯神先生! / 重音テト・音街ウナ",
                "author": "TRAP_CHICK_official",
                "tags": ["VOCALOID"],
                "duration": 203,
                "copyright": 1,
            },
            {
                "bvid": "BV0000000014",
                "title": "【本家投稿】请批准吧灯神先生! / 重音テト・音街ウナ",
                "author": "TRAP CHICK",
                "tags": ["重音テト", "音街ウナ", "原创曲"],
                "duration": 203,
                "copyright": 1,
            },
        ]
        ranked = rank_search_candidates(tracks, "请批准吧灯神先生!")
        self.assertEqual(ranked[0]["bvid"], "BV0000000014")

    def test_derives_canonical_title_from_top_result(self):
        variants = derive_query_variants(
            [
                {
                    "title": "【音质提升】《请批准吧灯神先生!》 / 重音テト・音街ウナ",
                    "tags": ["VOCALOID", "重音テト"],
                }
            ],
            "帮帮我吧神灯先生",
        )
        self.assertIn("请批准吧灯神先生", variants)

    def test_derived_titles_ignore_reupload_packaging(self):
        variants = derive_query_variants(
            [
                {
                    "title": "惊喜爱无打码补挡",
                    "tags": ["VOCALOID", "重音テト"],
                },
                {
                    "title": (
                        "【官方 MV/中字版】惊喜爱/哦吼爱 オッホ愛"
                        "（初音ミク 亜北ネル 重音テト）【PPP Sounds】"
                    ),
                    "tags": ["VOCALOID", "初音ミク", "重音テト"],
                },
            ],
            "惊喜爱",
        )

        self.assertFalse(any("无打码" in item or "补挡" in item for item in variants))
        self.assertTrue(any(item.startswith("哦吼爱") for item in variants))
        self.assertFalse(any("惊喜爱/哦吼爱" in item for item in variants))

    def test_plain_original_version_claim_is_not_home_upload_evidence(self):
        assessment = assess_candidate(
            {
                "title": "惊喜爱原版，你们是不是也被洗脑了",
                "tags": ["VOCALOID", "重音テト"],
                "duration": 156,
                "copyright": 3,
            },
            "惊喜爱",
        )

        self.assertFalse(assessment.original_signal)

    def test_official_mv_outranks_generic_original_version_claim(self):
        ranked = rank_search_candidates(
            [
                {
                    "bvid": "BV1BEApzJEWS",
                    "title": "惊喜爱原版，你们是不是也被惊喜爱洗脑了",
                    "author": "甜甜的幸福小日记",
                    "tags": ["VOCALOID", "重音テト"],
                    "duration": 156,
                    "play": 2_339,
                    "copyright": 3,
                },
                {
                    "bvid": "BV1NjDrBnEWc",
                    "title": (
                        "【官方 MV/中字版】惊喜爱/哦吼爱 オッホ愛"
                        "（初音ミク 亜北ネル 重音テト）【PPP Sounds】"
                    ),
                    "author": "芜溢-中文翻译",
                    "tags": ["VOCALOID", "初音ミク", "重音テト", "原创曲"],
                    "duration": 155,
                    "play": 30_327,
                    "favorites": 399,
                    "copyright": 1,
                },
            ],
            "惊喜爱",
        )

        self.assertEqual(ranked[0]["bvid"], "BV1NjDrBnEWc")
        self.assertTrue(ranked[0]["search_original"])

    def test_derived_alias_is_recorded_as_lower_confidence_source(self):
        ranked = rank_search_candidates(
            [
                {
                    "bvid": "BV0000000030",
                    "title": "アンノウン・マザーグース / wowaka feat. 初音ミク",
                    "tags": ["VOCALOID", "初音ミク", "原曲"],
                    "duration": 269,
                    "copyright": 1,
                }
            ],
            "鹅妈妈的童谣",
            derived_query_variants=["アンノウン・マザーグース"],
        )

        self.assertEqual(ranked[0]["search_match_source"], "derived")

    def test_cross_script_alias_requires_explicit_second_pass_trust(self):
        tracks = [
            {
                "title": "【初音ミク】Unknown Mother-Goose【wowaka】",
                "tags": ["初音ミク", "VOCALOID"],
            }
        ]

        self.assertEqual(
            derive_query_variants(tracks, "アンノウン・マザーグース"),
            [],
        )
        trusted = derive_query_variants(
            [
                {
                    "title": (
                        "アンノウン・マザーグース / Unknown Mother-Goose"
                    ),
                    "tags": ["初音ミク", "VOCALOID"],
                }
            ],
            "アンノウン・マザーグース",
            allow_top_cross_script=True,
        )
        self.assertIn("Unknown Mother-Goose", trusted)

    def test_cross_script_refinement_rejects_unrelated_single_title(self):
        variants = derive_query_variants(
            [
                {
                    "title": "Character / ACAね×Rin音",
                    "tags": ["初音未来", "VOCALOID"],
                }
            ],
            "キャラクターT",
            allow_top_cross_script=True,
        )

        self.assertEqual(variants, [])

    def test_hand_drawn_derivative_is_rejected(self):
        assessment = assess_candidate(
            {
                "title": "【手书】千本樱 初音未来",
                "tags": ["VOCALOID"],
                "duration": 240,
            },
            "千本樱",
        )
        self.assertIn("手书", assessment.rejected_reason or "")

    def test_duet_derivative_is_rejected(self):
        assessment = assess_candidate(
            {
                "title": "《アンノウン・マザーグース》 wowaka + 初音ミク DUET",
                "tags": ["初音ミク", "VOCALOID"],
                "duration": 269,
            },
            "アンノウン・マザーグース",
        )
        self.assertIn("duet", (assessment.rejected_reason or "").lower())

    def test_japanese_cover_is_rejected(self):
        assessment = assess_candidate(
            {
                "title": "【重音テト】Unknown Mother Goose【UTAUカバー】",
                "tags": ["重音テト", "UTAU"],
                "duration": 269,
            },
            "Unknown Mother",
        )
        self.assertIn("カバー", assessment.rejected_reason or "")

    def test_cover_tag_is_rejected_even_when_title_is_ambiguous(self):
        assessment = assess_candidate(
            {
                "title": "【える】Unknown Mother-Goose",
                "tags": ["える", "翻唱", "授权转载"],
                "duration": 269,
            },
            "Unknown Mother",
        )
        self.assertIn("标签", assessment.rejected_reason or "")

    def test_cover_cannot_borrow_original_signal_from_description(self):
        assessment = assess_candidate(
            {
                "title": "【urei】Unknown Mother Goose",
                "author": "精神安定剤",
                "tags": ["urei", "アンノウン・マザーグース"],
                "description": (
                    "original: wowaka / Vocal: Hatsune Miku / Vocal: urei"
                ),
                "duration": 355,
                "copyright": 2,
            },
            "Unknown Mother",
        )
        self.assertFalse(assessment.song_signal)
        self.assertLess(assessment.score, 90)

    def test_archival_reprint_can_use_preserved_external_source_credit(self):
        assessment = assess_candidate(
            {
                "title": "【初音ミク】Unknown Mother-Goose【wowaka】",
                "author": "原曲存档号",
                "description": (
                    "sm31791630 https://www.youtube.com/watch?v=example\n"
                    "Produced by wowaka"
                ),
                "tags": ["VOCALOID", "初音ミク"],
                "duration": 286,
                "copyright": 2,
            },
            "Unknown Mother Goose",
        )

        self.assertTrue(assessment.original_signal)
        self.assertGreater(assessment.score, 140)

    def test_cover_source_link_is_not_original_evidence(self):
        assessment = assess_candidate(
            {
                "title": "不为人知的鹅妈妈童谣／鏡音レン／キノコP",
                "description": (
                    "本家：sm31791630\nMusic：wowaka\nVocal：鏡音レン"
                ),
                "tags": ["VOCALOID", "鏡音レン", "wowaka"],
                "duration": 287,
                "copyright": 1,
            },
            "鹅妈妈的童谣",
        )

        self.assertFalse(assessment.original_signal)


if __name__ == "__main__":
    unittest.main()
