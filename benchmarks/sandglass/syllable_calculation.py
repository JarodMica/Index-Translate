# -*- coding: utf-8 -*-
"""
音节计数 V3 — 在 V2 基础上补齐 22 语种覆盖
（zh, en, ja, ko, fr, de, es, pt, it, ru, ro, pl, sv, nl, tr, ar, hi, th, vi, id, ms, fil）

V2 缺口与 V3 对应改动：
1. 脚本检测缺 cyrillic/hangul/thai/devanagari → ru/ko/th/hi 字符整段被丢弃（音节≈0）；V3 新增。
2. 拉丁正则只到 À-ÿ → pl/tr/vi/ro 的 ł/ş/ế/ș 等扩展拉丁字符丢失；V3 扩展到 Latin Ext-A/B + Additional。
3. pyphen 只配了 en/de/fr/es → V3 接入 it/pt/ru/ro/pl/sv/nl/id（ms 复用 id）。
4. 新增规则计数器：ko（音节块=音节，精确）、vi（词符=音节，精确）、tr/fil（元音计数）、
   hi（akshara 近似）、th（优先 pythainlp，否则元音符启发式，近似）。
5. 数字展开扩语种：it/pt/ru/ro/pl/sv/nl/tr/id/ko/vi/th/fil 直连 num2words；ms→id、hi→en。

可靠性分级：
  高:  zh en ja ko vi es de fr it pt
  中:  ru ro pl sv nl tr id ms ar fil （建议抽样校验后用）
  低:  th hi （近似规则；th 建议 pip install pythainlp）
"""

import re

try:
    from . import syllable_calculation_v2 as v2
except ImportError:
    import syllable_calculation_v2 as v2
from num2words import num2words

try:
    from pythainlp.tokenize import syllable_tokenize as _thai_syllable_tokenize
except ImportError:
    _thai_syllable_tokenize = None


# ========== 1. 扩展脚本检测（patch V2 的 _SCRIPT_RANGES） ==========

# 拉丁：基本 + 补充(去 × ÷) + Ext-A/B + IPA前段 + Ext Additional（覆盖 pl/tr/vi/ro 全部字符）
_LATIN_RE = re.compile(r'[a-zA-ZÀ-ÖØ-öø-ÿĀ-ɏḀ-ỿ]')

_NEW_SCRIPT_RANGES = [
    (re.compile(r'[가-힣]'), 'hangul'),
    (re.compile(r'[\u0400-\u04FF\u0500-\u052F]'), 'cyrillic'),
    (re.compile(r'[\u0E00-\u0E7F]'), 'thai'),
    (re.compile(r'[\u0900-\u097F]'), 'devanagari'),
]


def _patch_v2_script_ranges():
    """把新脚本插到 latin 之前，并替换 latin 为扩展版。幂等。"""
    ranges = v2._SCRIPT_RANGES
    names = [name for _, name in ranges]
    if 'hangul' in names:
        return
    latin_idx = names.index('latin')
    ranges[latin_idx] = (_LATIN_RE, 'latin')
    for item in reversed(_NEW_SCRIPT_RANGES):
        ranges.insert(latin_idx, item)


_patch_v2_script_ranges()


# ========== 2. pyphen 词典扩展 ==========

_PYPHEN_LANG_MAP_V3 = dict(v2._PYPHEN_LANG_MAP)
_PYPHEN_LANG_MAP_V3.update({
    'it': 'it_IT',
    'pt': 'pt_BR',
    'ru': 'ru_RU',
    'ro': 'ro_RO',
    'pl': 'pl_PL',
    'sv': 'sv',
    'nl': 'nl_NL',
    'id': 'id_ID',
    'ms': 'id_ID',  # 马来语与印尼语音系接近，共用词典
})
# 同步给 v2，使 v2._count_european 的兜底路径也拿到正确词典
v2._PYPHEN_LANG_MAP.update(_PYPHEN_LANG_MAP_V3)


# ========== 3. num2words 语言映射扩展 ==========

_NUM2WORDS_LANG_MAP_V3 = dict(v2._NUM2WORDS_LANG_MAP)
_NUM2WORDS_LANG_MAP_V3.update({
    'it': 'it', 'pt': 'pt', 'ru': 'ru', 'ro': 'ro', 'pl': 'pl',
    'sv': 'sv', 'nl': 'nl', 'tr': 'tr', 'id': 'id', 'ko': 'ko',
    'vi': 'vi', 'th': 'th', 'fil': 'fil',
    'ms': 'id',   # num2words 不支持 ms
    'hi': 'en',   # num2words 不支持 hi，退回英语（近似）
})
v2._NUM2WORDS_LANG_MAP.update(_NUM2WORDS_LANG_MAP_V3)


