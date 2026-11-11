# 本机交付证据

日期：2026-11-11。

## 自动验证

- `python -m pytest`：6 项通过。覆盖未知/零值、前导零、日期非法、字段冲突、跨页隔离、上传格式/大小、临时文件清理、就绪失败及 PDF 页数限制。
- `python -m ruff check src tests scripts examples`：通过。
- `python -m ruff format --check src tests scripts examples`：21 个 Python 文件通过。
- `python -m pip check`：无损坏依赖。
- Markdown 本地链接检查：无断链。
- 公开源码与文档扫描：未发现旧包名、旧功能目录、内部地址或个人用户名；模型、环境、日志和本机结果在 Git 忽略范围内。

## 真实模型与 HTTP

PaddleOCR / PaddlePaddle / PaddleX 使用本地准备的官方模型缓存，不使用 Mock。

- 合成 PNG：8 个文字块，总额 `123.45`，票号 `00000000123456789012`；首轮 3622 ms。
- 同图合成 PDF：8 个文字块，总额 `123.45`；修复资源句柄释放后 5419 ms。
- 就绪接口 `/health/ready`：返回 `ready: true`。

上述耗时只是这台机器的合成样本观测，不代表行业准确率或性能基准。不使用真实公司票样作为开源验收数据。

## 用户验收与发布状态

- 用户于 2026-11-11 明确回复“验收通过，可以发布”。浏览器连接恢复后已看到工作台显示真实识别结果、字段与 JSON 下载入口；用户材料与结果未写入公开仓库。
- Docker Compose、Linux 与 GPU 环境未实测；配方和限制已在 README 中说明。
- GitHub 发布按用户授权在本地验收后执行；远端仓库、提交和 CI 待发布时核验。

## 已解决问题

PDFium 当前锁定版本不支持原先写入的上下文管理语法，已改为显式 `closing`，补充有效 PDF、页数限制和临时句柄清理回归。真实 PDF HTTP 复测成功。
