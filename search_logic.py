"""Pure helpers for Bilibili song search and candidate ranking."""

from __future__ import annotations

import math
import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

_CHAR_TRANSLATION = str.maketrans(
    {
        "桜": "樱",
        "櫻": "樱",
        "強": "强",
        "風": "风",
        "臺": "台",
    }
)

HARD_NEGATIVE_MARKERS = (
    "翻唱",
    "翻弹",
    "covered",
    "cover",
    "カバー",
    "歌ってみた",
    "踊ってみた",
    "弾いてみた",
    "アレンジ",
    "リミックス",
    "remix",
    "duet",
    "合唱",
    "对唱",
    "對唱",
    "演奏",
    "教程",
    "学唱",
    "羅馬音",
    "罗马音",
    "谐音",
    "音游",
    "音遊",
    "谱面",
    "譜面",
    "鬼畜",
    "meme",
    "reaction",
    "剪辑",
    "剪輯",
    "歌切",
    "伴奏",
    "off vocal",
    "offvocal",
    "カラオケ",
    "ニコカラ",
    "mad",
    "amv",
    "mmd",
    "magical mirai",
    "魔法未来",
    "演唱会",
    "演唱會",
    "concert",
    "live",
    "project diva",
    "歌姬计划",
    "歌姬計畫",
    "宅舞",
    "手书",
    "手書き",
    "手描",
    "描改",
    "试跳",
    "試跳",
    "直拍",
    "镜面",
    "鏡面",
    "真人版",
    "钢琴",
    "鋼琴",
    "琴谱",
    "琴譜",
    "扒谱",
    "扒譜",
    "小提琴",
    "古筝",
    "古箏",
    "鼓谱",
    "鼓譜",
    "贝斯谱",
    "貝斯譜",
    "tab譜",
    "tab谱",
    "ギター",
    "maimai",
    "锁屏可打",
    "鎖屏可打",
    "歌词分配",
    "歌詞分配",
    "世界计划",
    "世界計畫",
    "プロセカ",
    "project sekai",
    "sekai ver",
    "2dmv",
    "3dmv",
    "翻跳",
    "翻调",
    "翻調",
    "编舞",
    "編舞",
    "一镜到底",
    "一鏡到底",
    "中文版",
    "中文填词",
    "中文填詞",
    "二创",
    "二創",
    "同人动画",
    "同人動畫",
    "短视频",
    "短視頻",
    "动画片段",
    "動畫片段",
    "游戏片段",
    "遊戲片段",
    "搞笑",
    "背景素材",
    "鸣潮",
    "鳴潮",
    "原神",
    "崩坏",
    "崩壞",
    "火影",
    "cosplay",
    "cos",
    "双声道",
    "雙聲道",
    "纯人声",
    "純人聲",
    "8bit",
    "8-bit",
    "fnf",
    "一小时循环",
    "一小時循環",
    "循环播放",
    "循環播放",
    "无打码",
    "無打碼",
    "无码",
    "無碼",
    "补档",
    "補檔",
    "补挡",
    "補擋",
)

SOFT_NEGATIVE_MARKERS = (
    "合集",
    "排名",
    "盘点",
    "盤點",
    "歌单",
    "歌單",
    "电台",
    "電台",
    "主播",
    "reaction",
    "搬运",
    "搬運",
    "自用",
    "完整版",
    "但是",
    "中文字幕",
    "字幕版",
    "中字",
    "自制字幕",
    "自製字幕",
    "自制中文字幕",
    "自製中文字幕",
    "高精度还原",
    "高精度還原",
    "声库对比",
    "聲庫對比",
    "修正版对比",
    "修正版對比",
    "修复",
    "修復",
    "高质量",
    "高質量",
    "音质提升",
    "音質提升",
    "高音质",
    "高音質",
    "无损",
    "無損",
    "4k",
    "60fps",
    "120fps",
    "v4x",
    "svp",
    "vsqx",
)