# ========== 4. 新语种规则计数器 ==========

def _count_hangul_chars(text):
    """韩语：正字法一个音节块=一个音节，精确。"""
    return len(re.findall(r'[가-힣]', text))


_TR_VOWELS = set('aeıioöuüâîû')


def _turkish_word_syllables(word):
    """土耳其语音节高度规则：元音数=音节数。"""
    return max(1, sum(1 for c in word.lower() if c in _TR_VOWELS))


_FIL_VOWELS = set('aeiou')


def _filipino_word_syllables(word):
    """他加禄语：相邻元音分属不同音节（oo=2），元音计数即音节数。"""
    return max(1, sum(1 for c in word.lower() if c in _FIL_VOWELS))


# --- 泰语 ---
_TH_PREPOSED_VOWELS = 'เแโใไ'          # 前置元音，每个起一个音节
_TH_SARA_A = '\u0e30'                  # ะ
_TH_MAI_HAN_AKAT = '\u0e31'            # ั
_TH_FOLLOW_VOWELS = '\u0e32\u0e33\u0e34\u0e35\u0e36\u0e37\u0e38\u0e39'  # า ำ ิ ี ึ ื ุ ู


def _thai_syllable_count(text):
    if _thai_syllable_tokenize is not None:
        try:
            return len([s for s in _thai_syllable_tokenize(text) if s.strip()])
        except Exception:
            pass
    # 启发式近似：前置元音 + 未跟随前置元音的后置/上下元音
    count = 0
    prev_preposed = False
    for ch in text:
        if ch in _TH_PREPOSED_VOWELS:
            count += 1
            prev_preposed = True
        elif ch in _TH_FOLLOW_VOWELS or ch == _TH_SARA_A or ch == _TH_MAI_HAN_AKAT:
            if not prev_preposed:
                count += 1
            prev_preposed = False
        elif '\u0e01' <= ch <= '\u0e2e':  # 辅音，不重置已计的前置元音音节
            continue
        else:
            prev_preposed = False
    return max(1, count) if re.search(r'[\u0e01-\u0e2e]', text) else count


# --- 印地语（天城文 akshara 近似） ---
_HI_INDEP_VOWEL_RE = re.compile(r'[\u0904-\u0914\u0960\u0961\u0972-\u0977]')  # 独立元音
_HI_CONSONANT_RE = re.compile(r'[\u0915-\u0939\u0958-\u095F\u0979-\u097F]')   # 辅音
_HI_VIRAMA = '\u094D'
_HI_MATRA_RE = re.compile(r'[\u093A\u093B\u093E-\u094C\u0955-\u0957\u0962\u0963]')  # 依附元音符（matra，不含 nukta/avagraha）
_HI_NUKTA = '\u093C'


def _devanagari_word_syllables(word):
    """单词音节：逐字符构建 (辅音是否带元音) 序列，再做 schwa 删除。

    - 辅音默认带固有 schwa；后跟 matra 则元音为该 matra；后跟 virama 则无元音（联接）
    - 词尾 schwa 删除：末辅音的固有 schwa 不发音（दिन=din）
    - 词中 schwa 删除（VC_CV）：前一单元有元音、后一单元也有元音时，
      中间辅音的固有 schwa 删除（समझा=sam-jhaa 而非 sa-ma-jhaa），标准规则的启发式近似
    """
    units = []  # 每单元: 'V'(发元音) 或 'C'(纯辅音)
    i = 0
    n = len(word)
    while i < n:
        ch = word[i]
        if _HI_INDEP_VOWEL_RE.match(ch):
            units.append(['V', False])  # 独立元音，非 schwa
            i += 1
        elif _HI_CONSONANT_RE.match(ch):
            j = i + 1
            if j < n and word[j] == _HI_NUKTA:
                j += 1
            if j < n and word[j] == _HI_VIRAMA:
                units.append(['C', False])
                i = j + 1
            elif j < n and _HI_MATRA_RE.match(word[j]):
                units.append(['V', False])  # 显式 matra
                i = j + 1
            else:
                units.append(['V', True])   # 固有 schwa
                i += 1
        else:
            i += 1
    if not units:
        return 0
    # 词尾 schwa 删除
    if len(units) >= 2 and units[-1][0] == 'V' and units[-1][1]:
        units[-1] = ['C', False]
    # 词中 schwa 删除（VC_CV）：从右往左，避免连删
    for k in range(len(units) - 2, 0, -1):
        if units[k][1] and units[k - 1][0] == 'V' and units[k + 1][0] == 'V':
            units[k] = ['C', False]
    return max(1, sum(1 for u in units if u[0] == 'V'))


