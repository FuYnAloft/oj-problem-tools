"""Convert one Markdown problem into an OpenJudge OJ Inject V2 script.

The public API is :func:`generate_injection_script`.  Raw HTML is deliberately
allowed because the generated description has the same trust model as the
original browser project.
"""

from __future__ import annotations

import base64
import gzip
import html as html_module
import json
import math
import re
import warnings
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from latex2mathml.converter import convert as latex_to_mathml
from markdown_it import MarkdownIt
from markdown_it.token import Token
from mdit_py_plugins.dollarmath import dollarmath_plugin
from mdit_py_plugins.tasklists import tasklists_plugin
from pygments import highlight as pygments_highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import CLexer, CppLexer, PythonLexer

FIELD_LIMIT = 65_535
PAYLOAD_FIELDS = ("input", "output", "sampleInput", "sampleOutput")
ALLOWED_STYLES = frozenset(
    {"none", "github", "github-tweaked", "github-tweaked-compact"}
)
MD_TWEAKS_STYLE_RESOURCES = {
    "github": "markdown-oj-fix.css",
    "github-tweaked": "markdown-tweaks.css",
    "github-tweaked-compact": "markdown-tweaks-compact.css",
}

DESCRIPTION = (
    "<p>题目描述加载中。如果持续看到此说明，请确认浏览器没有禁用 JavaScript，并查看是否有加载错误。</p>"
    '<p>本题使用 <a href="https://github.com/FuYnAloft/oj-inject">'
    "OJ Inject（FuYnAloft/oj-inject）</a> 构建。</p>"
    '<p>无需浏览器也可从本页 HTML 提取题面和源码：查找 type="application/x-oj-inject-data" '
    "的数据节点，根据源码节点的 data-parts 数量，按 data-part 从 0 开始依次拼接文本，再进行 Base64 解码、"
    "gzip 解压和 UTF-8 解码，即得到 HTML 题面。查找 type=\"application/x-oj-inject-source\" "
    "的 script 数据节点，对文本做同样的解码，即得到 Markdown 原文（或 HTML 原文，data-format "
    "表示源码格式）。</p>"
    "<p>也可以从上方的仓库下载 public/extract.mjs，用 Node.js 执行："
    "<code>node extract.mjs page.html recovered</code>，输出 recovered.html 和 recovered.md"
    "（或 recovered.source.html）。适用于服务器返回的页面源码，以及保留数据节点的渲染后 HTML。</p>"
)

# Kept on one line so embedding it in an OpenJudge field cannot be affected by
# line-oriented HTML processing.
LOADER = (
    "<script>(function(){"
    "const dl=document.currentScript?.closest('dl.problem-content');"
    "if(!dl)return;"
    "const visibility=dl.style.visibility;"
    "dl.style.visibility='hidden';"
    "const ready=document.readyState==='loading'?new Promise(resolve=>document.addEventListener('DOMContentLoaded',resolve,{once:true})):Promise.resolve();"
    "ready.then(async()=>{"
    "try{"
    "const source=dl.querySelector('script[type=\"application/x-oj-inject-source\"]');"
    "if(!source||source.dataset.version!=='2')throw new Error('源码数据缺失');"
    "const count=source.dataset.parts===undefined?4:Number(source.dataset.parts);"
    "if(!Number.isInteger(count)||count<1||count>4)throw new Error('题面分块数量无效');"
    "const parts=[];"
    "for(let i=0;i<count;i++){"
    "const matches=dl.querySelectorAll('script[type=\"application/x-oj-inject-data\"][data-part=\"'+i+'\"]');"
    "if(matches.length!==1||matches[0].dataset.version!=='2')throw new Error('题面数据缺失或版本不支持');"
    "parts.push(matches[0]);"
    "}"
    "const bytes=Uint8Array.from(atob(parts.map(part=>part.textContent).join('')),c=>c.charCodeAt(0));"
    "const html=await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'))).text();"
    "const range = document.createRange();"
    "const fragment = range.createContextualFragment(html);"
    "dl.replaceChildren(fragment);"
    "dl.append(...parts,source);"
    "}catch(error){"
    "const message=document.createElement('dd');"
    "message.textContent='OJ Inject 加载失败：'+error.message;"
    "dl.append(message);"
    "}finally{dl.style.visibility=visibility;}"
    "});"
    "})();</script>"
)

_OPEN_REMOVE_RE = re.compile(
    r"^[ \t]{0,3}(:{3,})[ \t]*oj-remove(?=$|[ \t\[{]).*$"
)
_CLOSE_REMOVE_RE = re.compile(r"^[ \t]{0,3}(:{3,})[ \t]*$")
_FENCE_OPEN_RE = re.compile(r"^[ ]{0,3}(`{3,}|~{3,})(.*)$")


