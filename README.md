# ACEngine Client SDK

用于调用 ACE 美学计算服务的 Python SDK。支持 MNet / ICAA17K 的私有资源调用、IQA 图片/视频异步任务，以及现有单项评分和图像/视频处理接口。

本文档对应 **SDK 0.2.0**，需要 Python 3.9 或更新版本。发行状态以 PyPI 和 GitHub 的实际版本为准；尚未发布的改动请使用本地源码安装。维护者首次发布步骤见 [PUBLISHING.md](PUBLISHING.md)。

## 安装

发布到 PyPI 后，用户可以直接安装：

```bash
pip install ace-engine-sdk
```

```bash
# GitHub 主分支
pip install --upgrade git+https://github.com/YuqiPlus/ACEngine-Client.git

# 本地开发
pip install -e .

# 已有的 0.1.0 标签（不含本轮新功能）
pip install git+https://github.com/YuqiPlus/ACEngine-Client.git@v0.1.0
```

HTTPS 不通时可以使用 SSH（需要已经配置 GitHub SSH 密钥）：

```bash
pip install git+ssh://git@github.com/YuqiPlus/ACEngine-Client.git
```

代理、证书和网络连接由本机配置，不在 SDK 中固定代理地址，也不关闭 HTTPS 证书验证。卸载包名为 `ace-engine-sdk`：

```bash
pip show ace-engine-sdk
pip uninstall ace-engine-sdk
```

## 快速开始

密钥放在环境变量里，勿写进共享代码。示例占位符需要替换成控制台颁发的有效凭证：

```bash
export ACE_ENGINE_ACCESS_KEY_ID="your-key-id"
export ACE_ENGINE_ACCESS_KEY_SECRET="your-key-secret"
```

Windows PowerShell：

```powershell
$env:ACE_ENGINE_ACCESS_KEY_ID="your-key-id"
$env:ACE_ENGINE_ACCESS_KEY_SECRET="your-key-secret"
```

```python
import os
from ace_engine import AceClient

with AceClient(
    access_key_id=os.environ["ACE_ENGINE_ACCESS_KEY_ID"],
    access_key_secret=os.environ["ACE_ENGINE_ACCESS_KEY_SECRET"],
    raise_for_errors=True,
) as client:
    response = client.mnet("photo.png")
    print(response["data"])  # 保留后端原始模型字段
    print(response["meta"])  # requestId、assetId、costCents、durationMs、replayed 等
```

默认服务为 `https://ace-aesthetics.cn`，接口前缀为 `/ibt`。`base_url` 也接受 `https://ace-aesthetics.cn/ibt`，不会重复拼接前缀。自建网关可以配置 `base_url` 和 `api_prefix`；只有直接连接不带统一前缀的网关时才使用 `api_prefix=""`。

旧的三参数构造 `AceClient(base_url, access_key_id, sign)` 继续可用，`sign` 是 `access_key_secret` 的兼容名称。两者同时传入时必须一致。`from ace_engine import Client` 也是同一客户端的别名。

## 上传一次，调用多个模型

下面使用 `client` 的片段应放在上面的 `with AceClient(...) as client:` 代码块内；离开代码块后连接已关闭。

```python
uploaded = client.upload_asset("photo.png")
asset_id = uploaded["data"]["assetId"]

mnet_key = client.new_idempotency_key()
response = client.mnet(asset_id=asset_id, idempotency_key=mnet_key)

# 新的模型调用意图使用新的幂等键
icaa_key = client.new_idempotency_key()
response = client.icaa17k(asset_id=asset_id, idempotency_key=icaa_key)

# 检查资源 / 查询已经提交的调用，不重新执行模型
asset = client.get_asset(asset_id)
status = client.get_inference(response["meta"]["requestId"])
```

`client.infer("mnet", asset_id, idempotency_key=...)` 和 `client.infer("icaa17k", ...)` 提供相同的底层入口。`mnet("photo.png")`、`icaa17k("photo.png")` 自动先上传再调用。

