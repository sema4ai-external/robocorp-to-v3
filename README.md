# Robocorp to Sema4.ai v3

Move your Robocorp Control Room processes to Sema4.ai v3 without rewriting your robots. Your task packages run as they are on v3 workers, inside v3 workflows.

This repository holds what does the work: the **Robocorp Relink** skill and three **Verified Logic** packages. You install them once into your v3 workspace, with the help of the AI tool you already use. After that, anyone in the workspace can ask an agent to relink their processes.

## Before you start

1. **Use an AI tool that can connect to MCP servers and run commands on your machine**, such as Claude Code, Cursor, VS Code with Copilot, or Codex. The install packs and uploads files with `tar` and `curl`, so a chat-only client without a shell won't do.
2. **Connect your v3 workspace to it first.** Add the Sema4.ai Workspace MCP connector, `https://<your-v3-host>/api/v1/workspace/mcp`, and sign in when your tool asks.
   - Claude Code: `claude mcp add --transport http sema4 https://<your-v3-host>/api/v1/workspace/mcp`
   - Other tools: add it as a remote (HTTP) MCP server in their MCP settings.

   Check that the connection works: ask your tool *"Which Sema4 workspaces and projects can you see?"*
3. **Be a workspace admin in v3.** The skill and Verified Logic are installed for the whole workspace (org scope).
4. **Clone this repository**, or download it, and open the folder in your AI tool.

## Install: the prompt

In your AI tool, with this folder open and the v3 connector connected, paste:

```text
Install the Robocorp relink kit from this repository into my Sema4.ai v3 workspace.
Use the Sema4 Workspace MCP connector and follow INSTALL.md step by step.
Ask me before anything that needs my decision, and finish with a short report of what was installed.
```

The tool creates a small project named **Robocorp Relink Toolkit**, which only hosts the drafts. It then publishes the three Verified Logic packages and the skill to your workspace and runs a quick check that needs no Control Room access. It takes a few minutes. If your workspace requires review before Verified Logic or skills go live, the tool tells you what to approve and where.

## Relink: the prompt

Once it's installed, open any v3 project chat, or keep using your AI tool with the v3 connector, and say:

```text
Relink my Robocorp Control Room processes to v3.
```

The agent starts with a 10-step roadmap and asks for your Control Room workspace URL. It then guides you through the rest:

1. **Project and connection:** a project with network access to Control Room only. You paste a **read-only** Control Room API key into the project settings, never into the chat.
2. **Inventory:** it reads your processes, task packages, workers, and the names of your Vault secrets and assets. It never reads secret values.
3. **Pick processes:** you choose which processes to bring over.
4. **Code peek:** it reads each package's code to find the secrets, assets, files and software it needs. It never runs the code.
5. **Workers:** you choose which v3 worker or worker group runs each step.
6. **Dependencies:** it adds the packages and the assets the code uses, and creates the Vault secrets. You type the secret values on the v3 secret page.
7. **Workflows and triggers:** it builds one v3 workflow per process. All schedules and other triggers are created **switched off**.
8. **Test runs:** it runs each workflow once and explains any failures.
9. **Cutover:** this is yours. Switch on the v3 triggers, switch off the Control Room ones, and revoke the API key.

Nothing runs on a schedule, and nothing in Control Room changes, until you do the cutover yourself.

## What's in this repository

| Path | What it is |
|---|---|
| `skills/robocorp-relink/SKILL.md` | The skill: how an agent runs a relink, step by step, and what it asks you. |
| `verified-logic/robocorp-inventory/` | Reads a Control Room workspace (GET only) into project files. Never requests secret values. |
| `verified-logic/robocorp-fetch-package/` | Downloads one task package zip from Control Room into the project. |
| `verified-logic/robocorp-code-peek/` | Reads a package zip without running it, and lists the secrets, assets, variables, work item use, UI needs and dependency risks. |
| `INSTALL.md` | The install steps your AI tool follows. |

## Security in short

- Your Control Room key lives only in a v3 project network credential. Code sees an opaque marker, and the v3 network gateway adds the real key to requests for your Control Room workspace path only (GET only).
- Vault secret values are never read from Control Room and never pass through the chat. You type them on the v3 secret page.
- Package code is read, never run, outside your own workers.
- Workers, process choices and cutover are always your decisions.