@dataclass(frozen=True, slots=True)
class _Config:
    style: str = "github-tweaked"
    widening: int | float = 0
    single_line_break: bool = True
    strip_oj_remove: bool = True


@dataclass(frozen=True, slots=True)
class _Line:
    start: int
    end: int
    text: str


@dataclass(frozen=True, slots=True)
class _Frontmatter:
    start: int
    end: int
    data: dict[Any, Any]


@dataclass(frozen=True, slots=True)
class _Heading:
    token_index: int
    start_line: int
    end_line: int
    title: str


@dataclass(frozen=True, slots=True)
class _RemoveFrame:
    start: int
    marker_length: int


def _source_lines(source: str) -> list[_Line]:
    lines: list[_Line] = []
    offset = 0
    for raw_line in source.splitlines(keepends=True):
        end = offset + len(raw_line)
        lines.append(_Line(offset, end, raw_line.rstrip("\r\n")))
        offset = end
    if offset < len(source):
        # splitlines(keepends=True) normally includes this case; keep the helper
        # correct for unusual Unicode line separators as well.
        lines.append(_Line(offset, len(source), source[offset:]))
    return lines


def _is_frontmatter_delimiter(line: str, *, allow_bom: bool = False) -> bool:
    if allow_bom:
        line = line.removeprefix("\ufeff")
    return line.strip(" \t") == "---"


def _load_frontmatter(yaml_source: str) -> dict[Any, Any]:
    try:
        value = yaml.safe_load(yaml_source)
    except yaml.YAMLError as error:
        raise ValueError(f"frontmatter YAML 无效：{error}") from error
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("frontmatter 必须是键值对象")
    return dict(value)


def _frontmatter_at_start(source: str) -> _Frontmatter | None:
    lines = _source_lines(source)
    if not lines or not _is_frontmatter_delimiter(lines[0].text, allow_bom=True):
        return None
    for close_index in range(1, len(lines)):
        if _is_frontmatter_delimiter(lines[close_index].text):
            return _Frontmatter(
                start=0,
                end=lines[close_index].end,
                data=_load_frontmatter(source[lines[0].end : lines[close_index].start]),
            )
    raise ValueError("文档开头的 frontmatter 未闭合")


def _inline_text(tokens: Sequence[Token] | None) -> str:
    if not tokens:
        return ""
    parts: list[str] = []
    for token in tokens:
        if token.type in {"text", "code_inline", "html_inline", "math_inline"}:
            parts.append(token.content)
        elif token.type == "image":
            parts.append(token.content)
        elif token.type in {"softbreak", "hardbreak"}:
            parts.append("\n")
    return "".join(parts)


def _parse_headings(source: str) -> tuple[list[Token], list[_Heading]]:
    parser = MarkdownIt("commonmark", {"html": True})
    tokens = parser.parse(source)
    headings: list[_Heading] = []
    for index, token in enumerate(tokens):
        if token.type != "heading_open" or token.tag != "h1" or token.level != 0:
            continue
        if token.map is None:
            continue
        inline = tokens[index + 1] if index + 1 < len(tokens) else None
        title = _inline_text(inline.children if inline and inline.type == "inline" else None)
        headings.append(
            _Heading(
                token_index=index,
                start_line=token.map[0],
                end_line=token.map[1],
                title=title.strip(),
            )
        )
    return tokens, headings


def _legacy_frontmatter_after_heading(
    source: str, heading: _Heading
) -> _Frontmatter | None:
    lines = _source_lines(source)
    index = heading.end_line
    while index < len(lines) and not lines[index].text.strip():
        index += 1
    if index >= len(lines) or not _is_frontmatter_delimiter(lines[index].text):
        return None
    for close_index in range(index + 1, len(lines)):
        if _is_frontmatter_delimiter(lines[close_index].text):
            return _Frontmatter(
                start=lines[index].start,
                end=lines[close_index].end,
                data=_load_frontmatter(source[lines[index].end : lines[close_index].start]),
            )
    # A lone thematic break after the title is valid Markdown, so it is only
    # considered legacy frontmatter when a closing delimiter is also present.
    return None


def _without_span(source: str, start: int, end: int) -> str:
    return source[:start] + source[end:]


def _line_start(source: str, line_number: int) -> int:
    lines = _source_lines(source)
    if line_number >= len(lines):
        return len(source)
    return lines[line_number].start