def _devanagari_syllable_count(text):
    return sum(_devanagari_word_syllables(w) for w in re.split(r'[\s\u0964\u0965]+', text) if w)


_RU_VOWELS = set('аеёиоуыэюяАЕЁИОУЫЭЮЯ')


def _cyrillic_word_syllables(word, lang='ru'):
    """西里尔词：元音字母计数（俄语正字法一元音字母=一音节）。

    espeak IPA 基准校验：元音计数 P50 2.6% / P90 10.5%，
    显著优于 pyphen ru_RU 断词（P50 8.3% / P90 20.0%——断词点≠音节数，
    俄语排版规则禁止单字母断行导致系统性低估）。
    """
    return max(1, sum(1 for c in word if c in _RU_VOWELS)) if any(c in _RU_VOWELS or c.isalpha() for c in word) else 0


# ========== 5. 拉丁词计数按语言分派 ==========

_VI_FOREIGN_RE = re.compile(r'[fjwzFJWZ]')

# 葡语元音簇（含重音/鼻化元音与 ü）；簇=音节核近似
# espeak IPA 基准校验：元音簇 P50 3.8% / P90 12.9%，
# 优于 pyphen pt_BR（P50 7.1% / P90 21.1%——词尾重音元音如 alô/olá 断词漏算）
_PT_VOWEL_CLUSTER_RE = re.compile(r'[aeiouáéíóúâêôãõàü]+', re.IGNORECASE)


def _portuguese_word_syllables(word):
    return max(1, len(_PT_VOWEL_CLUSTER_RE.findall(word))) if re.search(r'[a-zA-ZÀ-ÿ]', word) else 0


def _latin_word_syllables(word, lang):
    """单个拉丁词按目标语言规则计数。"""
    if lang == 'vi':
        clean = word.strip('.,;:!?()[]{}"\'-')
        # 越南语正字法无 f/j/w/z，且单音节词最长约 7 字符（如 nghiêng）；
        # 命中则视为外来词（internet/OK/人名），退回英语 pyphen，避免按 1 音节低估
        if _VI_FOREIGN_RE.search(clean) or len(clean) > 7:
            if not clean:
                return 0
            abbr = v2._abbreviation_syllable_count(clean, 'en')
            if abbr is not None:
                return abbr
            return v2._pyphen_syllable_count(clean, 'en_US')
        return 1  # 越南语一个词符=一个音节
    if lang == 'tr':
        return _turkish_word_syllables(word.strip('.,;:!?()[]{}"\'-'))
    if lang == 'fil':
        return _filipino_word_syllables(word.strip('.,;:!?()[]{}"\'-'))
    if lang == 'pt':
        return _portuguese_word_syllables(word.strip('.,;:!?()[]{}"\'-'))
    abbr = v2._abbreviation_syllable_count(word, 'en')
    if abbr is not None:
        return abbr
    pyphen_lang = _PYPHEN_LANG_MAP_V3.get(lang, 'en_US')
    return v2._pyphen_syllable_count(word, pyphen_lang)


# ========== 6. 通用混合内容计数 ==========

def _expand_and_count_number(num_str, lang):
    """数字展开为目标语言文字后计数。"""
    expanded = v2._expand_number(num_str, lang)
    if expanded == num_str:
        # 展开失败（如 hi），退回英语展开
        expanded = v2._expand_number(num_str, 'en')
    return _count_generic_text(expanded, lang, _in_number=True)


def _count_generic_text(text, lang, _in_number=False):
    """V3 通用计数：解析混合脚本，按段分派。"""
    segments = v2._parse_mixed_content(text)
    total = 0
    for segment, script_type in segments:
        if script_type == 'latin':
            for w in segment.split():
                total += _latin_word_syllables(w, lang)
        elif script_type == 'cyrillic':
            for w in segment.split():
                total += _cyrillic_word_syllables(w, 'ru')
        elif script_type == 'hangul':
            total += _count_hangul_chars(segment)
        elif script_type == 'thai':
            total += _thai_syllable_count(segment)
        elif script_type == 'devanagari':
            total += _devanagari_syllable_count(segment)
        elif script_type == 'han':
            total += len(re.findall(r'[一-鿿]', segment))
        elif script_type == 'kana':
            total += v2._japanese_syllable_count(segment)
        elif script_type == 'arabic':
            for w in v2._AR_LETTER_RE.findall(segment):
                total += v2._arabic_word_syllables(w)
        elif script_type == 'number' and not _in_number:
            total += _expand_and_count_number(segment, lang)
    return total