VOCAL_SYNTH_MARKERS = (
    "vocaloid",
    "术力口",
    "術力口",
    "ボカロ",
    "初音",
    "miku",
    "ミク",
    "gumi",
    "镜音",
    "鏡音",
    "rin",
    "len",
    "巡音",
    "luka",
    "重音",
    "teto",
    "テト",
    "可不",
    "kafu",
    "歌愛ユキ",
    "音街ウナ",
    "flower",
    "v flower",
    "cevio",
    "synthesizer v",
    "synthesizerv",
    "裏命",
    "ずんだもん",
)

ORIGINAL_MARKERS = (
    "official",
    "官方投稿",
    "官方mv",
    "官方pv",
    "本家",
    "原曲",
    "原版",
    "原创",
    "原創",
    "オリジナル",
    "original",
    "feat",
)

STRONG_ORIGINAL_MARKERS = (
    "本家投稿",
    "本家",
    "官方投稿",
    "官方mv",
    "官方pv",
    "原曲",
    "原版pv",
    "原创曲",
    "原創曲",
    "オリジナル",
    "official",
    "original",
)

LIGHT_SOFT_NEGATIVE_MARKERS = (
    "完整版",
    "中文字幕",
    "字幕版",
    "中字",
)

EDITORIAL_TITLE_MARKERS = (
    "你们",
    "你們",
    "是不是",
    "有没有",
    "有沒有",
    "竟然",
    "居然",
    "听完",
    "聽完",
    "看完",
    "什么水平",
    "什麼水平",
    "如何评价",
    "如何評價",
    "洗脑了",
    "洗腦了",
)

_DERIVED_TITLE_REJECT_MARKERS = (
    *HARD_NEGATIVE_MARKERS,
    "无打码",
    "無打碼",
    "无码",
    "無碼",
    "补档",
    "補檔",
    "补挡",
    "補擋",
    "未删减",
    "未刪減",
)


def normalize_search_text(value: str) -> str:
    """Normalize common Chinese/Japanese variants for loose title matching."""

    value = unicodedata.normalize("NFKC", str(value)).casefold()
    value = value.translate(_CHAR_TRANSLATION)
    return re.sub(r"[^0-9a-z\u3040-\u30ff\u3400-\u9fff]+", "", value)


def parse_duration(value: Any) -> int:
    """Parse Bilibili duration values such as ``04:21`` without raising."""

    if isinstance(value, (int, float)):
        return max(0, int(value))
    parts = str(value or "0").strip().split(":")
    if not parts or any(not part.isdigit() for part in parts) or len(parts) > 3:
        return 0
    return sum(int(part) * (60**index) for index, part in enumerate(reversed(parts)))


def _safe_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _marker_present(text: str, marker: str) -> bool:
    folded_text = unicodedata.normalize("NFKC", text).casefold()
    folded_marker = unicodedata.normalize("NFKC", marker).casefold()
    if folded_marker.isascii() and re.fullmatch(r"[a-z0-9 ]+", folded_marker):
        pattern = re.escape(folded_marker).replace(r"\ ", r"\s+")
        match = re.search(rf"(?<![a-z0-9]){pattern}(?![a-z0-9])", folded_text)
        return match is not None
    return normalize_search_text(folded_marker) in normalize_search_text(folded_text)


def _find_markers(text: str, markers: Iterable[str]) -> tuple[str, ...]:
    return tuple(marker for marker in markers if _marker_present(text, marker))


def _distinct_marker_count(markers: Iterable[str]) -> int:
    """Count overlapping labels once (for example, 中文字幕 and 中字)."""

    selected: list[str] = []
    normalized = sorted(
        {normalize_search_text(marker) for marker in markers if marker},
        key=len,
        reverse=True,
    )
    for marker in normalized:
        if marker and not any(marker in existing for existing in selected):
            selected.append(marker)
    return len(selected)


