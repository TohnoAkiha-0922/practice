"""
Blender MCP server for local scene automation.

Usage:
  python blender_mcp_server.py

Optional environment variables:
  BLENDER_EXE  Full path to blender.exe if Blender is not on PATH.
"""
import asyncio
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool


server = Server("blender-mcp")

WORKSPACE = Path(r"D:\code.c\Project20")
DEFAULT_OUTPUT = WORKSPACE / "blender_mcp_scene.blend"


def find_blender() -> str | None:
    env_path = os.environ.get("BLENDER_EXE")
    if env_path and Path(env_path).exists():
        return env_path

    on_path = shutil.which("blender")
    if on_path:
        return on_path

    local_appdata = Path(os.environ.get("LOCALAPPDATA", ""))
    candidate_patterns = [
        (Path(r"C:\Program Files\Blender Foundation"), "Blender*/blender.exe"),
        (Path(r"C:\Program Files (x86)\Blender Foundation"), "Blender*/blender.exe"),
        (local_appdata / "Programs" / "Blender Foundation", "Blender*/blender.exe"),
    ]
    for root, pattern in candidate_patterns:
        if not root.exists():
            continue
        try:
            matches = sorted(root.glob(pattern))
        except OSError:
            matches = []
        if matches:
            return str(matches[-1])
    return None


def run_blender_script(script: str, timeout: int = 120) -> str:
    blender = find_blender()
    if not blender:
        return (
            "Blender executable was not found. Install Blender or set BLENDER_EXE "
            "to the full path of blender.exe in .mcp.json."
        )

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(script)
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            [blender, "--background", "--python", tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = "\n".join(
            part.strip()
            for part in [result.stdout, result.stderr]
            if part and part.strip()
        )
        if result.returncode != 0:
            return f"Blender exited with code {result.returncode}.\n{output[:4000]}"
        return output[:4000] if output else "Blender script completed."
    except subprocess.TimeoutExpired:
        return f"Blender script timed out after {timeout} seconds."
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="get_blender_info",
            description="Find Blender and return version/path information.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="blender_python",
            description="Run Python code in Blender background mode.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python code to run inside Blender.",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds.",
                        "default": 120,
                    },
                },
                "required": ["code"],
            },
        ),
        Tool(
            name="create_basic_scene",
            description="Create a simple Blender scene and save it as a .blend file.",
            inputSchema={
                "type": "object",
                "properties": {
                    "output_path": {
                        "type": "string",
                        "description": "Destination .blend file path.",
                        "default": str(DEFAULT_OUTPUT),
                    },
                    "object_type": {
                        "type": "string",
                        "description": "Object to create: cube, sphere, cylinder, or cone.",
                        "default": "cube",
                    },
                    "size": {
                        "type": "number",
                        "description": "Main object size.",
                        "default": 2.0,
                    },
                },
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "get_blender_info":
        blender = find_blender()
        if not blender:
            return [
                TextContent(
                    type="text",
                    text=(
                        "Blender was not found. Install Blender, add it to PATH, "
                        "or set BLENDER_EXE in .mcp.json."
                    ),
                )
            ]
        try:
            result = subprocess.run(
                [blender, "--version"],
                capture_output=True,
                text=True,
                timeout=20,
            )
            text = f"Path: {blender}\n{result.stdout.strip()}"
        except Exception as exc:
            text = f"Path: {blender}\nCould not read version: {exc}"
        return [TextContent(type="text", text=text)]

    if name == "blender_python":
        code = arguments.get("code", "")
        timeout = int(arguments.get("timeout", 120))
        return [TextContent(type="text", text=run_blender_script(code, timeout))]

    if name == "create_basic_scene":
        output_path = arguments.get("output_path", str(DEFAULT_OUTPUT))
        object_type = arguments.get("object_type", "cube")
        size = float(arguments.get("size", 2.0))
        script = f"""
import bpy
from pathlib import Path

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

obj_type = {object_type!r}.lower()
size = {size!r}

if obj_type == "sphere":
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=size / 2)
elif obj_type == "cylinder":
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=size / 2, depth=size)
elif obj_type == "cone":
    bpy.ops.mesh.primitive_cone_add(vertices=48, radius1=size / 2, depth=size)
else:
    bpy.ops.mesh.primitive_cube_add(size=size)

obj = bpy.context.object
obj.name = "MCP Generated Object"
mat = bpy.data.materials.new("MCP Blue Material")
mat.diffuse_color = (0.12, 0.36, 0.95, 1.0)
obj.data.materials.append(mat)

bpy.ops.object.light_add(type='AREA', location=(3, -4, 5))
bpy.context.object.name = "MCP Softbox"
bpy.context.object.data.energy = 500
bpy.context.object.data.size = 4

bpy.ops.object.camera_add(location=(4, -6, 4), rotation=(1.109, 0, 0.588))
bpy.context.scene.camera = bpy.context.object

out = Path({output_path!r})
out.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(out))
print(f"Saved scene to {{out}}")
"""
        return [TextContent(type="text", text=run_blender_script(script))]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    async with stdio_server() as (reader, writer):
        await server.run(reader, writer, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
