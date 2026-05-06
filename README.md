# 论文答辩智能助理 Agent MVP

这是一个可本地运行的轻量级多 Agent 项目，用于把论文、PPT 文字稿和学校要求转化为：

- 论文核心逻辑梳理
- 金融/经管导师视角审稿意见
- 高频答辩问题与推荐回答
- 7 分钟答辩 PPT 汇报策略
- Token 使用记录与 Token Plan 说明

项目提供两种运行方式：

1. **命令行版**：适合稳定批处理和保存报告。
2. **Streamlit 网页版**：适合演示和上传文件操作。

---

## 1. 项目结构

```text
thesis_defense_mvp/
├─ README.md
├─ requirements.txt
├─ .env.example
├─ run_cli.py
├─ app_streamlit.py
├─ thesis_defense_mvp/
│  ├─ __init__.py
│  ├─ agents.py
│  ├─ io_utils.py
│  ├─ token_utils.py
│  └─ workflow.py
├─ examples/
│  ├─ sample_thesis.txt
│  ├─ sample_ppt.txt
│  └─ school_requirements.txt
└─ scripts/
   ├─ run_cli_demo.bat
   ├─ run_streamlit.bat
   ├─ run_cli_demo.sh
   └─ run_streamlit.sh
```

---

## 2. 安装环境

建议使用 Python 3.10 或以上版本。

```bash
cd thesis_defense_mvp
python -m venv .venv
```

Windows：

```bash
.venv\Scripts\activate
pip install -r requirements.txt
```

Mac / Linux：

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 3. 配置 API Key

复制 `.env.example` 为 `.env`：

```bash
cp .env.example .env
```

Windows 可以直接复制文件，然后在 `.env` 中填写：

```env
OPENAI_API_KEY=sk-你的key
OPENAI_MODEL=gpt-4.1-mini
CHUNK_TOKENS=6500
```

本项目使用 OpenAI Python SDK 调用 Responses API；代码也保留了 Chat Completions 回退逻辑，便于兼容不同 SDK / 模型环境。OpenAI 官方文档中列出了 Responses API、Python SDK 和模型相关入口。  

---

## 4. 快速跑通：Mock 演示模式

没有 API Key 时，可以先用 mock 模式验证项目能否运行：

```bash
python run_cli.py --thesis examples/sample_thesis.txt --ppt examples/sample_ppt.txt --school examples/school_requirements.txt --mock
```

运行后会生成：

```text
outputs/答辩智能助理报告.md
outputs/答辩智能助理报告.token_usage.json
outputs/parts/
```

---

## 5. 正式运行：命令行版

```bash
python run_cli.py \
  --thesis 你的论文.docx \
  --ppt 你的PPT文字稿.txt \
  --school 学校要求.txt \
  --out outputs/答辩智能助理报告.md
```

只输入论文也可以：

```bash
python run_cli.py --thesis 你的论文.docx
```

支持文件类型：

- `.docx`
- `.pdf`
- `.txt`
- `.md`

注意：扫描件 PDF 不能稳定提取文本，建议先转成可复制文字的 PDF 或 Word。

---

## 6. 正式运行：网页 MVP

```bash
streamlit run app_streamlit.py
```

打开浏览器后上传论文、PPT 文字稿、学校要求，点击“开始生成答辩报告”。

---

## 7. 多 Agent 逻辑

本项目包含 6 个 Agent：

1. **论文分块理解 Agent**：逐段读取长论文，提取答辩相关摘要。
2. **论文理解 Agent**：重构整篇论文的研究问题、变量、方法、结论和创新点。
3. **金融审稿 Agent**：从经济学/金融学导师视角找薄弱环节。
4. **答辩模拟 Agent**：生成高风险追问和现场回答。
5. **PPT 表达优化 Agent**：输出 7 分钟汇报结构和页面策略。
6. **综合报告 Agent**：整合为最终答辩准备报告。

---

## 8. Token Plan 设计

为了减少 Token 浪费，项目没有让每个 Agent 都重复读取完整论文，而是采用：

```text
长论文原文
  ↓
按 Token 分块
  ↓
论文分块理解 Agent 生成结构化摘要
  ↓
后续 Agent 复用摘要与核心逻辑
  ↓
输出答辩报告、问答手册、PPT 策略、Token 记录
```

同时启用了 `.agent_cache` 本地缓存：

- 相同论文片段、相同 Agent、相同模型输入不会重复调用 API。
- 多次调试 PPT 或学校要求时，可以复用之前的论文理解结果。

---

## 9. 可以写进申报表的成果描述

我构建了一个面向硕士论文答辩准备的 AI 多 Agent 工作流，用于解决论文内容复杂、实证结果多、答辩提问不确定性高的问题。该流程以论文正文、实证表格、答辩 PPT 和学校要求为输入，分为论文理解 Agent、金融审稿 Agent、答辩模拟 Agent、PPT 表达优化 Agent 等多个角色协同工作。系统首先对长论文进行分块理解和结构化摘要，再提取研究问题、变量构建、模型设定、核心结论和创新点，随后从金融学导师视角生成高风险提问清单，并给出可直接用于答辩现场的回答逻辑。

在 Token 使用方面，该流程采用“先压缩、再复用”的策略，避免每个 Agent 重复读取完整论文；同时通过本地缓存机制减少重复运行带来的 Token 浪费，使长文档处理更加稳定、经济和可控。

---

## 10. 常见问题

### Q1：运行时提示没有 OPENAI_API_KEY 怎么办？

先复制 `.env.example` 为 `.env`，填入你的 API Key。或者使用 `--mock` 演示模式。

### Q2：我的模型不可用怎么办？

修改 `.env` 中的：

```env
OPENAI_MODEL=gpt-4.1-mini
```

换成你账号可用的模型。

### Q3：论文太长怎么办？

把 `.env` 中的 `CHUNK_TOKENS` 调小，例如：

```env
CHUNK_TOKENS=4500
```

### Q4：输出内容太长怎么办？

可以在 `thesis_defense_mvp/agents.py` 中降低对应 Agent 的 `max_output_tokens`。