`import_asset(image_url)` 将网址交给服务端的允许来源检查；SDK 不下载任意网址，也不绕过后端来源限制。资源属于凭证对应的用户/团队，会按服务端保留策略过期；不能假定资源永久有效。

### 幂等、错误和计费

一次逻辑调用使用一个幂等键，网络超时或响应丢失后的恢复必须沿用原键。不同模型或不同图片使用新键。

```python
from ace_engine import AceError

key = client.new_idempotency_key()  # 调用前由业务持久化保存 key 和 asset_id
try:
    response = client.infer("mnet", asset_id, idempotency_key=key)
except AceError as error:
    print(error.code, error.request_id, error.idempotency_key)
    # 有 request_id 时先 get_inference(request_id) 查看 RUNNING / SETTLING / SUCCEEDED / FAILED。
    # 状态允许恢复时，再使用同一个模型、asset_id、key 调用 infer。
    # 不要因超时直接换一个新 key。
```

SDK **不自动重试模型 POST，不在错误后自动换旧接口重发**。MNet / ICAA 的服务端负责幂等、结算和余额检查；SDK 透传其 `costCents` 等实际字段，不估算费用、不伪造结果。`replayed=True` 表示服务端返回此前调用的结果，不是一次新的计费意图。

默认 `raise_for_errors=False`，兼容 0.1 的字典返回方式，调用方应检查 `code` / `success`。HTTP 和业务错误保留原始业务码、说明、请求编号和 HTTP 状态（`httpStatus`）。本地或网络错误使用 `errorType` 区分。

网络/协议异常可能带 `outcomeUnknown=True`：这表示客户端不能确认提交结果，不能据此推断模型未运行或未扣款。错误中的 `meta` 保留可用的 `assetId`、`idempotencyKey`、`taskId` 等恢复信息。密钥和令牌会从 SDK 返回的错误中脱敏；SDK 不打印请求或凭证，不跟随重定向发送凭证。

`raise_for_errors=True` 会抛出 `AceError`，其 `.response` 保留相同的错误字典。响应数据及费用字段以实际部署版本为准。

## IQA 异步评估

```python
# 一张或多张图片；默认等待完成
response = client.iqa(
    ["photo1.png", "photo2.jpg"],
    selections=["sharpness", "exposure", "contrast", "noise"],
    wait_timeout=300,
)
print(response["data"]["status"])
print(response["data"].get("result"))
```

图片每任务最多 50 张，视频每任务 1 个。图片单文件上限 20 MiB，视频 100 MiB；还受服务端实际配额限制。支持的指标为：`sharpness`、`color_accuracy`、`saturation`、`exposure`、`contrast`、`noise`、`holistic`、`overall_iqa`。`holistic` 需要至少一项基础指标；视频不支持 `overall_iqa`。

异步提交、查询和取消：

```python
asset = client.upload_iqa_asset("clip.mp4", kind="video")
asset_ids = [asset["data"]["assetId"]]
key = client.new_idempotency_key()
created = client.create_iqa_task(
    asset_ids, kind="video", selections=["exposure"], idempotency_key=key,
)
task_id = created["data"]["taskId"]

response = client.get_iqa_task(task_id)
response = client.wait_iqa_task(task_id, wait_timeout=600, poll_interval=2)
# client.cancel_iqa_task(task_id)  # 只有显式调用才请求取消
# client.list_iqa_tasks()
```

也可以 `client.iqa("photo.png", selections=["exposure"], wait=False)`，返回已创建的任务。`wait_timeout` 只限制客户端等待，超时不会自动取消、重建或重新扣费；保存错误 `meta.taskId` 后继续查询。

