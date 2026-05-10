# Windows 安装包说明

## 交付形态

发布产物由三部分组成：

- `bili-flow-launcher.exe`：唯一的用户入口
- `bili-flow-backend.exe`：管理后台服务
- `bili-flow-scheduler.exe`：定时任务和队列服务

安装后：

- 程序文件安装到 `%LOCALAPPDATA%\Programs\bili-flow`
- 运行时数据写入 `%LOCALAPPDATA%\bili-flow`
- 双击桌面图标会自动启动后端和调度器，并打开本地管理页

## 运行目录

默认运行目录由 `BILI_AUTO_HOME` 控制。安装版默认使用：

- `%LOCALAPPDATA%\bili-flow`

该目录下会保存：

- `.env`
- `data/`
- `logs/`
- `models/`

如果 `.env` 不存在，安装器会从发布包中的 `.env.example` 初始化一份。

## 打包前置条件

- Node.js 22+
- `uv`
- PyInstaller
- Inno Setup 6
- 可用的 `ffmpeg` / `ffprobe`

## 打包步骤

更新代码后，按下面顺序重新生成发布包：

```powershell
scripts\build_frontend.ps1
scripts\build_pyinstaller.ps1
scripts\build_installer.ps1
```

说明：

1. `build_frontend.ps1` 负责生成 `web/dist`
2. `build_pyinstaller.ps1` 负责生成 `bili-flow-backend` / `bili-flow-scheduler` / `bili-flow-launcher`
3. `build_installer.ps1` 负责调用 Inno Setup 生成最终安装器

## 升级发布

发新版本时，直接分发 `dist\installer` 下的新安装包即可。

覆盖安装时：

- 不会覆盖 `%LOCALAPPDATA%\bili-flow\.env`
- 不会删除 `data/`
- 不会删除 `logs/`
- 不会删除 `models/`

也就是说，程序文件会更新，用户本地配置和运行数据会保留。
