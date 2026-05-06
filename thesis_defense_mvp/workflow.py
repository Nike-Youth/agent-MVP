from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Callable

from .agents import AgentSpec, build_agents
from .token_utils import estimate_tokens, split_text_by_tokens

ProgressCallback = Callable[[str], None]


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def safe_response_output_text(response: Any) -> str:
    """尽量兼容不同 openai SDK 版本的响应文本读取方式。"""
    output_text = getattr(response, "output_text", None)
    if output_text:
        return str(output_text)

    output = getattr(response, "output", None)
    if output:
        parts: list[str] = []
        for item in output:
            content = getattr(item, "content", None) or []
            for block in content:
                text = getattr(block, "text", None)
                if text:
                    parts.append(str(text))
        if parts:
            return "\n".join(parts)

    raise RuntimeError("无法从模型响应中读取文本。请检查 openai SDK 版本。")


def safe_usage(response: Any) -> dict[str, int]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    input_tokens = getattr(usage, "input_tokens", None)
    output_tokens = getattr(usage, "output_tokens", None)
    total_tokens = getattr(usage, "total_tokens", None)

    # Chat Completions 兼容
    if input_tokens is None:
        input_tokens = getattr(usage, "prompt_tokens", 0) or 0
    if output_tokens is None:
        output_tokens = getattr(usage, "completion_tokens", 0) or 0
    if total_tokens is None:
        total_tokens = int(input_tokens or 0) + int(output_tokens or 0)

    return {
        "input_tokens": int(input_tokens or 0),
        "output_tokens": int(output_tokens or 0),
        "total_tokens": int(total_tokens or 0),
    }