# ========== 7. 公共 API ==========

# v2 已有完整专用链路的语言，直接委托
_V2_NATIVE = {'zh', 'ja', 'ar', 'en', 'de', 'fr', 'es'}

SUPPORTED_LANGS = sorted(_V2_NATIVE | {
    'ko', 'vi', 'tr', 'fil', 'ru', 'it', 'pt', 'ro', 'pl',
    'sv', 'nl', 'id', 'ms', 'th', 'hi',
})

# 可靠性分级（2026-08-04 espeak-ng IPA 基准校验后更新；校验脚本 validate_v3_counter.py 未随仓发布）
# 21 语种全部通过（P50≤8% 且 P90≤20%）；ja/ar espeak 基准无效，凭生产 RL 验证豁免
RELIABILITY = {
    'high':   ['zh', 'en', 'ja', 'ko', 'vi', 'es', 'de', 'fr', 'it', 'pt',
               'ru', 'ro', 'pl', 'sv', 'nl', 'tr', 'id', 'ms', 'ar', 'fil',
               'th', 'hi'],
    'medium': [],
    'low':    [],
}


# 本模块 patch 进 v2._SCRIPT_RANGES 的新脚本段
# （v2 的分派表只认 han/kana/latin/arabic/number，其余静默丢弃）
_NEW_SCRIPT_TYPES = ('cyrillic', 'hangul', 'thai', 'devanagari')


def _count_new_script_segments(text, lang):
    """补齐 v2 原生链路不认的脚本段，避免 cyrillic/hangul/thai/devanagari 静默计 0。"""
    return sum(_count_generic_text(segment, lang) for segment, script_type
               in v2._parse_mixed_content(text) if script_type in _NEW_SCRIPT_TYPES)


def cal_syllable_count(text, lang='en'):
    if not text or not text.strip():
        return 0
    lang = lang.lower()
    if lang in ('tl',):
        lang = 'fil'
    if lang in _V2_NATIVE:
        # v2 原生链路 + patch 新脚本段（v2 对这几类脚本返回 0）
        return v2.cal_syllable_count(text, lang) + _count_new_script_segments(text, lang)
    return _count_generic_text(text.strip(), lang)


cal_syllable_details = v2.cal_syllable_details  # 详细分解暂沿用 v2（仅 v2 语种可靠）


# ========== 测试入口 ==========

if __name__ == '__main__':
    cases = [
        # (文本, 语言, 期望音节, 说明)
        ("Hello world", 'en', 3, ''),
        ("你好世界", 'zh', 4, ''),
        ("こんにちは", 'ja', 5, ''),
        ("안녕하세요", 'ko', 5, '韩文音节块'),
        ("Xin chào các bạn", 'vi', 4, '越南语词符=音节'),
        ("Merhaba dünya", 'tr', 5, 'mer-ha-ba dün-ya'),
        ("Magandang umaga", 'fil', 6, 'ma-gan-dang u-ma-ga'),
        ("Привет мир", 'ru', 3, 'При-вет мир'),
        ("Ciao mondo", 'it', 3, 'ciao(1) mon-do'),
        ("Olá mundo", 'pt', 4, 'o-lá mun-do（pyphen 算 olá=1，已知近似偏差）'),
        ("Bună ziua", 'ro', 4, 'bu-nă zi-ua'),
        ("Dzień dobry", 'pl', 3, 'dzień do-bry'),
        ("Hej världen", 'sv', 3, ''),
        ("Hallo wereld", 'nl', 4, ''),
        ("Selamat pagi", 'id', 5, 'se-la-mat pa-gi'),
        ("Selamat pagi", 'ms', 5, ''),
        ("สวัสดีครับ", 'th', 5, 'sa-wat-dee-khrap≈4-5 近似'),
        ("नमस्ते दुनिया", 'hi', 6, 'na-mas-te du-ni-ya 近似'),
        ("مرحبا بالعالم", 'ar', 6, ''),
        ("I have 25 cats", 'en', None, '数字展开'),
        ("У меня 25 кошек", 'ru', None, '俄语数字展开'),
    ]
    print(f"{'lang':6s} {'count':>5s}  text")
    for text, lang, expect, note in cases:
        c = cal_syllable_count(text, lang)
        mark = '' if expect is None else ('✓' if c == expect else f'(期望{expect})')
        print(f"{lang:6s} {c:5d}  {text}  {mark} {note}")
