# Contributing

Thanks for improving Context Genome. This project is still small and experimental, so the best contributions are focused, reproducible, and easy to inspect.

## Local Workflow

```bash
cp .env.example .env
./run.sh
make doctor
make check
```

Use `rule` or `prompt_preview` mode for quick non-LLM smoke tests. Use `LLM JSON` mode only when the change specifically touches model behavior, prompt layout, report generation, cache behavior, or runtime credentials.

## Pull Request Checklist

- Keep changes scoped to one behavioral or documentation concern.
- Add or update tests when changing parser, world, runtime, export, report, or token-budget behavior.
- Run `make check` before committing.
- Do not commit `runs/`, `.env`, `__pycache__/`, screenshots with private content, or local machine paths.
- If updating README screenshots, use clean seeded runs and avoid exposing API keys, local paths, browser tabs, or personal data.

## Design Principles

- Context is the evolving unit. Preserve the distinction between base model capability and organism context genome.
- First-person organism context should remain model self-state; world observations should remain external input.
- Cost controls matter. Keep token budget, call caps, cache signals, and small-model defaults visible.
- Researcher interventions should be explicit and reversible where possible.
