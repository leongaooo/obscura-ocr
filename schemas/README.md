# 数据契约示例

这些文件描述模块之间的最小交换结构，属于设计示例，不代表已经冻结的生产 API。

- `ocr-result.schema.json`：页面、文字块、坐标和引擎信息
- `sensitive-field.schema.json`：敏感字段候选、证据和状态
- `redaction-result.schema.json`：脱敏动作、校验报告和输出指纹

所有对象都应关联任务标识和输入指纹；普通日志不保存完整敏感原文。