def _extract_document(
    source: str,
) -> tuple[dict[Any, Any], _Config, str, str, int, _Frontmatter | None]:
    standard = _frontmatter_at_start(source)
    probe_source = (
        _without_span(source, standard.start, standard.end) if standard else source
    )
    _, probe_headings = _parse_headings(probe_source)
    if not probe_headings:
        raise ValueError("未找到题目（需要一个顶层一级标题 #）")

    legacy = _legacy_frontmatter_after_heading(probe_source, probe_headings[0])
    if standard and legacy:
        raise ValueError("检测到多块 frontmatter；请只保留文档开头的一块")

    selected = standard
    content = probe_source
    legacy_selected = False
    if not standard and legacy:
        selected = legacy
        content = _without_span(source, legacy.start, legacy.end)
        legacy_selected = True

        # Removing one legacy block can expose a second adjacent block.
        _, once_cleaned_headings = _parse_headings(content)
        if once_cleaned_headings:
            duplicate = _legacy_frontmatter_after_heading(
                content, once_cleaned_headings[0]
            )
            if duplicate:
                raise ValueError("检测到多块 frontmatter；请只保留一块")

    _, headings = _parse_headings(content)
    if not headings:
        raise ValueError("未找到题目（需要一个顶层一级标题 #）")
    if len(headings) > 1:
        raise ValueError("检测到多个顶层一级标题；此实现仅支持单个题目")

    if legacy_selected:
        warnings.warn(
            "检测到一级标题后的兼容式 frontmatter；建议将它移动到 Markdown 文档开头。",
            UserWarning,
            stacklevel=3,
        )

    params = selected.data if selected else {}
    config = _parse_config(params.get("config")) if "config" in params else _Config()
    heading = headings[0]
    body_start = _line_start(content, heading.end_line)
    body = content[body_start:]
    return params, config, heading.title, body, body_start, selected


def _parse_config(raw_config: Any) -> _Config:
    if not isinstance(raw_config, Mapping):
        raise ValueError("frontmatter.config 必须是键值对象")

    style = raw_config.get("style", "github-tweaked")
    widening = raw_config.get("widening", 0)
    single_line_break = raw_config.get("singleLineBreak", True)
    strip_oj_remove = raw_config.get("stripOjRemove", True)

    if not isinstance(style, str) or style not in ALLOWED_STYLES:
        allowed = ", ".join(sorted(ALLOWED_STYLES))
        raise ValueError(f"config.style 必须是以下值之一：{allowed}")
    if (
        isinstance(widening, bool)
        or not isinstance(widening, (int, float))
        or not math.isfinite(widening)
    ):
        raise ValueError("config.widening 必须是有限数字")
    if not isinstance(single_line_break, bool):
        raise ValueError("config.singleLineBreak 必须是布尔值")
    if not isinstance(strip_oj_remove, bool):
        raise ValueError("config.stripOjRemove 必须是布尔值")

    return _Config(style, widening, single_line_break, strip_oj_remove)


def _overlaps(line: _Line, ignored: tuple[int, int] | None) -> bool:
    return bool(ignored and line.start < ignored[1] and line.end > ignored[0])


def _is_fence_close(line: str, marker: str, marker_length: int) -> bool:
    pattern = rf"^[ ]{{0,3}}{re.escape(marker)}{{{marker_length},}}[ \t]*$"
    return re.match(pattern, line) is not None


def _oj_remove_ranges(
    source: str,
    *,
    start_offset: int = 0,
    ignored: tuple[int, int] | None = None,
) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    outer_ranges: list[tuple[int, int]] = []
    marker_ranges: list[tuple[int, int]] = []
    stack: list[_RemoveFrame] = []
    fence_marker: str | None = None
    fence_length = 0

    for line in _source_lines(source):
        if line.start < start_offset or _overlaps(line, ignored):
            continue

        if fence_marker is not None:
            if _is_fence_close(line.text, fence_marker, fence_length):
                fence_marker = None
                fence_length = 0
            continue

        fence = _FENCE_OPEN_RE.match(line.text)
        if fence:
            run = fence.group(1)
            fence_marker = run[0]
            fence_length = len(run)
            continue

        opening = _OPEN_REMOVE_RE.match(line.text)
        if opening:
            stack.append(_RemoveFrame(line.start, len(opening.group(1))))
            marker_ranges.append((line.start, line.end))
            continue

        closing = _CLOSE_REMOVE_RE.match(line.text)
        if closing and stack and len(closing.group(1)) >= stack[-1].marker_length:
            frame = stack.pop()
            marker_ranges.append((line.start, line.end))
            if not stack:
                outer_ranges.append((frame.start, line.end))

    if stack:
        raise ValueError("oj-remove 容器未闭合")
    return outer_ranges, marker_ranges


