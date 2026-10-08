"""
SolidWorks MCP Server —— 让 Claude Code 操控 SolidWorks 2024
使用: python solidworks_mcp_server.py
"""
import asyncio
import pythoncom
import win32com.client
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

server = Server("solidworks-mcp")

# SolidWorks 模板路径
TEMPLATE = r"C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2024\templates\gb_part.prtdot"


def get_sw():
    """连接当前运行的 SolidWorks"""
    pythoncom.CoInitialize()
    sw = win32com.client.Dispatch("SldWorks.Application")
    sw.Visible = True
    return sw


def new_part(sw):
    """创建新零件"""
    return sw.NewDocument(TEMPLATE, 0, 0, 0)


@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="create_cube",
            description="在 SolidWorks 中创建一个正方体零件",
            inputSchema={
                "type": "object",
                "properties": {
                    "side_length": {
                        "type": "number",
                        "description": "边长(mm)，默认100",
                        "default": 100.0
                    }
                }
            }
        ),
        Tool(
            name="create_cylinder",
            description="在 SolidWorks 中创建一个圆柱体零件",
            inputSchema={
                "type": "object",
                "properties": {
                    "diameter": {
                        "type": "number",
                        "description": "直径(mm)，默认50",
                        "default": 50.0
                    },
                    "height": {
                        "type": "number",
                        "description": "高度(mm)，默认100",
                        "default": 100.0
                    }
                }
            }
        ),
        Tool(
            name="get_active_doc_info",
            description="查看 SolidWorks 当前活动文档的信息",
            inputSchema={"type": "object", "properties": {}}
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    sw = get_sw()

    if name == "create_cube":
        side = arguments.get("side_length", 100.0)
        doc = new_part(sw)
        part = doc

        # 在前视基准面上画草图
        part.SketchManager.InsertSketch(True)
        part.SketchManager.CreateCenterRectangle(0, 0, 0, side/2, side/2, 0)

        # 拉伸
        part.FeatureManager.FeatureExtrusion2(
            True, False, False, 0, 0, side, 0.01,
            False, False, False, False, 0, 0, False, False,
            False, False, True, True, True, 0, 0, False
        )
        return [TextContent(type="text", text=f"✅ 已创建 {side}mm 的正方体")]

    elif name == "create_cylinder":
        dia = arguments.get("diameter", 50.0)
        h = arguments.get("height", 100.0)
        doc = new_part(sw)
        part = doc

        part.SketchManager.InsertSketch(True)
        part.SketchManager.CreateCircle(0, 0, 0, dia/2, 0, 0)

        part.FeatureManager.FeatureExtrusion2(
            True, False, False, 0, 0, h, 0.01,
            False, False, False, False, 0, 0, False, False,
            False, False, True, True, True, 0, 0, False
        )
        return [TextContent(type="text", text=f"✅ 已创建直径{dia}mm、高{h}mm 的圆柱体")]

    elif name == "get_active_doc_info":
        doc = sw.ActiveDoc
        if doc is None:
            return [TextContent(type="text", text="当前没有打开的文档")]
        title = doc.GetTitle()
        dtype = doc.GetType()
        return [TextContent(type="text", text=f"文档名: {title}\n类型: {dtype}")]

    return [TextContent(type="text", text=f"未知命令: {name}")]


async def main():
    async with stdio_server() as (reader, writer):
        await server.run(reader, writer, server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
