from __future__ import annotations

import re


def estimate_tokens(text: str) -> int:
    """估算 Token 数。优先使用 tiktoken；没有则用中英文混合场景近似估算。"""
    if not text:
        return 0

    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:  # noqa: BLE001
        chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
        other_chars = len(text) - chinese_chars
        return int(chinese_chars / 1.5 + other_chars / 4)


def split_text_by_tokens(text: str, max_tokens: int = 6500) -> list[str]:
    """按段落拆分长文档，尽量保留论文语义结构。"""
    if not text.strip():
        return []

    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for para in paragraphs:
        para_tokens = estimate_tokens(para)

        if para_tokens > max_tokens:
            if current:
                chunks.append("\n".join(current))
                current = []
                current_tokens = 0

            # 极长段落兜底：按字符粗切
            approx_chars = max(1200, max_tokens * 2)
            for start in range(0, len(para), approx_chars):
                chunks.append(para[start : start + approx_chars])
            continue

        if current and current_tokens + para_tokens > max_tokens:
            chunks.append("\n".join(current))
            current = [para]
            current_tokens = para_tokens
        else:
            current.append(para)
            current_tokens += para_tokens

    if current:
        chunks.append("\n".join(current))

    return chunks
