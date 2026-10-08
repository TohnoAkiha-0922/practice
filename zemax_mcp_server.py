"""
Zemax OpticStudio MCP server.

This server connects to Ansys Zemax OpticStudio through ZOS-API and exposes a
small set of safe, practical tools for opening, inspecting, and saving optical
systems.

Supports both older OpticStudio (pre-2021, no ZOSAPI_NetHelper) and newer versions.
"""
import asyncio
import os
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

import pythonnet

server = Server("zemax-mcp")

_zosapi: dict[str, Any] = {
    "initialized": False,
    "connection": None,
    "application": None,
}


def _zemax_root() -> Path:
    env_root = os.environ.get("ZEMAX_ROOT") or os.environ.get("OPTICSTUDIO_ROOT")
    if env_root:
        root = Path(env_root)
        if root.exists():
            return root

    program_files = [
        os.environ.get("ProgramFiles"),
        os.environ.get("ProgramFiles(x86)"),
    ]
    for base in program_files:
        if not base:
            continue
        for candidate in [
            Path(base) / "Zemax OpticStudio",
            Path(base) / "Ansys Zemax OpticStudio",
            Path(base) / "ANSYS Inc" / "Zemax OpticStudio",
        ]:
            if candidate.exists():
                return candidate

    raise RuntimeError(
        "Could not find OpticStudio installation. Set ZEMAX_ROOT or "
        "OPTICSTUDIO_ROOT to the OpticStudio installation directory."
    )


def _connect():
    if _zosapi["application"] is not None:
        return _zosapi["application"]

    pythonnet.load()

    import clr

    zemax_dir = str(_zemax_root())
    os.environ["PATH"] = zemax_dir + os.pathsep + os.environ.get("PATH", "")

    clr.AddReference(os.path.join(zemax_dir, "ZOSAPI.dll"))
    clr.AddReference(os.path.join(zemax_dir, "ZOSAPI_Interfaces.dll"))

    from ZOSAPI import ZOSAPI_Connection

    connection = ZOSAPI_Connection()

    application = connection.ConnectAsExtension(0)
    if application is None:
        application = connection.CreateNewApplication()

    if application is None:
        raise RuntimeError("Could not start or connect to OpticStudio.")

    if not application.IsValidLicenseForAPI:
        application.CloseApplication()
        raise RuntimeError("OpticStudio license is not valid for ZOS-API.")

    _zosapi.update(
        {
            "initialized": True,
            "connection": connection,
            "application": application,
        }
    )
    return application


def _primary_system():
    app = _connect()
    system = app.PrimarySystem
    if system is None:
        raise RuntimeError("Connected to OpticStudio, but no primary system is available.")
    return system


def _system_summary(system) -> str:
    lens = system.LDE
    fields = system.SystemData.Fields
    wavelengths = system.SystemData.Wavelengths
    title = system.SystemData.Title or "(untitled)"
    file_name = system.SystemFile or "(not saved)"
    return (
        f"Title: {title}\n"
        f"File: {file_name}\n"
        f"Surfaces: {lens.NumberOfSurfaces}\n"
        f"Fields: {fields.NumberOfFields}\n"
        f"Wavelengths: {wavelengths.NumberOfWavelengths}"
    )


@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="zemax_status",
            description="Connect to Zemax OpticStudio through ZOS-API and report status.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="zemax_new_sequential",
            description="Create a new sequential OpticStudio system.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="zemax_open_file",
            description="Open a .zmx or .zos OpticStudio file.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the OpticStudio file.",
                    }
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="zemax_save_as",
            description="Save the current OpticStudio system to a new path.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute output path, usually ending in .zos or .zmx.",
                    }
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="zemax_system_info",
            description="Return basic information about the active optical system.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="zemax_set_title",
            description="Set the title of the active optical system.",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "New system title."}
                },
                "required": ["title"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    try:
        if name == "zemax_status":
            app = _connect()
            version = getattr(app, "Version", "(version unavailable)")
            return [
                TextContent(
                    type="text",
                    text=(
                        "Connected to Zemax OpticStudio.\n"
                        f"Version: {version}\n"
                        f"API license valid: {app.IsValidLicenseForAPI}"
                    ),
                )
            ]

        if name == "zemax_new_sequential":
            system = _primary_system()
            system.New(False)
            return [TextContent(type="text", text="Created a new sequential system.")]

        if name == "zemax_open_file":
            path = Path(arguments.get("path", "")).expanduser()
            if not path.exists():
                raise FileNotFoundError(f"OpticStudio file not found: {path}")
            system = _primary_system()
            system.LoadFile(str(path), False)
            return [TextContent(type="text", text="Opened file.\n" + _system_summary(system))]

        if name == "zemax_save_as":
            path = Path(arguments.get("path", "")).expanduser()
            path.parent.mkdir(parents=True, exist_ok=True)
            system = _primary_system()
            system.SaveAs(str(path))
            return [TextContent(type="text", text=f"Saved current system to: {path}")]

        if name == "zemax_system_info":
            system = _primary_system()
            return [TextContent(type="text", text=_system_summary(system))]

        if name == "zemax_set_title":
            title = arguments.get("title", "")
            system = _primary_system()
            system.SystemData.Title = title
            return [TextContent(type="text", text=f"Set system title to: {title}")]

        return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except Exception as exc:
        return [TextContent(type="text", text=f"Zemax MCP error: {exc}")]


async def main():
    async with stdio_server() as (reader, writer):
        await server.run(reader, writer, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