class ThesisDefenseWorkflow:
    """论文答辩智能助理 MVP 的核心工作流。"""

    def __init__(
        self,
        model: str = "gpt-4.1-mini",
        cache_dir: str | Path = ".agent_cache",
        mock: bool = False,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        self.model = model
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.mock = mock
        self.progress_callback = progress_callback or print
        self.usage_records: list[dict[str, Any]] = []
        self.client = None

        if not self.mock:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise ImportError("请先安装 openai：pip install openai") from exc
            self.client = OpenAI()

    def log(self, message: str) -> None:
        self.progress_callback(message)

    def call_agent(self, agent: AgentSpec, user_input: str, cache_enabled: bool = True) -> str:
        cache_key = sha256_text(
            json.dumps(
                {
                    "model": self.model,
                    "mock": self.mock,
                    "agent": agent.name,
                    "instructions": agent.instructions,
                    "input": user_input,
                },
                ensure_ascii=False,
            )
        )
        cache_path = self.cache_dir / f"{cache_key}.json"

        if cache_enabled and cache_path.exists():
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            self.log(f"命中缓存：{agent.name}")
            return data["output"]

        self.log(f"正在运行：{agent.name}")
        start = time.time()

        if self.mock:
            output = self.mock_agent_output(agent, user_input)
            usage = {
                "input_tokens": estimate_tokens(user_input),
                "output_tokens": estimate_tokens(output),
                "total_tokens": estimate_tokens(user_input) + estimate_tokens(output),
            }
        else:
            if not os.environ.get("OPENAI_API_KEY"):
                raise EnvironmentError(
                    "未检测到 OPENAI_API_KEY。请设置环境变量，或使用 --mock 先跑通流程。"
                )
            output, usage = self.call_openai(agent, user_input)

        elapsed = round(time.time() - start, 2)
        record = {
            "agent": agent.name,
            "input_tokens": usage["input_tokens"],
            "output_tokens": usage["output_tokens"],
            "total_tokens": usage["total_tokens"],
            "elapsed_seconds": elapsed,
        }
        self.usage_records.append(record)

        cache_path.write_text(
            json.dumps({"agent": agent.name, "output": output, "usage": record}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        self.log(f"完成：{agent.name} | Token: {record['total_tokens']} | 耗时: {elapsed}s")
        return output

    def call_openai(self, agent: AgentSpec, user_input: str) -> tuple[str, dict[str, int]]:
        """优先使用 Responses API，失败时回退到 Chat Completions。"""
        assert self.client is not None

        try:
            response = self.client.responses.create(
                model=self.model,
                instructions=agent.instructions,
                input=user_input,
                max_output_tokens=agent.max_output_tokens,
            )
            return safe_response_output_text(response), safe_usage(response)
        except Exception as response_error:  # noqa: BLE001
            self.log(f"Responses API 调用失败，尝试回退 Chat Completions：{response_error}")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": agent.instructions},
                    {"role": "user", "content": user_input},
                ],
                max_tokens=agent.max_output_tokens,
            )
            output = response.choices[0].message.content or ""
            return output, safe_usage(response)

    def mock_agent_output(self, agent: AgentSpec, user_input: str) -> str:
        """无 API Key 时用于演示流程的假输出。"""
        preview = user_input[:500].replace("\n", " ")
        return f"""
# {agent.name} 演示输出

这是 mock 模式下生成的占位结果，用于验证 MVP 的安装、文件读取、分块、缓存、报告输出流程是否正常。

## 已接收内容预览
{preview}...

## 下一步
关闭 mock 模式并配置 OPENAI_API_KEY 后，本 Agent 会根据你的论文材料生成正式内容。
""".strip()

    def run(
        self,
        thesis_text: str,
        ppt_text: str = "",
        school_text: str = "",
        chunk_tokens: int = 6500,
    ) -> dict[str, Any]:
        agents = build_agents()

        thesis_tokens = estimate_tokens(thesis_text)
        chunks = split_text_by_tokens(thesis_text, max_tokens=chunk_tokens)
        if not chunks:
            raise ValueError("论文文本为空，无法运行。")

        self.log(f"论文文本估算 Token：{thesis_tokens}")
        self.log(f"论文共拆分为 {len(chunks)} 个片段。")

        chunk_summaries: list[str] = []
        for idx, chunk in enumerate(chunks, start=1):
            prompt = f"""
这是论文的第 {idx}/{len(chunks)} 个片段。

请阅读并提取答辩相关信息。

【论文片段开始】
{chunk}
【论文片段结束】
""".strip()
            summary = self.call_agent(agents["chunk_reader"], prompt)
            chunk_summaries.append(f"## 片段 {idx}\n\n{summary}")

        all_chunk_summaries = "\n\n".join(chunk_summaries)

        thesis_map = self.call_agent(
            agents["understanding"],
            f"""
以下是论文各片段的结构化摘要，请你重构整篇论文的核心逻辑。

【论文分块摘要】
{all_chunk_summaries}
""".strip(),
        )

        reviewer_report = self.call_agent(
            agents["reviewer"],
            f"""
请从经济学、金融学硕士论文答辩评委视角审查这篇论文。

【论文核心逻辑】
{thesis_map}

【论文分块摘要】
{all_chunk_summaries}
""".strip(),
        )

        defense_qas = self.call_agent(
            agents["defense"],
            f"""
请基于以下内容生成答辩模拟问题和推荐回答。

【论文核心逻辑】
{thesis_map}

【金融审稿意见】
{reviewer_report}
""".strip(),
        )

        ppt_plan = self.call_agent(
            agents["ppt"],
            f"""
请为该论文设计答辩 PPT 汇报策略。

【论文核心逻辑】
{thesis_map}

【金融审稿意见】
{reviewer_report}

【已有 PPT 文字稿，如有】
{ppt_text if ppt_text else "未提供"}

【学校或老师要求，如有】
{school_text if school_text else "未提供"}
""".strip(),
        )

        final_report = self.call_agent(
            agents["integrator"],
            f"""
请整合以下四部分内容，生成最终答辩准备报告。

【论文理解 Agent 输出】
{thesis_map}

【金融审稿 Agent 输出】
{reviewer_report}

【答辩模拟 Agent 输出】
{defense_qas}

【PPT 表达优化 Agent 输出】
{ppt_plan}

【学校要求】
{school_text if school_text else "未提供"}
""".strip(),
        )

        token_summary = self.build_token_summary(thesis_tokens=thesis_tokens, chunk_count=len(chunks))
        full_report = final_report + "\n\n---\n\n" + token_summary

        return {
            "final_report": full_report,
            "thesis_map": thesis_map,
            "reviewer_report": reviewer_report,
            "defense_qas": defense_qas,
            "ppt_plan": ppt_plan,
            "chunk_summaries": all_chunk_summaries,
            "usage_records": self.usage_records,
            "chunk_count": len(chunks),
            "thesis_tokens": thesis_tokens,
        }

    def build_token_summary(self, thesis_tokens: int, chunk_count: int) -> str:
        total_input = sum(x["input_tokens"] for x in self.usage_records)
        total_output = sum(x["output_tokens"] for x in self.usage_records)
        total = sum(x["total_tokens"] for x in self.usage_records)

        lines = [
            "| Agent | 输入 Token | 输出 Token | 总 Token | 耗时 秒 |",
            "|---|---:|---:|---:|---:|",
        ]
        for record in self.usage_records:
            lines.append(
                f"| {record['agent']} | {record['input_tokens']} | "
                f"{record['output_tokens']} | {record['total_tokens']} | {record['elapsed_seconds']} |"
            )
        table_md = "\n".join(lines)

        return f"""
# Token 使用与效率说明

## 1. Token 使用统计

论文原文估算 Token：{thesis_tokens}  
论文分块数量：{chunk_count}

{table_md}

合计输入 Token：{total_input}  
合计输出 Token：{total_output}  
合计总 Token：{total}

## 2. Token Plan 说明

本工作流没有将整篇论文一次性输入模型，而是采用“论文分块理解 → 结构化摘要 → 多 Agent 复用摘要”的方式。

具体策略包括：

1. 长论文先拆分为 {chunk_count} 个片段，避免一次性输入超长上下文。
2. 每个片段先由“论文分块理解 Agent”压缩成答辩相关摘要。
3. 后续 Agent 不再重复读取完整论文，而是复用结构化摘要和论文核心逻辑。
4. 相同输入启用本地缓存 `.agent_cache`，重复运行时不会再次消耗 Token。
5. PPT 优化、答辩模拟、金融审稿分别调用不同 Agent，避免一个 Prompt 同时承担过多任务导致输出混乱。

## 3. 可写入成果描述的版本

我构建了一个面向硕士论文答辩准备的 AI 多 Agent 工作流，用于解决论文内容复杂、实证结果多、答辩提问不确定性高的问题。该流程将论文正文、实证表格、答辩 PPT 和学校要求作为输入，分为论文理解 Agent、金融审稿 Agent、答辩模拟 Agent 和 PPT 表达优化 Agent 等多个角色协同工作。系统首先对长论文进行分块理解和结构化摘要，再提取研究问题、变量构建、模型设定、核心结论和创新点，随后从金融学导师视角生成高风险提问清单，并给出可直接用于答辩现场的回答逻辑。

在 Token 使用方面，该流程采用“先压缩、再复用”的策略，避免每个 Agent 重复读取完整论文；同时通过本地缓存机制减少重复运行带来的 Token 浪费，使长文档处理更加稳定、经济和可控。
""".strip()
