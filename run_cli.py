from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from thesis_defense_mvp.io_utils import read_file
from thesis_defense_mvp.workflow import ThesisDefenseWorkflow


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="硕士论文答辩智能助理 Agent MVP")
    parser.add_argument("--thesis", required=True, help="论文文件路径，支持 docx / pdf / txt / md")
    parser.add_argument("--ppt", default="", help="PPT 文字稿文件路径，可选")
    parser.add_argument("--school", default="", help="学校要求文件路径，可选")
    parser.add_argument("--out", default="outputs/答辩智能助理报告.md", help="输出 Markdown 报告路径")
    parser.add_argument("--model", default="", help="模型名称；默认读取 .env 的 OPENAI_MODEL")
    parser.add_argument("--chunk_tokens", type=int, default=0, help="每个论文片段最大 Token 数")
    parser.add_argument("--mock", action="store_true", help="无 API Key 演示模式，不调用模型")
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()

    model = args.model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    chunk_tokens = args.chunk_tokens or int(os.getenv("CHUNK_TOKENS", "6500"))

    thesis_text = read_file(args.thesis)
    ppt_text = read_file(args.ppt) if args.ppt else ""
    school_text = read_file(args.school) if args.school else ""

    workflow = ThesisDefenseWorkflow(
        model=model,
        cache_dir=".agent_cache",
        mock=args.mock,
    )

    result = workflow.run(
        thesis_text=thesis_text,
        ppt_text=ppt_text,
        school_text=school_text,
        chunk_tokens=chunk_tokens,
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(result["final_report"], encoding="utf-8")

    usage_path = out_path.with_suffix(".token_usage.json")
    usage_path.write_text(
        json.dumps(result["usage_records"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    parts_dir = out_path.parent / "parts"
    parts_dir.mkdir(parents=True, exist_ok=True)
    (parts_dir / "01_论文核心逻辑.md").write_text(result["thesis_map"], encoding="utf-8")
    (parts_dir / "02_金融审稿意见.md").write_text(result["reviewer_report"], encoding="utf-8")
    (parts_dir / "03_答辩问答.md").write_text(result["defense_qas"], encoding="utf-8")
    (parts_dir / "04_PPT优化建议.md").write_text(result["ppt_plan"], encoding="utf-8")
    (parts_dir / "00_论文分块摘要.md").write_text(result["chunk_summaries"], encoding="utf-8")

    print("\n运行完成。")
    print(f"主报告：{out_path.resolve()}")
    print(f"Token 记录：{usage_path.resolve()}")
    print(f"中间结果：{parts_dir.resolve()}")


if __name__ == "__main__":
    main()