_BRACKETED_PREFIX_RE = re.compile(
    r"(?:【[^】]{0,80}】|\[[^\]]{0,80}\]|\([^)]{0,80}\)|（[^）]{0,80}）)"
)
_QUOTED_TITLE_RE = re.compile(r"[《「『](?P<title>[^》」』]{2,80})[》」』]")
_TITLE_SEPARATOR_RE = re.compile(r"\s*(?:/|／|\||｜|—|–)\s*")
_PAREN_ALIAS_RE = re.compile(r"[（(](?P<title>[^()（）]{2,60})[）)]")

# A small, evidence-backed alias table is safer than asking an LLM to guess a
# title.  Keep this deliberately narrow: entries belong here only when the
# Chinese, Japanese and English names are established names of the same song.
_KNOWN_TITLE_ALIASES = {
    "角色t": ("キャラクターT", "Character T", "角色T 重音テト Atena"),
    "キャラクターt": ("角色T", "Character T", "キャラクターT 重音テト Atena"),
    "charactert": ("角色T", "キャラクターT", "Character T 重音テト Atena"),
}


def _title_match_variants(title: str) -> tuple[str, ...]:
    """Return compact title-shaped strings for fuzzy comparison."""

    raw = unicodedata.normalize("NFKC", str(title or ""))
    values = [raw]
    values.extend(match.group("title") for match in _QUOTED_TITLE_RE.finditer(raw))
    stripped = _BRACKETED_PREFIX_RE.sub(" ", raw).strip()
    if stripped:
        values.append(stripped)
        values.extend(_TITLE_SEPARATOR_RE.split(stripped))

    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = normalize_search_text(value)
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return tuple(result)


def _best_title_similarity(title: str, query: str) -> float:
    query_norm = normalize_search_text(query)
    if len(query_norm) < 4:
        return 0.0

    # A trailing one-letter discriminator can be the meaningful part of a
    # title ("Character T").  Sequence similarity would otherwise consider
    # plain "Character" almost identical and admit an unrelated song.
    query_ascii_tokens = re.findall(
        r"[a-z0-9]+",
        unicodedata.normalize("NFKC", str(query)).casefold(),
    )
    if len(query_ascii_tokens) >= 2 and len(query_ascii_tokens[-1]) == 1:
        title_ascii_tokens = set(
            re.findall(
                r"[a-z0-9]+",
                unicodedata.normalize("NFKC", str(title)).casefold(),
            )
        )
        if query_ascii_tokens[-1] not in title_ascii_tokens:
            return 0.0

    def ngram_dice(left: str, right: str) -> float:
        size = 2 if min(len(left), len(right)) < 8 else 3
        left_parts = {
            left[index : index + size]
            for index in range(len(left) - size + 1)
        }
        right_parts = {
            right[index : index + size] for index in range(len(right) - size + 1)
        }
        if not left_parts or not right_parts:
            return 0.0
        return 2 * len(left_parts & right_parts) / (len(left_parts) + len(right_parts))

    similarities: list[float] = []
    for variant in _title_match_variants(title):
        sequence = SequenceMatcher(None, query_norm, variant, autojunk=False).ratio()
        similarities.append(max(sequence, ngram_dice(query_norm, variant)))
    return max(similarities, default=0.0)


_REQUEST_PREFIX_PATTERNS = (
    re.compile(
        r"^(?:麻烦|麻煩|请|請)?(?:给我|給我|帮我|幫我)?"
        r"(?:播放|放一下|放首|放|来一首|來一首|来首|來首|点播|點播|搜索|搜|找)"
        r"(?:一下|一首|首)?[：:、,，\s]*"
    ),
    re.compile(
        r"^(?:我)?(?:想听听|想聽聽|想听|想聽|要听|要聽)"
        r"(?:一下|一首|首)?[：:、,，\s]*"
    ),
)
_REQUEST_SUFFIX_RE = re.compile(
    r"(?:这首歌|這首歌|这首|這首)?(?:可以吗|可以嗎|行吗|行嗎|谢谢|謝謝)[?？!！\s]*$"
)


