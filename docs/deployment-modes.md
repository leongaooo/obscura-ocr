# 部署指南 / Deployment

## 本机 Python（默认）

详见中英文 README 的安装命令。`obscura-ocr prepare` 显式下载模型；`obscura-ocr serve` 默认监听 `127.0.0.1:18083`。

可通过环境变量配置：

| 变量 | 默认 | 用途 |
| --- | --- | --- |
| OBSCURA_OCR_MODEL_HOME | models | 模型缓存目录，离线前先准备 |
| OBSCURA_OCR_MAX_FILE_BYTES | 20971520 | 上传大小限制 |
| OBSCURA_OCR_MAX_PDF_PAGES | 10 | PDF 页数限制 |
| OBSCURA_OCR_CONCURRENCY | 1 | 共享引擎并发，建议保持 1 |
| OBSCURA_OCR_CPU_THREADS | 2 | CPU 推理线程 |
| OBSCURA_OCR_CANDIDATE_PDF_MAX_SIDE | 1800 | PDF 渲染最长边，坐标基于此像素尺寸 |

Windows 环境变量示例：`$env:OBSCURA_OCR_MODEL_HOME='D:/ocr-models'`；Linux 示例：`export OBSCURA_OCR_MODEL_HOME=/srv/ocr-models`。请勿把个人机器路径写入公共配置。

## Docker Compose（CPU）

```bash
docker compose build
docker compose run --rm ocr obscura-ocr prepare
docker compose up -d
docker compose logs -f
docker compose down
```

默认仅暴露回环端口，命名卷保留模型。使用非 root 用户。此配方需目标 Docker 环境实测，不声明已通过容器验收。

## 离线环境

联网机器预先安装依赖并准备模型；镜像与模型目录按平台交付。运行时禁用模型下载，防火墙控制出站；模型框架仍可能执行连通性探测，要求严格离线时在网络层阻断。配置 `PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True` 可禁用框架的来源探测（依引擎版本验证）。

## 对外服务

需另外提供鉴权、TLS、请求体上限、连接超时、进程资源限制和审计。当前不是多租户平台。默认单进程，运行中不要清空模型缓存。GPU 依赖和容器由后续任务单独验证。

## 启停与升级

前台进程 Ctrl+C 停止；后台服务由操作者记录 PID 并使用系统服务管理器停止。升级前保留上一安装包、依赖清单和模型缓存；新环境通过就绪及合成样例后切换流量。当前无数据库迁移。
