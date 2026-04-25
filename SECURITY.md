# Security And Privacy

Context Genome is a local research sandbox that can call OpenAI-compatible LLM endpoints. Treat API keys, exported runs, prompts, and generated reports as potentially sensitive.

## API Keys

- Prefer `.env` or the in-browser `Tune -> LLM Runtime` form for local keys.
- `.env` is ignored by git, and `.env.example` contains placeholders only.
- Runtime keys are stored only in server memory. The browser does not receive the key back after saving.
- `/api/health`, `/api/presets`, and runtime status responses expose only whether a key is available, not the key itself.

## Data Handling

- `runs/` is ignored by git because exported worlds may contain prompts, reports, model outputs, and edited context genomes.
- Before sharing screenshots or run artifacts, check for model outputs, personal notes, local paths, credentials, or private prompt content.
- `scripts/check_repository_hygiene.py` scans tracked files for common secret patterns and local path leaks. Run `make check` before publishing.

## Reporting Issues

If you find a secret exposure, unsafe default, or privacy bug, avoid posting the sensitive value publicly. Open an issue describing the mechanism and affected file or endpoint, or contact the maintainer privately if the repository settings provide a private channel.