def derive_request_query_variants(query: str, *, limit: int = 5) -> list[str]:
    """Turn conversational song requests into bounded search aliases.

    The original input is always kept.  This matters for titles that really do
    begin with words such as ``想听``; cleaned forms are extra retrieval probes,
    not destructive rewrites.
    """

    raw = " ".join(unicodedata.normalize("NFKC", str(query or "")).split()).strip()
    values: list[str] = [raw] if raw else []
    values.extend(
        match.group("title").strip() for match in _QUOTED_TITLE_RE.finditer(raw)
    )

    # Spoken requests such as “想听你说月色真美” contain both a request verb
    # and a likely remembered lyric/title.  Keep both useful granularities.
    spoken_title = re.match(
        r"^(?:我)?(?:想听|想聽|想听听|想聽聽)(?:你|妳)(?:对我|對我)?说(?P<title>.{2,60})$",
        raw,
    )
    if spoken_title:
        values.append(spoken_title.group("title").strip())

    cleaned = raw
    for pattern in _REQUEST_PREFIX_PATTERNS:
        candidate = pattern.sub("", cleaned, count=1).strip()
        if candidate != cleaned:
            cleaned = candidate
            values.append(cleaned)
            break
    suffix_cleaned = _REQUEST_SUFFIX_RE.sub("", cleaned).strip()
    if suffix_cleaned and suffix_cleaned != cleaned:
        values.append(suffix_cleaned)

    # Known cross-language names are extra retrieval probes.  The user's text
    # remains first and therefore keeps the highest ranking authority.
    for source in tuple(values):
        values.extend(_KNOWN_TITLE_ALIASES.get(normalize_search_text(source), ()))

    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        value = value.strip(" \t\r\n-—–:：,，!！?？'\"")
        normalized = normalize_search_text(value)
        if len(normalized) < 2 or normalized in seen:
            continue
        seen.add(normalized)
        result.append(value)
        if len(result) >= limit:
            break
    return result


def derive_query_variants(
    tracks: Iterable[dict[str, Any]],
    query: str,
    *,
    limit: int = 3,
    allow_top_cross_script: bool = False,
) -> list[str]:
    """Derive likely canonical titles from strong top search results.

    Bilibili often understands a remembered or translated song name even when
    the returned title uses a different language. These variants are only used
    for a second search pass; they are never presented as authoritative data.
    """

    query_norm = normalize_search_text(query)
    singer_names = {
        normalize_search_text(marker)
        for marker in VOCAL_SYNTH_MARKERS
        if normalize_search_text(marker)
    }
    variants: list[str] = []
    seen = {query_norm}

    for position, track in enumerate(tracks):
        if position >= 4 or len(variants) >= limit:
            break
        title = unicodedata.normalize("NFKC", str(track.get("title") or ""))
        metadata = f"{title} {' '.join(str(tag) for tag in track.get('tags') or [])}"
        if not (
            _find_markers(metadata, VOCAL_SYNTH_MARKERS)
            or _find_markers(metadata, ORIGINAL_MARKERS)
        ):
            continue
        title_norm = normalize_search_text(title)
        source_relevant = (
            query_norm in title_norm
            or _best_title_similarity(title, query) >= 0.44
        )
        if not source_relevant and not (
            allow_top_cross_script and position <= 2
        ):
            # Do not let an unrelated top search result invent a new song name.
            continue

        quoted = [
            match.group("title").strip()
            for match in _QUOTED_TITLE_RE.finditer(title)
        ]
        parenthesized = [
            match.group("title").strip()
            for match in _PAREN_ALIAS_RE.finditer(title)
        ]
        stripped = _BRACKETED_PREFIX_RE.sub(" ", title).strip()
        pieces = [*quoted, *parenthesized]
        if stripped:
            split_pieces = _TITLE_SEPARATOR_RE.split(stripped)
            pieces.extend(split_pieces)
            # A whole "title / singer" string is a poor second-pass query and
            # can overpower the user's title. Keep it only when no separator
            # was found.
            if len(split_pieces) == 1:
                pieces.append(stripped)

        normalized_pieces = {
            normalize_search_text(piece)
            for piece in pieces
            if normalize_search_text(piece)
        }
        has_seed_piece = any(
            query_norm in piece or piece in query_norm
            for piece in normalized_pieces
        )
        if allow_top_cross_script and not source_relevant:
            # Cross-script refinement is only trustworthy when a bilingual
            # title visibly contains the previous alias.  A merely popular top
            # result must not invent a new song name (the old behaviour could
            # turn “角色T” into ACAね/Rin音's unrelated “Character”).
            if len(normalized_pieces) < 2 or not has_seed_piece:
                continue

        for piece in pieces:
            piece = piece.strip(" \t\r\n-—–:：,，!！?？'\"")
            normalized = normalize_search_text(piece)
            if not 3 <= len(normalized) <= 64:
                continue
            if normalized in seen or normalized in singer_names:
                continue
            if _find_markers(piece, _DERIVED_TITLE_REJECT_MARKERS):
                continue
            if re.search(r"(?i)(?:^|\s)(?:feat\.?|ft\.?|vocal(?:s)?|music|movie|mix)\b", piece):
                continue
            singer_hits = _find_markers(piece, VOCAL_SYNTH_MARKERS)
            if singer_hits:
                credit_residue = normalized
                for hit in singer_hits:
                    credit_residue = credit_residue.replace(
                        normalize_search_text(hit), ""
                    )
                if len(credit_residue) <= 2:
                    continue
            seen.add(normalized)
            variants.append(piece)
            if len(variants) >= limit:
                break
    return variants


