# Keil Web File Server

用于在 **Keil uVision -> Customize Tools Menu** 中调用，把当前 Keil 工作目录（或指定目录）暴露为 Web 文件访问服务。

## 架构

- 后端：`FastAPI`（`keil_web_file_server.py`）
- 前端：`Vue 3 + Vite + vue-router`（`webui-vue/`，路由级独立页面）
- 构建：`PyInstaller` 单文件 exe（打包 Vue `dist` 静态资源）
- CI：GitHub Actions 自动构建 Windows EXE 并上传产物

## 功能

- 默认访问 Keil 当前工作目录（不传路径参数）
- Web 端动态切换访问根目录（无需重启）
- 目录浏览、文本/图片/PDF/二进制(HEX)预览、文件下载
- 目录列表分页与排序（名称/大小）
- 文件多选并批量打包下载
- 从本机上传文件并原子替换现有文件
- 文件夹打包下载（ZIP）
- 文件夹异步打包任务队列（创建任务、状态轮询、完成后下载、任务删除）
- 下载对空格/中文/特殊符号文件名兼容（RFC 5987）
- 路径越界保护（限制在当前根目录）
- 提供调试页面（上下文/进程链/模块列表/文件探针），便于对比 Keil 与独立运行差异

## 目录

- `keil_web_file_server.py`: FastAPI 服务
- `webui-vue/`: Vue + Vite 前端工程
- `requirements-build.txt`: Python 构建依赖
- `build_exe.bat`: 本地一键构建脚本（前端 + EXE）
- `.github/workflows/build-exe.yml`: Windows 自动构建流程
- `dist/keil_web_file_server.exe`: 输出文件

## 前端开发

在 `webui-vue` 下：

```bash
npm install
npm run dev
```

开发时访问 `http://127.0.0.1:5173`，API 默认代理到 `http://127.0.0.1:8765`。

## 本地运行后端（Python）

```bash
python keil_web_file_server.py
```

指定根目录：

```bash
python keil_web_file_server.py "D:\\your\\path"
```

局域网暴露：

```bash
python keil_web_file_server.py --public --port 8765
```

## 本地构建 EXE

先创建 Python 虚拟环境：

```bash
uv venv .venv
```

也可以使用 Python 自带的 `venv`：

```bash
python -m venv .venv
```

然后运行一键构建脚本（会安装依赖、构建前端并打包 EXE）：

```bat
build_exe.bat
```

## GitHub Actions 自动构建

推送到 `main` 或 `master`、创建 Pull Request，或在 Actions 页面手动运行
`Build Windows EXE` workflow 后，会生成名为 `keil-web-file-server-windows` 的构建产物，
其中包含 `keil_web_file_server.exe`。

## Keil Tools Menu 示例

`Project -> Manage -> Configure Tools Menu...`

- Menu Text: `Web File Server`
- Command: `D:\\...\\dist\\keil_web_file_server.exe`
- Arguments: `"$P." --open --detach`
- Initial Folder: `$P`

`--detach` 会让 Keil 直接启动的引导进程派生后台 Worker 后立即退出，因此关闭
Keil 时不会继续等待 Web 服务。后台日志位于
`%LOCALAPPDATA%\KeilWebFileServer\server.log`。

`$P` 通常以反斜杠结尾，写成 `"$P."` 可以避免 Windows 把路径后的右引号
与 `--open --detach` 合并为同一个参数。

## 参数

- `root`：初始根目录，默认当前目录
- `--open`：启动后自动打开浏览器
- `--detach`：派生 Windows 后台 Worker 后立即返回，避免 Keil 等待服务进程
- `--port 8765`：指定端口
- `--public`：等价于 `--host 0.0.0.0`

## 调试 API 用法

服务启动后（默认 `http://127.0.0.1:8765`），可直接请求以下接口获取调试信息。

### 1) 聚合报告（推荐）

- `GET /api/debug/report`
- 可选参数：
  - `include_all_env=true|false`
  - `env_limit=200`
  - `modules_limit=400`
  - `modules_keyword=keil`
  - `probe_path=相对root路径`
  - `probe_head=128`
  - `probe_tail=128`
  - `probe_hash_mode=sample|full`

示例（PowerShell）：

```powershell
Invoke-RestMethod "http://127.0.0.1:8765/api/debug/report?include_all_env=true&modules_limit=800&modules_keyword=keil&probe_path=JK_SmartProduct_CanAnalysis/SRC/JK_SmartProduct_Application_CanAnalysis.c&probe_hash_mode=full" | ConvertTo-Json -Depth 12
```

示例（curl）：

```bash
curl "http://127.0.0.1:8765/api/debug/report?include_all_env=true&modules_limit=800&modules_keyword=keil&probe_path=JK_SmartProduct_CanAnalysis/SRC/JK_SmartProduct_Application_CanAnalysis.c&probe_hash_mode=full"
```

### 2) 单项接口

- `GET /api/debug/context`：进程/环境/recent_access
- `GET /api/debug/process-tree`：父进程链
- `GET /api/debug/modules?limit=400&keyword=keil`：模块列表
- `GET /api/debug/file-probe?path=相对路径&head=128&tail=128&hash_mode=sample|full`：文件探针（首尾字节+SHA256）
- `POST /api/open-in-vscode`：在服务器本机的 VS Code 中打开文件，请求体为 `{ "path": "相对路径" }`；仅接受本机请求
- `POST /api/download-selected`：将请求体 `{ "paths": ["相对路径"] }` 中的文件打包为 ZIP
- `PUT /api/file?path=相对路径`：用请求体中的原始文件内容替换目标文件；仅接受本机请求
