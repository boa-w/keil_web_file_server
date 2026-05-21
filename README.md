# Keil Web File Server

用于在 **Keil uVision -> Customize Tools Menu** 中调用，把当前 Keil 工作目录（或指定目录）暴露为 Web 文件访问服务。

## 架构

- 后端：`FastAPI`（`keil_web_file_server.py`）
- 前端：`Vue 3 + Vite + vue-router`（`webui-vue/`，路由级独立页面）
- 构建：`PyInstaller` 单文件 exe（打包 Vue `dist` 静态资源）

## 功能

- 默认访问 Keil 当前工作目录（不传路径参数）
- Web 端动态切换访问根目录（无需重启）
- 目录浏览、文本/图片/PDF/二进制(HEX)预览、文件下载
- 目录列表分页与排序（名称/大小）
- 文件夹打包下载（ZIP）
- 文件夹异步打包任务队列（创建任务、状态轮询、完成后下载、任务删除）
- 下载对空格/中文/特殊符号文件名兼容（RFC 5987）
- 路径越界保护（限制在当前根目录）
- 提供调试页面（上下文/进程链/模块列表/文件探针），便于对比 Keil 与独立运行差异

## 目录

- `keil_web_file_server.py`: FastAPI 服务
- `webui-vue/`: Vue + Vite 前端工程
- `build_frontend.bat`: 前端构建脚本
- `requirements-build.txt`: Python 构建依赖
- `build_exe.bat`: EXE 构建脚本
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

## 使用 `.venv` + `uv` 构建 EXE

先安装 Python 依赖：

```bash
uv venv .venv
uv pip install --python .venv/Scripts/python.exe -r requirements-build.txt
```

再构建前端：

```bat
build_frontend.bat
```

最后打包 exe：

```bat
build_exe.bat
```

## Keil Tools Menu 示例

`Project -> Manage -> Configure Tools Menu...`

- Menu Text: `Web File Server`
- Command: `D:\\...\\dist\\keil_web_file_server.exe`
- Arguments: `"$P" --open`
- Initial Folder: `$P`

## 参数

- `root`：初始根目录，默认当前目录
- `--open`：启动后自动打开浏览器
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
