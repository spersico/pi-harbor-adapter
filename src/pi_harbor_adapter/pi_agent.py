import shlex
from typing import Any, override

from harbor.agents.installed.base import (
    BaseInstalledAgent,
    CliFlag,
    with_prompt_template,
)
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext


class PiAgent(BaseInstalledAgent):
    """Harbor adapter for @earendil-works/pi-coding-agent."""

    DEFAULT_PI_PACKAGE = "@earendil-works/pi-coding-agent"
    DEFAULT_NODE_VERSION = "24"
    DEFAULT_PI_CODING_AGENT_DIR = "/root/.pi/agent"

    CLI_FLAGS = [
        CliFlag(
            "thinking",
            cli="--thinking",
            type="enum",
            choices=["off", "minimal", "low", "medium", "high", "xhigh"],
        ),
    ]

    def __init__(
        self,
        *args: Any,
        version: str | None = None,
        node_version: str | None = None,
        extra_env: dict[str, str] | None = None,
        **kwargs: Any,
    ):
        """Configure the npm package, Node version, and Pi agent directory."""
        self.node_version = node_version or self.DEFAULT_NODE_VERSION
        self.pi_package_spec = f"{self.DEFAULT_PI_PACKAGE}@{version or 'latest'}"
        merged_extra_env = dict(extra_env or {})
        merged_extra_env.setdefault("PI_CODING_AGENT_DIR", self.DEFAULT_PI_CODING_AGENT_DIR)
        super().__init__(
            *args,
            version=version,
            extra_env=merged_extra_env,
            **kwargs,
        )

    @staticmethod
    @override
    def name() -> str:
        """Name shown by Harbor in result summaries."""
        return "pi"

    async def _install_system_dependencies(self, environment: BaseEnvironment) -> None:
        """Install OS packages needed by nvm, Node, and Pi."""
        await self.exec_as_root(
            environment,
            command="apt-get update && apt-get install -y curl libatomic1",
            env={"DEBIAN_FRONTEND": "noninteractive"},
        )

    def _install_node_command(self, node_version: str) -> str:
        """Return the shell snippet that installs the requested Node version."""
        return (
            "curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.5/install.sh | bash && "
            'export NVM_DIR="$HOME/.nvm" && '
            '\\. "$NVM_DIR/nvm.sh" || true && '
            "command -v nvm &>/dev/null || { echo 'Error: NVM failed to load' >&2; exit 1; } && "
            f"nvm install {shlex.quote(node_version)} && "
        )

    @override
    def get_version_command(self) -> str | None:
        """Let Harbor detect the installed Pi version after setup."""
        return ". ~/.nvm/nvm.sh; pi --version"

    @override
    async def install(self, environment: BaseEnvironment) -> None:
        """Install Node and the configured Pi npm package in the task container."""
        await self._install_system_dependencies(environment)

        await self.exec_as_agent(
            environment,
            command=(
                "set -euo pipefail; "
                f"{self._install_node_command(self.node_version)}"
                f"npm install -g {self.pi_package_spec} && "
                "pi --version"
            ),
        )

    @with_prompt_template
    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        """Run Pi once against the Terminal-Bench task instruction."""
        if not self.model_name or "/" not in self.model_name:
            raise ValueError("Model name must be in the format provider/model_name")

        provider, model = self.model_name.split("/", 1)

        cli_flags = self.build_cli_flags()
        if cli_flags:
            cli_flags += " "

        await self.exec_as_agent(
            environment,
            command=(
                "set -euo pipefail; mkdir -p /logs/agent; . ~/.nvm/nvm.sh; "
                "pi --print --mode json --no-session "
                f"--provider {shlex.quote(provider)} --model {shlex.quote(model)} "
                f"{cli_flags}"
                f"{shlex.quote(instruction)} "
                f"2>&1 </dev/null | grep -v '\"type\":\"message_update\"' | "
                "stdbuf -oL tee /logs/agent/pi.jsonl; "
                "if grep -Eq '\"stopReason\"[[:space:]]*:[[:space:]]*\"error\"|\"errorMessage\"[[:space:]]*:' "
                "/logs/agent/pi.jsonl; then "
                "echo 'Pi reported a provider/agent error; see /logs/agent/pi.jsonl' >&2; "
                "exit 1; "
                "fi"
            ),
        )
