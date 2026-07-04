# Pi Terminal-Bench adapter

Harbor adapter for running [Pi](https://www.npmjs.com/package/@earendil-works/pi-coding-agent) against Terminal-Bench tasks.

The adapter is as simple as possible:

- installs node via nvm inside the task container (default: 24)
- installs Pi via npm inside the task container (default: latest)
- passes the model and thinking level to Pi via environment variables
- runs Pi in non-interactive mode with the task instruction and captures the JSON event stream to a file for later analysis.

On top of that, I documented here, how to mount your local Pi agent resources into the task container using Harbor mounts, so you can use your local skills, extensions, and settings, and test your local Pi agent resources against Terminal-Bench tasks.

## Installation

You'll need uv and Harbor installed. See [Harbor installation](https://www.harborframework.com/docs/install) for details.

Clone the repository and sync the project environment:

```bash
git clone https://github.com/<owner>/pi-tbench-adapter.git
cd pi-tbench-adapter
uv sync
```

Then run tests, like the smoke tests below, with either option:

- From the repository root: use the commands as written with `uv run harbor ...`.
- From anywhere else: set `ADAPTER_DIR` to the repository path and replace `uv run harbor ...` with `uv run --project "$ADAPTER_DIR" harbor ...`.

For example:

```bash
ADAPTER_DIR=/path/to/pi-tbench-adapter
uv run --project "$ADAPTER_DIR" harbor --version
```

## Authentication and local agent resources

You can use your own Pi's `auth.json` or the typical provider-specific environment variables (e.g., `OPENAI_API_KEY`, `OPENROUTER_API_KEY`) to authenticate Pi inside the task container.

If you use env variables, and don't care about testing your local Pi agent resources, you can skip mounting `auth.json` and the local agent folder.

The adapter sets `PI_CODING_AGENT_DIR=/root/.pi/agent` by default, matching Pi's standard user agent directory (`~/.pi/agent`) inside the task container. To use a different container path, set `PI_CODING_AGENT_DIR` and pass it with Harbor `--ae`.

### Flow 1: Clean Pi with auth.json mount

If you already have a Pi auth file, mount it read-only into the container at the adapter's default auth path:

```bash
PI_AUTH_PATH="${PI_AUTH_PATH:-$HOME/.pi/agent/auth.json}"
PI_CODING_AGENT_DIR="${PI_CODING_AGENT_DIR:-/root/.pi/agent}"
AUTH_MOUNT="[{\"type\":\"bind\",\"source\":\"$PI_AUTH_PATH\",\"target\":\"$PI_CODING_AGENT_DIR/auth.json\",\"read_only\":true}]"
```

### Flow 2: Clean Pi install with full local agent folder mount

Uses a clean Pi from npm inside the task container, but mounts YOUR local Pi agent resources at `PI_CODING_AGENT_DIR`.

```bash
LOCAL_PI_AGENT_DIR="${LOCAL_PI_AGENT_DIR:-$HOME/.pi/agent}"
PI_CODING_AGENT_DIR="${PI_CODING_AGENT_DIR:-/root/.pi/agent}"
MOUNTS="[{\"type\":\"bind\",\"source\":\"$LOCAL_PI_AGENT_DIR\",\"target\":\"$PI_CODING_AGENT_DIR\",\"read_only\":false}]"
```

The local agent folder is writable because Pi may update cache, settings locks, and sessions during a run.

> Warning
>
> Mounting your local pi has a bit of risk, because the agent in the container can read AND modify your local agent resources (it needs read-write permission because pi may update cache, settings locks, and sessions during a run). Use a backup of your agent folder if you want to be completely sure your local agent resources are not modified. Or use [harbor's native skills feature](https://www.harborframework.com/docs/run-jobs/skills) instead of mounting the full agent folder mount.
>
> Personally, I accept the risk and mount my local agent folder, because my agent folder is in a repo, and I want to use my local skills, extensions, and settings, and I trust the bench tasks to not do anything malicious. This is a personal choice, and you should make your own decision.

If `settings.json` references absolute extension paths outside `$LOCAL_PI_AGENT_DIR`, mount those paths too, ideally at the same container path.
Extension dependencies must be available in the mounted extension repo or otherwise installable in the container.

## Options and environment variables

Harbor passes adapter options with `--ak key=value` and container environment variables with `--ae KEY=VALUE`.

Adapter options:

| Option         | Default | Description                                                           |
| -------------- | ------- | --------------------------------------------------------------------- |
| `thinking`     | unset   | Pi thinking level: `off`, `minimal`, `low`, `medium`, `high`, `xhigh` |
| `node_version` | `24`    | Node version passed to `nvm install` inside the container             |
| `version`      | latest  | Pi npm package version. Example: `--ak version=0.80.3`                |

Common environment variables:

| Variable              | Default           | Description                                      |
| --------------------- | ----------------- | ------------------------------------------------ |
| `PI_CODING_AGENT_DIR` | `/root/.pi/agent` | Pi agent resource directory inside the container |
| Provider API keys     | unset             | Example: `OPENROUTER_API_KEY`, `OPENAI_API_KEY`  |

Examples:

```bash
--ak thinking=medium
--ak version=0.80.3
--ae PI_CODING_AGENT_DIR="$PI_CODING_AGENT_DIR"
--ae OPENROUTER_API_KEY="$OPENROUTER_API_KEY"
```

Use the provider variable expected by Pi for the provider you choose.

## Smoke test

This setup-only run verifies system dependencies, Node installation, Pi npm installation, local agent resource mounting, auth detection, and version detection. It does not run the agent or verifier (_it's free! xD_).

```bash
LOCAL_PI_AGENT_DIR="${LOCAL_PI_AGENT_DIR:-$HOME/.pi/agent}"
PI_CODING_AGENT_DIR="${PI_CODING_AGENT_DIR:-/root/.pi/agent}"
MOUNTS="[{\"type\":\"bind\",\"source\":\"$LOCAL_PI_AGENT_DIR\",\"target\":\"$PI_CODING_AGENT_DIR\",\"read_only\":false}]"

uv run harbor run \
  -d terminal-bench/terminal-bench-2-1 \
  -a pi_tbench_adapter:PiAgent \
  -m openrouter/openai/gpt-4.1-nano \
  --ak thinking=off \
  --ae PI_CODING_AGENT_DIR="$PI_CODING_AGENT_DIR" \
  --mounts "$MOUNTS" \
  --install-only \
  -l 1 \
  -n 1 \
  --jobs-dir ./results/pi-local-agent-smoke
```

# Harbor reference

## Running suites

Remove `--install-only` to run the agent and verifier.

- `-n` is for concurrency.
- `-l` is to limit how many tasks from a dataset are selected.
- `-k` is for attempts per task. So `-l 10 -k 3 -n 2` runs 10 tasks, 2 concurrently, each with 3 attempts.
- Add `--agent-include-logs pi.jsonl` to save Pi's JSON event stream with Harbor's trial logs.

For more information, check the [Harbor documentation](https://www.harborframework.com/docs).

## Results

Results are written under the `--jobs-dir` path. Each run creates a timestamped directory containing:

- `result.json` — job summary
- `job.log` — job-level logs
- `<trial>/result.json` — trial result
- `<trial>/trial.log` — per-trial logs
- `<trial>/agent/pi.jsonl` — Pi JSON event stream, when run with `--agent-include-logs pi.jsonl`

View results with:

```bash
uv run harbor view ./results/pi-local-agent-smoke
```