`SUCCEEDED` 是完成，`PARTIAL` 表示部分结果可用（需要检查任务里的 errors），`FAILED` / `CANCELLED` 在等待接口中作为错误返回。查询接口保留服务端原始状态。等待网络中断后继续查询原任务，不要重新上传并创建另一个任务。若创建响应丢失，应使用原 `asset_ids`、指标、kind 和幂等键恢复；IQA 重传文件会产生新资源 ID，不能假定与原任务等价。

MNet/ICAA 的资源与 IQA 的资源是不同接口管理的资源，不能混用 ID。IQA 输出可能包含短期签名图片/CSV/视频链接；保留签名参数，失效后重新查询任务，SDK 不向这些链接转发账户凭证。

`get_iqa_config()` 读取配置；`configure_iqa(config)` 显式提交服务端要求的完整权重/阈值对象。`iqa()` 不会暗中修改账户默认设置，也不支持旧网页中曾出现但服务端并无对应参数的 `weights={...}` 用法。

## 兼容的单项文件接口

以下方法接受本地图片，继续调用对应的 `/api/file/...` 接口：

| 方法 | 用途 |
| --- | --- |
| `sharpness(path)` | 清晰度 |
| `color(path)` | 色彩 |
| `contrast(path)` | 对比度 |
| `noise(path)` | 噪声 |
| `exposure(path)` | 曝光 |
| `holistic(path)` | 综合质量 |
| `evaluate_all(path)` | 服务端定义的综合评估 |
| `overall_iqa(path)` | 高分辨率整体质量 |
| `roc4mllm(path)` | 多模态评价 |
| `physique(path)` / `paa(path)` | 体态评价 |
| `human(path)` | 人像评价 |

这些接口使用 API-Key 表单鉴权，保留服务端各自的数据字段，不统一捏造成 `{score, level}`。实际可用性取决于部署的模型服务、凭证权限和余额。

MNet / ICAA 默认走新资源接口；只有明确连接旧版服务时才使用 `client.mnet(path, legacy=True)` 或 `client.icaa17k(path, legacy=True)`。普通单项文件接口没有统一幂等保障，超时后不能盲目重发；SDK 不自动重试。

## 图像和视频输出

```python
from ace_engine import BinaryResult

result = client.creative_crop("photo.jpg")
if isinstance(result, BinaryResult):
    result.save("crop.jpg")  # 默认拒绝覆盖已有文件

# 返回 BinaryResult，保留真实 Content-Type
result = client.acellm("photo.jpg", selections=["exposure"])
result = client.highlight("clip.mp4", query="a person running")

# JSON 响应
result = client.videomamba("clip.mp4", query="a person running")
```

二进制成功返回 `BinaryResult(content, content_type, request_id)`；失败仍按统一错误机制处理，不把 JSON 报错写成图片或视频。内容在内存中，只有显式 `.save()` 才写文件；覆盖需要 `overwrite=True`。

## 网站登录令牌

已有有效普通用户 JWT 时，可使用 `AceClient(token=token)` 访问新资源、模型调用和正式 IQA 任务接口。SDK 不负责登录、验证码或刷新令牌。API-Key 与 JWT 必须选择一种，不能混传；旧的单项文件接口需要 API-Key，不自动切换鉴权身份。

## 命令行示例与验证

```bash
python test_my_sdk.py photo.png --model mnet
python test_my_sdk.py photo.png --model icaa17k --idempotency-key your-persisted-key
python test_my_sdk.py photo.png --model iqa --selections exposure noise

python -m unittest discover -s tests -v
python -m build
```

`ACE_ENGINE_BASE_URL`、`ACE_ENGINE_API_PREFIX`、`ACE_ENGINE_ACCESS_KEY_ID`、`ACE_ENGINE_ACCESS_KEY_SECRET`（兼容 `ACE_ENGINE_SIGN`）及 `ACE_ENGINE_TOKEN` 可供示例程序使用。测试使用隔离的本机 HTTP 服务，不依赖真实密钥、不执行模型、不产生费用。实际联调需另用测试账号核对模型、状态和账单，不能用传输测试代替真实验证。