@dataclass(frozen=True)
class CandidateAssessment:
    score: int
    match_quality: str
    title_match: bool
    song_signal: bool
    rejected_reason: str | None = None
    original_signal: bool = False
    match_source: str = "request"


def assess_candidate(
    track: dict[str, Any],
    query: str,
    *,
    position: int = 0,
    query_variants: Iterable[str] | None = None,
    derived_query_variants: Iterable[str] | None = None,
) -> CandidateAssessment:
    """Score a candidate while keeping exclusion reasons observable."""

    title = str(track.get("title") or "")
    author = str(track.get("author") or "")
    tags = " ".join(str(tag) for tag in track.get("tags") or [])
    description = str(track.get("description") or "")
    category = str(track.get("category") or "")
    title_norm = normalize_search_text(title)
    query_pairs: list[tuple[str, str, str, int]] = []
    query_seen: set[str] = set()
    for source, penalty, values in (
        ("request", 0, [query, *(query_variants or [])]),
        ("derived", 22, list(derived_query_variants or [])),
    ):
        for value in values:
            normalized = normalize_search_text(value)
            if normalized and normalized not in query_seen:
                query_seen.add(normalized)
                query_pairs.append((str(value), normalized, source, penalty))
    query_values = [normalized for _, normalized, _, _ in query_pairs]
    query_norm = query_values[0] if query_values else ""
    metadata = f"{title} {author} {tags} {description} {category}"
    metadata_norm = normalize_search_text(metadata)

    if not query_norm:
        return CandidateAssessment(-1000, "none", False, False, "点歌词为空")

    hard_negatives = _find_markers(title, HARD_NEGATIVE_MARKERS)
    if hard_negatives:
        return CandidateAssessment(
            -1000,
            "rejected",
            any(value in title_norm for value in query_values),
            False,
            f"标题含排除词：{hard_negatives[0]}",
        )
    tagged_negatives = _find_markers(f"{tags} {category}", HARD_NEGATIVE_MARKERS)
    if tagged_negatives:
        return CandidateAssessment(
            -1000,
            "rejected",
            any(value in title_norm for value in query_values),
            False,
            f"标签含排除词：{tagged_negatives[0]}",
        )

    match_candidates: list[tuple[int, str, str]] = []
    for value, normalized, source, penalty in query_pairs:
        if title_norm == normalized:
            match_candidates.append((150 - penalty, "exact", source))
        elif title_norm.startswith(normalized):
            match_candidates.append((128 - penalty, "prefix", source))
        elif normalized in title_norm:
            match_candidates.append((105 - penalty, "title", source))
        elif _best_title_similarity(title, value) >= 0.62:
            match_candidates.append((90 - penalty, "fuzzy", source))
        elif normalized in metadata_norm:
            match_candidates.append((35 - penalty, "metadata", source))
        else:
            match_candidates.append((-70, "none", source))
    score, match_quality, match_source = max(
        match_candidates,
        key=lambda item: (item[0], item[2] == "request"),
        default=(-70, "none", "request"),
    )

    signal_context = f"{title} {author} {tags} {category}"
    vocal_title = bool(_find_markers(f"{title} {tags}", VOCAL_SYNTH_MARKERS))
    vocal_metadata = bool(_find_markers(signal_context, VOCAL_SYNTH_MARKERS))
    original_title = bool(_find_markers(title, ORIGINAL_MARKERS))
    original_metadata = bool(_find_markers(signal_context, ORIGINAL_MARKERS))
    strong_original_title = bool(_find_markers(title, STRONG_ORIGINAL_MARKERS))
    strong_original_metadata = bool(
        _find_markers(f"{author} {tags} {category}", STRONG_ORIGINAL_MARKERS)
    )
    home_upload_title = bool(_find_markers(title, ("本家投稿", "本家")))
    home_upload_metadata = bool(
        _find_markers(f"{author} {tags} {category}", ("本家投稿", "本家"))
    )
    official_author = _marker_present(author, "official") or "官方" in author
    producer_credits = re.findall(
        r"(?im)^(?:produced\s+by|music(?:\s*&\s*lyrics)?\s*[:：])\s*"
        r"([^\n/|]{2,50})",
        unicodedata.normalize("NFKC", description),
    )
    external_source_credit = vocal_title and any(
        normalize_search_text(credit) in title_norm
        for credit in producer_credits
        if normalize_search_text(credit)
    )
    song_signal = vocal_metadata or original_metadata or official_author
    original_signal = (
        strong_original_title
        or strong_original_metadata
        or official_author
        or external_source_credit
    )

    if _marker_present(title, "ai") and not strong_original_title:
        return CandidateAssessment(
            score=-1000,
            match_quality="rejected",
            title_match=match_quality in {"exact", "prefix", "title", "fuzzy"},
            song_signal=song_signal,
            rejected_reason="标题标注 AI 版本",
            original_signal=False,
            match_source=match_source,
        )

    if vocal_title:
        score += 30
    elif vocal_metadata:
        score += 18
    if home_upload_title:
        score += 86
    elif strong_original_title:
        score += 56
    elif original_title:
        # "原版" and "feat" are easy for repost titles to claim. They help,
        # but are not proof of a home/official upload on their own.
        score += 12
        copyright_value = _safe_int(track.get("copyright"))
        if copyright_value not in {0, 1}:
            score -= 24
    elif home_upload_metadata:
        score += 44
    elif strong_original_metadata:
        score += 24
    elif original_metadata:
        score += 12
    if official_author:
        score += 16
    if external_source_credit:
        # Old Bilibili reprints of the Niconico/YouTube original often have no
        # "原曲" tag, but preserve the source ID and producer credits.
        score += 40
    if _safe_int(track.get("copyright")) == 1:
        score += 10
    if not song_signal:
        score -= 80
    elif match_quality == "metadata" and position <= 2:
        # B站搜索偶尔只在简介或标签保留日文原名，标题已经换成中文译名。
        # 仅给搜索页最前面的强术曲信号结果加权，避免普通视频借简介蹭分。
        score += 25

    light_soft = _find_markers(title, LIGHT_SOFT_NEGATIVE_MARKERS)
    light_norms = {normalize_search_text(marker) for marker in light_soft}
    heavy_soft = tuple(
        marker
        for marker in _find_markers(title, SOFT_NEGATIVE_MARKERS)
        if normalize_search_text(marker) not in light_norms
    )
    score -= min(54, 18 * _distinct_marker_count(heavy_soft))
    score -= min(12, 6 * _distinct_marker_count(light_soft))
    editorial_markers = _find_markers(title, EDITORIAL_TITLE_MARKERS)
    score -= min(42, 14 * _distinct_marker_count(editorial_markers))
    if _find_markers(f"{description} {tags}", HARD_NEGATIVE_MARKERS):
        score -= 8

    duration = parse_duration(track.get("duration"))
    if 0 < duration < 50 and not original_signal:
        return CandidateAssessment(
            score=-1000,
            match_quality="rejected",
            title_match=match_quality in {"exact", "prefix", "title", "fuzzy"},
            song_signal=song_signal,
            rejected_reason="时长过短，疑似片段或短视频",
            original_signal=original_signal,
        )
    if 60 <= duration <= 600:
        score += 8
    elif 20 <= duration <= 900:
        score += 2
    elif duration > 1800:
        score -= 15

    views = _safe_int(track.get("play"))
    favorites = _safe_int(track.get("favorites"))
    if views:
        score += min(10, int(math.log10(views + 1) * 2))
    if favorites:
        score += min(6, int(math.log10(favorites + 1)))
    score += max(0, 8 - min(max(0, position), 8))
    origin_count = len(
        {
            normalize_search_text(origin)
            for origin in track.get("search_origins") or []
            if normalize_search_text(origin)
        }
    )
    if origin_count > 1:
        score += min(12, 4 * (origin_count - 1))

    return CandidateAssessment(
        score=score,
        match_quality=match_quality,
        title_match=match_quality in {"exact", "prefix", "title", "fuzzy"},
        song_signal=song_signal,
        original_signal=original_signal,
        match_source=match_source,
    )


