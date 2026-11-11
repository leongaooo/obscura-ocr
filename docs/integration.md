# API 集成

## 请求

`POST /api/recognize`，multipart 字段 `file`，内容支持 PNG/JPEG/PDF。文件名和 MIME 不能代替内容检查。无需云端令牌；公网部署方应在反向代理补充认证。

## 响应

| 字段 | 含义 |
| --- | --- |
| requestId | 请求追踪 ID；不是可查询任务或幂等键 |
| documentSha256 | 原始上传文件 SHA-256 |
| tokens | text、confidence、box、page；box 为左上右下的处理后像素坐标 |
| candidates | value、rawText、confidence、evidence、reviewReasons |
| documentType / documentSubtype | OCR 标题证据的分类候选 |
| reviewRequired / warnings | 至少一项缺失或冲突时建议复核 |
| durationMs | 处理耗时，毫秒 |

PDF 每页按最长边 1800 像素渲染（可配置）；图片在 EXIF 纠正、缩放之后识别。坐标不能直接投影回原图，调用方需要保留同样的缩放与方向处理。`tokens` 页码从 1 开始。暂无原图坐标转换 API。

金额使用字符串而不是浮点数。字段未知为 null，不推算缺失税额，不把不确定分类伪装为成功。服务不会创建票据、数据库记录或业务审批。

## 错误

422：缺文件、空文件、格式错误、损坏/加密 PDF、超限。429：引擎繁忙。503：引擎未准备或推理失败。错误包含 `message`，集成方优先展示它；FastAPI 缺字段校验使用标准 `detail` 响应。

超时断连不代表服务器推理已取消；不在共享推理线程仍运行时释放并发锁。重试会重新执行识别，当前不保证幂等。

## Python

```bash
python examples/client.py examples/synthetic-invoice.png --url http://127.0.0.1:18083/api/recognize
```

Java、Node.js、Go 等客户端使用同样的 multipart 协议，无需专有 SDK。完整字段类型以运行服务 `/openapi.json` 为入口；原始结果以实际 JSON 为准。
