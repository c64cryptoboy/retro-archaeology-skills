# Optional RetroDebugger MCP setup

RetroDebugger's built-in MCP server lets a compatible client inspect a running emulator without requiring a particular agent harness, private proxy, or extension.  Most tools in this archaeology-skills collection can also work offline, and live-debugging skills can use another backend that supplies equivalent evidence.  Installing a skill does not install or connect a debugger.

## 1. Choose a debugger distribution

Start with an appropriate [official prebuilt release](https://github.com/slajerek/RetroDebugger/releases) if it supplies the features you need.  Keep the downloaded package intact, follow its instructions, and record its release identity and executable SHA-256.  A rolling prerelease can change, so record the resolved version rather than only its moving tag.

Build from source only when you need unreleased functionality, a fix, a different configuration, or contributor work.  Follow [setup and first build](setup-and-first-build.md), including the dependency pins and native Windows validation.  A successful source build is not proof of a successful MCP connection.

The examples below are source-backed templates, not a claim that every published executable has passed these checks.  The source inspected for this guide was revision `20bc9c2fcad3743f2a770b0a3ebaa4d6497f389c`.  Match your binary's documentation and advertised tool schemas if they differ.

## 2. Select one mode

| Flag | Intended use |
| --- | --- |
| `--mcp-server` | Start a normal GUI application with its own stdio MCP server.  This is the simplest starting point. |
| `--mcp-headless` | Start the emulator with stdio MCP in headless mode. |
| `--mcp-live` | Start a windowless stdio bridge that connects to an already-running desktop debugger over WebSocket. |

The client's MCP connection is **stdin/stdout JSON-RPC**, not an HTTP or SSE URL.  The WebSocket connection in live mode is a separate debugger-side transport.  Let a compatible MCP client manage initialization and framing; the inspected server emits newline-delimited JSON.

For live mode, first enable **WebSockets debugger server** in the desktop application's settings.  Do not assume an ordinary desktop launch enables it.  The inspected bridge defaults are host `127.0.0.1`, port `3563`, and path `/stream`; `--host`, `--port`, and `--path` override them.  Keep the service local unless you have separately reviewed remote exposure and access controls.

## 3. Configure the executable and working directory

Use an absolute executable path, but also select the correct working directory.  Contributor builds resolve resources through the working directory: the inspected Windows project sets it to the RetroDebugger repository root.  Release-package layouts may differ; use the package's documented launch location, and do not infer that every package needs the same external resource directories.

For a Windows-native client, an illustrative contributor-build wrapper named `C:\Tools\retrodebugger-mcp.cmd` is:

```bat
@echo off
cd /d "C:\src\RetroDebugger" || exit /b 1
"C:\src\RetroDebugger\platform\Windows\bin\x64\Release\c64d.exe" --mcp-server
exit /b %errorlevel%
```

Replace both paths with your checkout and actual executable.  Executable names and output directories vary by revision and packaging.  The wrapper changes only its own working directory; it does not install, build, reset, or load media explicitly.

A client whose configuration uses `mcpServers` might accept:

```json
{
  "mcpServers": {
    "retrodebugger": {
      "type": "stdio",
      "command": "C:\\Windows\\System32\\cmd.exe",
      "args": ["/d", "/c", "C:\\Tools\\retrodebugger-mcp.cmd"]
    }
  }
}
```

Client schemas differ; adapt this to your client's documented stdio configuration.  If the client supports an explicit subprocess working directory, it can launch the executable directly with the appropriate directory instead.  A client running on another operating system needs a supported way to launch the Windows process and preserve its streams; the Windows-native example does not establish that integration.

Preserve stdin and stdout, keep stderr available for diagnostics, and do not use `start`, detach the process, or merge stderr into stdout.  Do not add banners or ordinary log output to the protocol stream.  Build-log redirection examples elsewhere in this skill are not MCP launch commands.

## 4. Verify discovery and read-only readiness

Have the client complete `initialize`, send `notifications/initialized`, and request `tools/list`.  Inspect the actual tool roster and schemas; a process, handshake, or fixed expected tool count is not a readiness test.  Startup registration can take time, and a disconnected live bridge may hide debugger-backed tools.

Use the following small, sequential sequence, checking every response for protocol and tool errors:

```text
retro_transport_diagnostics({})
retro_list_platforms({})
retro_machine_state({"platform":"c64"})
retro_cpu_status({"platform":"c64"})
retro_memory_read({"platform":"c64","address":1024,"length":16})
```

The first call is for live-bridge mode only, and only when advertised.  Continue with a platform actually returned by `retro_list_platforms`; the remaining examples use `c64`.  A nonempty platform list, a successful machine-state response, valid registers, and a successful small memory read together establish a useful initial connection.  The inspected memory-read schema uses `length`, and its data is Base64 inside the returned result envelope.

These are observations, not an atomic snapshot of a running machine.  They do not establish BASIC READY, a particular game state, disk readiness, or permission to replace the current session.  Do not automatically pause, continue, reset, load media, or shut down as part of this check.  Before later state-changing work, establish the required starting state and obtain appropriate authorization.

## 5. Troubleshoot only the failing layer

| Symptom | Smallest useful check |
| --- | --- |
| Process fails to start | Confirm the actual executable, dependencies, launch directory, and stderr.  Do not begin by rebuilding everything. |
| Window opens, but MCP initialization fails | Confirm the chosen flag, stdio client configuration, and uncontaminated stdout.  Do not configure the WebSocket address as an HTTP MCP endpoint. |
| Handshake succeeds, but tools or platforms are missing | Allow bounded startup time, refresh discovery, and inspect errors.  In live mode, check transport diagnostics and the desktop WebSocket setting. |
| Tools are listed, but state reads fail | Check the reported platform, connection state, and result envelope.  A roster alone does not prove the emulator is responsive. |
| An older release lacks a needed feature | Check that release's documented capabilities before selecting a newer release or a source build. |
| Connection is lost during an action | Preserve the error and last confirmed state.  Reconnect or restart explicitly, recheck readiness, and do not automatically replay a possibly completed action. |

Record the client version, executable hash, source or release identity, launch arguments, working directory, and first failing response.  A build problem belongs in the build workflow; a connection problem does not by itself justify changing the emulator or client architecture.

## Sources and limits

- [Official MCP documentation](https://github.com/slajerek/RetroDebugger/tree/devel/docs/mcp-server) is a moving reference; compare it with your selected revision.
- [Inspected mode parser](https://github.com/slajerek/RetroDebugger/blob/20bc9c2fcad3743f2a770b0a3ebaa4d6497f389c/src/RetroDebuggerAppInit.cpp#L233).
- [Inspected Windows working-directory contract](https://github.com/slajerek/RetroDebugger/blob/20bc9c2fcad3743f2a770b0a3ebaa4d6497f389c/platform/Windows/c64d/c64d.vcxproj#L73).
- [Inspected MCP implementation and schemas](https://github.com/slajerek/RetroDebugger/blob/20bc9c2fcad3743f2a770b0a3ebaa4d6497f389c/src/Remote/MCP/CMCPServer.cpp).
- [Inspected desktop server setting](https://github.com/slajerek/RetroDebugger/blob/20bc9c2fcad3743f2a770b0a3ebaa4d6497f389c/src/Tools/C64SettingsStorage.cpp#L379) and [startup condition](https://github.com/slajerek/RetroDebugger/blob/20bc9c2fcad3743f2a770b0a3ebaa4d6497f389c/src/Screens/CViewC64.cpp#L752).

This guide was checked against source, not by downloading or executing a release binary.  Its Windows launch examples still require validation on the reader's selected executable and client.  No private adapter, sample game, or preserved disk image is needed for the read-only connection check.
