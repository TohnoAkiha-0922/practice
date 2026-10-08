"""
MATLAB MCP Server —— 让 Claude Code 调用 MATLAB R2024a
"""
import asyncio
import subprocess
import tempfile
import os
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

server = Server("matlab-mcp")

MATLAB = r"C:\Program Files\MATLAB\R2024a\bin\matlab.exe"


def run_matlab(code: str) -> str:
    """运行 MATLAB 代码并返回结果"""
    # 写入临时文件
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".m", delete=False, encoding="utf-8")
    try:
        tmp.write(code)
        tmp.close()

        result = subprocess.run(
            [MATLAB, "-batch", f"run('{tmp.name}')"],
            capture_output=True, text=True, timeout=60
        )
        output = result.stdout.strip()
        if result.stderr:
            output += "\n" + result.stderr.strip()
        return output[:3000] if output else "执行完成，无输出"
    finally:
        try:
            os.unlink(tmp.name)
        except:
            pass


@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="matlab_eval",
            description="在 MATLAB 中运行代码并返回结果。支持：数学计算、矩阵运算、绘图(saveas)等。",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "要运行的 MATLAB 代码"
                    }
                },
                "required": ["code"]
            }
        ),
        Tool(
            name="matlab_plot",
            description="在 MATLAB 中绘图并保存为图片",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "MATLAB 绘图代码，图片会自动保存为 plot.png"
                    },
                    "output_path": {
                        "type": "string",
                        "description": "输出图片路径，默认 D:\\code.c\\Project20\\plot.png",
                        "default": "D:\\code.c\\Project20\\plot.png"
                    }
                },
                "required": ["code"]
            }
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "matlab_eval":
        code = arguments.get("code", "")
        output = run_matlab(code)
        return [TextContent(type="text", text=output)]

    elif name == "matlab_plot":
        code = arguments.get("code", "")
        output_path = arguments.get("output_path", r"D:\code.c\Project20\plot.png")

        wrap = f"""
{code}
saveas(gcf, '{output_path}');
disp('图片已保存: {output_path}');
"""
        output = run_matlab(wrap)
        return [TextContent(type="text", text=output)]

    return [TextContent(type="text", text=f"未知命令: {name}")]


async def main():
    async with stdio_server() as (reader, writer):
        await server.run(reader, writer, server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
