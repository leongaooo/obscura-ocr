# ObscuraOCR · 暗纹 OCR

**自由部署，简易集成的开源 OCR 服务。**

[English](README.en.md) · [部署指南](docs/deployment-modes.md) · [API 集成](docs/integration.md) · [交付计划](docs/roadmap.md)

把图片和 PDF 转为带位置、置信度与来源证据的文字及票据字段。无需云端账户，不绑定报销或其他业务系统；你决定服务运行在哪台机器、文件留在哪里。

## 已实现能力

- 真实 PaddleOCR 本地推理：中文/英文文字、页码、文字框、置信度。
- 中国票据技术分类与字段提取：票种、票号、日期、购销方、总额、税额和适用行程。
- 原始文字与字段证据同源；未知保持空值，冲突标记复核，不根据文件名猜测。
- PNG、JPEG、PDF 上传；请求结束删除临时文件，结果不写入持久库。
- 独立 HTTP API、OpenAPI 和浏览器工作台；无需前端构建或业务数据库。

**这里的“脱敏开源”是清除公司资料、真实票样及业务耦合。文件自动遮盖、Office 解析和企业治理属于后续规划，当前服务不提供。**

## 本机部署（Windows / Linux）

需要 Python 3.11–3.13。CPU 是默认方案；模型首次准备需要网络，完成后可以离线运行。

```bash
python -m venv .venv
# Windows PowerShell
.venv/Scripts/python.exe -m pip install -e ".[paddle]"
.venv/Scripts/obscura-ocr.exe prepare
.venv/Scripts/obscura-ocr.exe serve
# Linux / macOS: use .venv/bin/python and .venv/bin/obscura-ocr instead
```

打开 [本地工作台](http://127.0.0.1:18083) 验收；接口说明位于 `/docs`，模型就绪检查位于 `/health/ready`。未准备模型时就绪检查返回 503，不会伪装识别成功。

## Docker Compose 部署

```bash
docker compose build
docker compose run --rm ocr obscura-ocr prepare
docker compose up -d
```

默认仅映射本机 `127.0.0.1:18083`，模型保存在命名卷 `models`。CPU 容器方案待目标 Linux Docker 环境实测；GPU 不包含在默认镜像内。离线交付需提前准备依赖镜像和模型卷。

## 一次 HTTP 请求即可集成

```bash
curl -F "file=@examples/synthetic-invoice.png" http://127.0.0.1:18083/api/recognize
```

Windows 使用 `curl.exe`。Python 标准库示例无需额外客户端 SDK：

```bash
python examples/client.py examples/synthetic-invoice.png
```

返回 `tokens`（文字、页码、坐标和置信度）、`candidates`（值、证据和复核原因）、输入 SHA-256 和耗时。金额使用十进制字符串；号码保留前导零；多页文字均返回，但跨页票据字段拒绝拼接，交给调用方复核。

## 安全边界

默认 20 MB、10 页、单并发；不包含账号、TLS 或多租户授权。用于公网前应部署鉴权反向代理、限制请求体与超时并隔离运行环境。不要把真实文件、识别输出或密钥提交到 Git。

结果包含原始识别文字，属于敏感数据。临时文件删除不等于磁盘安全擦除；崩溃时应由部署方清理临时目录。

## 开发与文档

```bash
python -m pip install -e ".[test]"
python -m pytest
python -m ruff check src tests scripts examples
python -m ruff format --check src tests scripts examples
```

[最终设计](docs/final-design.md) · [功能架构](docs/functional-architecture.md) · [商业化](docs/commercialization.md) · [依赖声明](THIRD_PARTY_NOTICES.md)

本仓库自有代码采用 [Apache-2.0](LICENSE)。引擎、模型、PDFium 及其传递依赖保留各自许可证；模型不随仓库分发。
