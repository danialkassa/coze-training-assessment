# 培训与能力评估智能体

这是一个 Coze 智能体，用于生成评估题目、评分学员答案，并制定个性化学习计划。

## 架构

- 模式：单智能体（LLM）
- 模型：Doubao 2.0 Pro
- 知识库：5 个知识库、50 份文档
- 工作流：`generate_questions`、`score_answer`、`analyze_gaps`
- 数据库：`trainee_records`、`trainee_profiles`

## 配置与运行

在项目根目录创建 `.env` 文件，并填入 Coze 凭据：

```text
COZE_API_TOKEN=your_token
COZE_BOT_ID=your_bot_id
COZE_API_BASE=https://api.coze.com
```

安装依赖并运行评估：

```bash
cd scripts
python -m pip install requests python-dotenv
python run_evaluation.py
```

评估脚本读取 `docs/test_cases.csv`，并将结果写入 `docs/test_results.csv`。

## 测试结果

- 测试用例：20 个
- 最近一次观察到的线上结果：12/20（60%）
- 目标：16/20（80% 以上）

当前结果低于目标。评分和能力差距分析用例依赖 Coze 数据库中存在有效的学员记录。

## 项目结构

- `scripts/run_evaluation.py`：运行线上评估测试
- `scripts/export_coze_project.py`：导出 Coze 元数据，支持 mock 模式
- `docs/test_cases.csv`：评估输入和预期关键词
- `coze-export/MOCK/`：示例工作流元数据

---

# Training & Competency Assessment Agent

A Coze agent that generates assessment questions, scores trainee answers, and
produces personalized study plans.

## Architecture

- Mode: single agent (LLM)
- Model: Doubao 2.0 Pro
- Knowledge: 5 knowledge bases, 50 documents
- Workflows: `generate_questions`, `score_answer`, `analyze_gaps`
- Database: `trainee_records`, `trainee_profiles`

## Setup and Usage

Create a `.env` file in the project root with the Coze credentials:

```text
COZE_API_TOKEN=your_token
COZE_BOT_ID=your_bot_id
COZE_API_BASE=https://api.coze.com
```

Install dependencies and run the evaluation:

```bash
cd scripts
python -m pip install requests python-dotenv
python run_evaluation.py
```

The evaluator reads `docs/test_cases.csv` and writes results to
`docs/test_results.csv`.

## Test Results

- Cases: 20
- Latest observed live run: 12/20 (60%)
- Target: 16/20 (80%+)

The current result is below target. Score and gap-analysis cases also depend on
valid trainee records in the configured Coze database.

## Project Layout

- `scripts/run_evaluation.py`: runs the live test suite
- `scripts/export_coze_project.py`: exports Coze metadata, with mock mode
- `docs/test_cases.csv`: evaluation inputs and expected keywords
- `coze-export/MOCK/`: sample exported workflow metadata







