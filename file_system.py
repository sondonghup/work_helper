import asyncio

from pathlib import Path
from typing import List, Optional
import os
import shutil
import mimetypes
from mcp.server import Server
from mcp.types import Resource, Tool, TextContent

class FileSystemManager:
    def __init__(self, base_path: str | Path):
        self.base_path = Path(base_path).resolve()
        if not self.base_path.exists():
            self.base_path.mkdir(parents=True)

    def _validate_path(self, path: str | Path) -> Path:
        """주어진 경로가 base_path 내에 있는지 확인"""
        full_path = (self.base_path / path).resolve()
        if not str(full_path).startswith(str(self.base_path)):
            raise ValueError("Invalid path: Access denied")
        return full_path

    async def read_file(self, path: str) -> tuple[str, str]:
        """파일 읽기"""
        full_path = self._validate_path(path)
        if not full_path.is_file():
            raise FileNotFoundError(f"File not found: {path}")

        mime_type, _ = mimetypes.guess_type(str(full_path))
        content = await asyncio.to_thread(full_path.read_text)
        return content, mime_type or "text/plain"

    async def write_file(self, path: str, content: str) -> None:
        """파일 쓰기"""
        full_path = self._validate_path(path)
        await asyncio.to_thread(full_path.write_text, content)

    async def list_directory(self, path: str = "") -> List[dict]:
        """디렉토리 내용 나열"""
        full_path = self._validate_path(path)
        if not full_path.is_dir():
            raise NotADirectoryError(f"Not a directory: {path}")

        items = []
        for item in full_path.iterdir():
            rel_path = str(item.relative_to(self.base_path))
            items.append({
                "name": item.name,
                "path": rel_path,
                "type": "directory" if item.is_dir() else "file",
                "size": item.stat().st_size if item.is_file() else None
            })
        return items

    async def search_files(self, pattern: str) -> List[dict]:
        """파일 검색"""
        results = []
        async for path in self._walk_async(self.base_path):
            if pattern.lower() in path.name.lower():
                rel_path = str(path.relative_to(self.base_path))
                results.append({
                    "name": path.name,
                    "path": rel_path,
                    "type": "directory" if path.is_dir() else "file"
                })
        return results

    async def _walk_async(self, path: Path):
        """비동기 파일 시스템 탐색"""
        dirs = []
        files = []
        async for entry in asyncio.to_thread(os.scandir, str(path)):
            if entry.is_dir():
                dirs.append(entry)
            else:
                files.append(entry)

        for entry in files:
            yield Path(entry.path)

        for entry in dirs:
            async for x in self._walk_async(Path(entry.path)):
                yield x


class FileServer:
    def __init__(self, base_path: str | Path):
        self.fs = FileSystemManager(base_path)
        self.server = Server("file-server")

    def setup_handlers(self):
        """MCP 핸들러 설정"""
        @self.server.list_resources()
        async def list_resources() -> list[Resource]:
            items = await self.fs.list_directory()
            return [
                Resource(
                    uri=f"file:///{item['path']}",
                    name=item['name'],
                    mimeType=(
                        "inode/directory" if item['type'] == "directory" 
                        else mimetypes.guess_type(item['name'])[0] or "text/plain"
                    ),
                    description=f"{'Directory' if item['type'] == 'directory' else 'File'}: {item['path']}"
                )
                for item in items
            ]

        @self.server.read_resource()
        async def read_resource(uri: str) -> str:
            path = uri.replace("file:///", "")
            content, _ = await self.fs.read_file(path)
            return content

        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            return [
                Tool(
                    name="write_file",
                    description="파일 작성",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "content": {"type": "string"}
                        },
                        "required": ["path", "content"]
                    }
                ),
                Tool(
                    name="search_files",
                    description="파일 검색",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "pattern": {"type": "string"}
                        },
                        "required": ["pattern"]
                    }
                )
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict) -> list[TextContent]:
            if name == "write_file":
                await self.fs.write_file(
                    arguments["path"],
                    arguments["content"]
                )
                return [TextContent(
                    type="text",
                    text=f"File written: {arguments['path']}"
                )]

            elif name == "search_files":
                results = await self.fs.search_files(arguments["pattern"])
                return [TextContent(
                    type="text",
                    text="\n".join(
                        f"[{r['type']}] {r['path']}"
                        for r in results
                    ) or "No files found"
                )]

            raise ValueError(f"Unknown tool: {name}")


async def main():
    base_path = Path("/Users/sondonghyeob/Library/Mobile Documents/iCloud~md~obsidian/Documents/daily report/")  # 작업 디렉토리 지정
    server = FileServer(base_path)
    server.setup_handlers()
    await server.server.run_stdio()


if __name__ == "__main__":
    asyncio.run(main())