def _remove_ranges(source: str, ranges: Sequence[tuple[int, int]]) -> str:
    result = source
    for start, end in sorted(ranges, reverse=True):
        result = result[:start] + result[end:]
    return result


def _process_oj_remove(source: str, *, strip: bool) -> str:
    blocks, markers = _oj_remove_ranges(source)
    return _remove_ranges(source, blocks if strip else markers)


def _render_math(content: str, options: dict[str, Any]) -> str:
    display = "block" if options.get("display_mode") else "inline"
    try:
        return latex_to_mathml(content, display=display)
    except Exception as error:  # latex2mathml exposes several parser errors
        message = html_module.escape(str(error), quote=True)
        escaped = html_module.escape(content)
        return f'<span class="katex-error" title="{message}">{escaped}</span>'


def _render_markdown(source: str, config: _Config) -> tuple[str, bool]:
    highlighted = False
    formatter = HtmlFormatter(nowrap=True)
    lexers = {
        "c": CLexer(),
        "h": CLexer(),
        "cpp": CppLexer(),
        "c++": CppLexer(),
        "cc": CppLexer(),
        "cxx": CppLexer(),
        "hpp": CppLexer(),
        "h++": CppLexer(),
        "python": PythonLexer(),
        "py": PythonLexer(),
    }

    def highlight(code: str, language: str, _attributes: str) -> str:
        nonlocal highlighted
        lexer = lexers.get(language.lower())
        if lexer is None:
            return ""
        highlighted = True
        rendered = pygments_highlight(code, lexer, formatter)
        language_class = html_module.escape(language, quote=True)
        return (
            f'<pre><code class="hljs language-{language_class}">'
            f"{rendered}</code></pre>"
        )

    parser = MarkdownIt(
        "gfm-like",
        {
            "html": True,
            "breaks": config.single_line_break,
            "linkify": True,
            "typographer": False,
            "xhtmlOut": False,
            "highlight": highlight,
        },
    )
    parser.use(tasklists_plugin)
    parser.use(dollarmath_plugin, renderer=_render_math)
    return parser.render(source), highlighted


@lru_cache(maxsize=None)
def _resource_text(*segments: str | Path) -> str:
    path = Path(__file__).resolve().parent / "resources" / Path(*segments)
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise RuntimeError(f"无法读取 OJ Inject 资源文件：{path}") from error


def _widening_css(widening: int | float) -> str:
    value = json.dumps(widening, allow_nan=False, separators=(",", ":"))
    return f"""\
:root {{
  --oj-inject-widening: {value}px;
  --oj-inject-stat-max-narrowing: 75px;
  
  --oj-inject-stat-narrowing: clamp(0px, var(--oj-inject-widening), var(--oj-inject-stat-max-narrowing));
  --oj-inject-wrapper-delta: calc(var(--oj-inject-widening) - var(--oj-inject-stat-narrowing));
}}
.problem-page {{
    width: calc(670px + var(--oj-inject-widening));
}}
.problem-statistics {{
    width: calc(234px - var(--oj-inject-stat-narrowing));
}}
#pageTitle {{
    width: calc(932px + var(--oj-inject-wrapper-delta));
}}
#pagebody .wrapper{{
    width: calc(960px + var(--oj-inject-wrapper-delta));
}}
"""


def _post_process_html(raw_html: str, config: _Config, *, highlighted: bool) -> str:
    result = f'<div class="markdown-body">\n{raw_html}\n</div>'
    result = _build_styles(config, highlighted=highlighted) + result
    if config.style != "none":
        result = _resource_text('elements', 'theme-toggle.html') + result
    return result


def _build_styles(config: _Config, *, highlighted: bool) -> str:
    light = dark = common = ""
    light += _resource_text('styles', 'light', 'syntax-highlight.css') if highlighted else ""
    dark += _resource_text('styles', 'dark', 'syntax-highlight.css') if highlighted else ""
    if config.widening != 0:
        common += _widening_css(config.widening)
    if config.style != "none":
        dark += _resource_text('styles', 'dark', 'oj-dark.css')
    if config.style.startswith("github"):
        light += _resource_text('styles', 'light', 'github-markdown.css')
        dark += _resource_text('styles', 'dark', 'github-markdown.css')
        common += _resource_text('styles', 'common', MD_TWEAKS_STYLE_RESOURCES[config.style])

    return f'''\
<style class="theme-light">{light}</style>
<style class="theme-dark" media="(prefers-color-scheme: dark)">{dark}</style>
<style class="theme-common">{common}</style>'''


