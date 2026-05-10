# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None
project_root = Path.cwd().resolve()

datas = []
for relative in [
    "docs/prompt.md",
    "docs/prompt_dynamic.md",
    "docs/prompt_podcast.md",
]:
    src = project_root / relative
    if src.exists():
        datas.append((str(src), "docs"))

hiddenimports = []
hiddenimports.extend(collect_submodules("app"))
hiddenimports.extend(
    [
        "aiohttp",
        "dashscope",
        "feishu_sdk",
        "faster_whisper",
        "httpx",
        "modelscope",
        "openai",
        "oss2",
        "qwen_asr",
        "sqlalchemy",
        "uvicorn",
    ]
)

a = Analysis(
    [str(project_root / "entrypoints" / "entrypoint-scheduler.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="bili-scheduler",
    console=False,
    disable_windowed_traceback=True,
    strip=False,
    upx=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="bili-scheduler",
)
