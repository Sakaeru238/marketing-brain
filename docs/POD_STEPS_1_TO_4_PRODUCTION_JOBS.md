# POD Steps [1]-[4] — Production Jobs

This patch implements production job files directly, with no sample/test data.

## Implemented flow

```text
Brand Context Source of Truth
+ Brand Learning
+ POD Campaign Intake
+ Product Catalog
        ↓
[1] Alysha — creative-strategy-engine
        ↓
POD Strategy Output
        ↓
[2] julianoczkowski/designer-skills
        ↓
POD Design Brief
        ↓
[3] DeepEval — Brief Strategy Evaluation
        ↓
PASS / FAIL
        ├── FAIL → run step [2] again with revision feedback
        └── PASS
              ↓
[4] Open Design / Generative Media Translation Layer
        ↓
ChatGPT Image Prompt
+ ComfyUI JSON / Render Request
```

## Jobs

### Individual jobs
```bash
python -m core.jobs.run_pod_strategy_job ...
python -m core.jobs.run_pod_design_brief_job ...
python -m core.jobs.run_pod_brief_eval_job ...
python -m core.jobs.run_pod_open_design_translation_job ...
```

### Full production pipeline [1]-[4]
```bash
python -m core.jobs.run_pod_steps_1_to_4_job ...
```

## Required install

```bash
pip install -r requirements-pod-strategy-brief.txt
```

## Environment

```bash
export ANTHROPIC_API_KEY="..."
```

Telegram:
- First tries existing project notifier:
  `core.notifications.telegram_notifier.TelegramNotifier`
- Fallback envs:
```bash
export TELEGRAM_BOT_TOKEN="..."
export TELEGRAM_CHAT_ID="..."
```

## Token and cost report
Every major job writes:
- usage JSON
- run report JSON

Folders:
```text
data/brands/{brand_id}/pod/campaigns/{campaign_id}/usage/
data/brands/{brand_id}/pod/campaigns/{campaign_id}/reports/
```

## Telegram notification
Each major step sends:
- start
- completion with token/cost summary
- failure

## Output artifacts

```text
data/brands/{brand_id}/pod/campaigns/{campaign_id}/
  01_pod_strategy/
  02_pod_design_brief/
  03_pod_brief_eval/
  04_open_design_translation/
  reports/
  usage/
```


## Repo structure note

The repository currently keeps `core/services/` flat.
This patch therefore adds POD services directly under:

```text
core/services/
  pod_pipeline_utils.py
  pod_llm_client.py
  pod_prompts.py
  pod_strategy_service.py
  pod_design_brief_service.py
  pod_brief_eval_service.py
  pod_open_design_translation_service.py
```

No `core/services/pod/` subfolder is used in this final patch.