def rank_search_candidates(
    tracks: Iterable[dict[str, Any]],
    query: str,
    *,
    minimum_score: int = 90,
    query_variants: Iterable[str] | None = None,
    derived_query_variants: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    """Return safe, relevant candidates sorted by confidence."""

    ranked: list[dict[str, Any]] = []
    seen: set[str] = set()
    for position, source_track in enumerate(tracks):
        track = dict(source_track)
        identity = str(track.get("bvid") or track.get("url") or "").strip()
        if identity and identity in seen:
            continue
        if identity:
            seen.add(identity)
        effective_position = _safe_int(track.get("best_search_position"))
        if "best_search_position" not in track:
            effective_position = position
        assessment = assess_candidate(
            track,
            query,
            position=effective_position,
            query_variants=query_variants,
            derived_query_variants=derived_query_variants,
        )
        track["search_score"] = assessment.score
        track["search_match"] = assessment.match_quality
        track["search_original"] = assessment.original_signal
        track["search_match_source"] = assessment.match_source
        if assessment.rejected_reason:
            track["search_rejected_reason"] = assessment.rejected_reason
            continue
        metadata_match_allowed = assessment.song_signal and (
            assessment.score >= minimum_score + 20
            or (effective_position <= 2 and assessment.score >= minimum_score)
        )
        if not assessment.song_signal or assessment.score < minimum_score or not (
            assessment.title_match or metadata_match_allowed
        ):
            continue
        ranked.append(track)

    match_priority = {
        "exact": 4,
        "prefix": 3,
        "title": 2,
        "fuzzy": 1,
        "metadata": 0,
    }
    ranked.sort(
        key=lambda item: (
            int(item.get("search_score") or 0),
            item.get("search_match_source") == "request",
            bool(item.get("search_original")),
            match_priority.get(str(item.get("search_match") or ""), -1),
            _safe_int(item.get("favorites")),
            _safe_int(item.get("play")),
        ),
        reverse=True,
    )
    return ranked