def _compress_to_base64(text: str) -> str:
    compressed = gzip.compress(text.encode("utf-8"), mtime=0)
    return base64.b64encode(compressed).decode("ascii")


def _field_size(name: str, value: str) -> int:
    size = len(value.encode("utf-8"))
    if size > FIELD_LIMIT:
        raise ValueError(
            f"{name} 字段为 {size} 字节，超过 {FIELD_LIMIT} 字节上限"
        )
    return size


def _pack_fields(html_base64: str, source_base64: str) -> dict[str, str]:
    fields = {"description": DESCRIPTION}
    offset = 0
    total_capacity = 0
    used_parts = 0
    for index, field in enumerate(PAYLOAD_FIELDS):
        opening = (
            '<script type="application/x-oj-inject-data" data-version="2" '
            f'data-part="{index}">'
        )
        closing = "</script>"
        capacity = FIELD_LIMIT - len((opening + closing).encode("utf-8"))
        total_capacity += capacity
        chunk = html_base64[offset : offset + capacity]
        if chunk:
            used_parts += 1
        fields[field] = opening + chunk + closing
        offset += len(chunk)

    if offset != len(html_base64):
        raise ValueError(
            f"题面 Base64 共 {len(html_base64)} 字节，超过四个字段的总载荷容量 "
            f"{total_capacity} 字节"
        )

    fields["hint"] = (
        '<script type="application/x-oj-inject-source" data-version="2" '
        f'data-format="markdown" data-parts="{used_parts}">{source_base64}</script>{LOADER}'
    )
    for name, value in fields.items():
        _field_size(name, value)
    return fields


def _metadata(frontmatter: Mapping[Any, Any], title: str) -> dict[str, Any]:
    values: dict[str, Any] = {"title": title}
    for name in ("timeLimit", "caseTimeLimit", "memoryLimit", "source"):
        value = frontmatter.get(name)
        if value is not None:
            values[name] = value
    return values


def _generate_console_code(fields: Mapping[str, str], params: Mapping[str, Any]) -> str:
    values = {**params, **fields}
    try:
        serialized = json.dumps(
            values,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as error:
        raise ValueError(f"frontmatter 字段无法写入注入脚本：{error}") from error

    return (
        "(function() {\n"
        f"const values = {serialized};\n"
        'const editor = globalThis.tinymce?.get("editor");\n'
        'if (!editor) throw new Error("未找到题目描述编辑器，请在 OpenJudge 题目编辑页执行");\n'
        "const form = document.querySelector('textarea[name=\"description\"]')?.form;\n"
        "const targets = Object.keys(values).map(name => [name, form?.elements.namedItem(name)]);\n"
        'for (const [name, element] of targets) { if (!element || !("value" in element)) throw new Error("未找到字段：" + name); }\n'
        "editor.setContent(values.description);\n"
        "editor.save();\n"
        'for (const [name, element] of targets) { if (name !== "description") element.value = values[name]; }\n'
        'console.info("OJ Inject 已填入，请提交保存。");\n'
        "})();\n"
    )


def _map_clean_offset_to_original(
    offset: int, frontmatter: _Frontmatter | None
) -> int:
    if frontmatter is None or offset <= frontmatter.start:
        return offset
    return offset + frontmatter.end - frontmatter.start


def generate_injection_script(markdown: str) -> str:
    """Return an OpenJudge console injection script for one Markdown problem.

    A standard YAML frontmatter block belongs at the beginning of ``markdown``.
    For compatibility, a block immediately after the title is accepted with a
    :class:`UserWarning`.  Invalid input and OpenJudge field overflows raise
    :class:`ValueError`.
    """

    if not isinstance(markdown, str):
        raise TypeError("markdown 必须是字符串")

    params, config, title, body, clean_body_start, frontmatter = _extract_document(
        markdown
    )
    rendered_source = _process_oj_remove(body, strip=config.strip_oj_remove)
    raw_html, highlighted = _render_markdown(rendered_source, config)
    final_html = _post_process_html(raw_html, config, highlighted=highlighted)

    stored_source = markdown
    if config.strip_oj_remove:
        body_start = _map_clean_offset_to_original(clean_body_start, frontmatter)
        ignored = (
            (frontmatter.start, frontmatter.end) if frontmatter is not None else None
        )
        block_ranges, _ = _oj_remove_ranges(
            markdown, start_offset=body_start, ignored=ignored
        )
        stored_source = _remove_ranges(markdown, block_ranges)

    html_payload = _compress_to_base64(final_html)
    source_payload = _compress_to_base64(stored_source)
    fields = _pack_fields(html_payload, source_payload)
    return _generate_console_code(fields, _metadata(params, title))
