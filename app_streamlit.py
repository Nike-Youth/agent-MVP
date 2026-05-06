from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from thesis_defense_mvp.io_utils import read_file, save_uploaded_file
from thesis_defense_mvp.workflow import ThesisDefenseWorkflow

load_dotenv()

st.set_page_config(page_title="论文答辩智能助理 MVP", page_icon="🎓", layout="wide")
st.title("🎓 论文答辩智能助理 Agent MVP")
st.caption("上传论文、PPT 文字稿和学校要求，自动生成答辩准备报告、追问清单和 PPT 汇报建议。")

with st.sidebar:
    st.header("运行设置")
    model = st.text_input("模型名称", value=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))
    chunk_tokens = st.number_input("论文分块 Token 上限", min_value=1500, max_value=20000, value=int(os.getenv("CHUNK_TOKENS", "6500")), step=500)
    mock = st.checkbox("Mock 演示模式：不调用 API", value=not bool(os.getenv("OPENAI_API_KEY")))
    st.info("首次正式运行请复制 .env.example 为 .env，并填写 OPENAI_API_KEY。")

col1, col2, col3 = st.columns(3)
with col1:
    thesis_file = st.file_uploader("上传论文文件（必填）", type=["docx", "pdf", "txt", "md"])
with col2:
    ppt_file = st.file_uploader("上传 PPT 文字稿（可选）", type=["docx", "pdf", "txt", "md"])
with col3:
    school_file = st.file_uploader("上传学校/老师要求（可选）", type=["docx", "pdf", "txt", "md"])

run_button = st.button("开始生成答辩报告", type="primary", disabled=thesis_file is None)

if run_button:
    upload_dir = Path("uploads") / datetime.now().strftime("%Y%m%d_%H%M%S")
    upload_dir.mkdir(parents=True, exist_ok=True)

    thesis_path = save_uploaded_file(thesis_file, upload_dir)
    ppt_path = save_uploaded_file(ppt_file, upload_dir) if ppt_file else None
    school_path = save_uploaded_file(school_file, upload_dir) if school_file else None

    progress_area = st.empty()
    log_lines: list[str] = []

    def progress_callback(message: str) -> None:
        log_lines.append(message)
        progress_area.code("\n".join(log_lines[-20:]), language="text")

    try:
        thesis_text = read_file(thesis_path)
        ppt_text = read_file(ppt_path) if ppt_path else ""
        school_text = read_file(school_path) if school_path else ""

        workflow = ThesisDefenseWorkflow(
            model=model,
            cache_dir=".agent_cache",
            mock=mock,
            progress_callback=progress_callback,
        )

        with st.spinner("Agent 正在处理，请不要关闭页面..."):
            result = workflow.run(
                thesis_text=thesis_text,
                ppt_text=ppt_text,
                school_text=school_text,
                chunk_tokens=int(chunk_tokens),
            )

        st.success("生成完成")
        st.subheader("最终报告预览")
        st.markdown(result["final_report"])

        output_dir = Path("outputs")
        output_dir.mkdir(exist_ok=True)
        report_path = output_dir / f"答辩智能助理报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        report_path.write_text(result["final_report"], encoding="utf-8")
        usage_path = report_path.with_suffix(".token_usage.json")
        usage_path.write_text(json.dumps(result["usage_records"], ensure_ascii=False, indent=2), encoding="utf-8")

        st.download_button(
            "下载 Markdown 报告",
            data=result["final_report"].encode("utf-8"),
            file_name="答辩智能助理报告.md",
            mime="text/markdown",
        )
        st.download_button(
            "下载 Token 记录 JSON",
            data=json.dumps(result["usage_records"], ensure_ascii=False, indent=2).encode("utf-8"),
            file_name="token_usage.json",
            mime="application/json",
        )

    except Exception as exc:  # noqa: BLE001
        st.error(f"运行失败：{exc}")
        st.exception(exc)
