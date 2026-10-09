# Training & Competency Assessment Agent
A Coze agent that generates assessment questions, scores trainee answers, and
produces personalized study plans.

## Architecture

- Mode: single agent (LLM)
- Model: Doubao 2.0 Pro
- Knowledge: 5 knowledge bases, 50 documents
- Workflows: `generate_questions`, `score_answer`, `analyze_gaps`
- Database: `trainee_records`, `trainee_profiles`

## Setup

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







