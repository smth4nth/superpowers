import brainstorm_session
import codex_brainstorm_session
import codex_session
import session


UNKNOWN_AGENT_EXIT = -3


def agent_name(item, config):
    return item.get("agent") or config.get("default_agent") or "claude"


def _agent_config(name, config):
    agents = config.get("agents", {})
    return agents.get(name, {})


def _claude_cmd(config):
    return _agent_config("claude", config).get("cmd") or config.get("claude_cmd", "claude")


def _codex_cmd(config):
    return _agent_config("codex", config).get("cmd", "codex")


def run_work_item(item, config):
    name = agent_name(item, config)
    if name == "claude":
        return session.run(item, claude_cmd=_claude_cmd(config))
    if name == "codex":
        return codex_session.run(item, codex_cmd=_codex_cmd(config))
    return UNKNOWN_AGENT_EXIT


def run_brainstorm_item(item, config):
    name = agent_name(item, config)
    if name == "claude":
        return brainstorm_session.run(item, claude_cmd=_claude_cmd(config))
    if name == "codex":
        return codex_brainstorm_session.run(item, codex_cmd=_codex_cmd(config))
    return None
