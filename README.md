# ACEngine Client SDK

ACEngine Client SDK 是一个用于调用 AceEngine 图像质量评价服务的 Python 客户端。它会将本地图片上传到远程 AceEngine API，并返回对应算法的评分结果。

## 安装

从 GitHub 仓库安装：

```bash
pip install git+https://github.com/YuqiPlus/ACEngine-Client.git
```

如果 HTTPS 连接 GitHub 失败，可以改用 SSH 安装：

```bash
pip install git+ssh://git@github.com/YuqiPlus/ACEngine-Client.git
```

也可以指定 `main` 分支：

```bash
pip install git+ssh://git@github.com/YuqiPlus/ACEngine-Client.git@main
```

本地开发安装：

```bash
pip install -e .
```

## 安装失败排查

如果出现类似下面的报错：

```text
fatal: unable to access 'https://github.com/...': OpenSSL SSL_connect: SSL_ERROR_SYSCALL in connection to github.com:443
```

这通常是本机网络、代理、证书或 GitHub HTTPS 连接问题，不是 SDK 包代码问题。可以优先尝试 SSH 安装：

```bash
pip install git+ssh://git@github.com/YuqiPlus/ACEngine-Client.git
```

如果需要确认 SSH 是否可用：

```bash
ssh -T git@github.com
```

如果必须使用 HTTPS，并且本机需要代理，请先配置代理后再安装。PowerShell 示例：

```powershell
$env:HTTPS_PROXY="http://127.0.0.1:7890"
$env:HTTP_PROXY="http://127.0.0.1:7890"
pip install git+https://github.com/YuqiPlus/ACEngine-Client.git
```

其中 `7890` 需要替换成本机实际代理端口。

## 卸载

无论是从 GitHub 安装，还是本地开发安装，卸载时都使用包名 `ace-engine-sdk`：

```bash
pip uninstall ace-engine-sdk
```

如果不确定是否已经安装，可以先查看：

```bash
pip show ace-engine-sdk
```

## 快速开始

```python
from ace_engine import AceClient

client = AceClient(
    base_url="https://ace-aesthetics.cn/",
    access_key_id="your-access-key-id",
    sign="your-sign",
)

result = client.evaluate_all("./test.jpg")
print(result)
client.close()
```

## 支持的接口

- `mnet(image_path)`: 美学评分
- `sharpness(image_path)`: 清晰度检测
- `icaa17k(image_path)`: 综合评分
- `color(image_path)`: 色彩质量评估
- `contrast(image_path)`: 对比度评估
- `evaluate_all(image_path)`: 整体观感评分
- `noise(image_path)`: 噪声检测
- `roc4mllm(image_path)`: 多模态模型相关评估
- `physique(image_path)`: 身体/构图评估
- `human(image_path)`: 人像质量评估

## 环境变量示例

为了避免把密钥写进代码，可以使用环境变量：

```powershell
$env:ACE_ENGINE_BASE_URL="https://ace-aesthetics.cn/"
$env:ACE_ENGINE_ACCESS_KEY_ID="your-access-key-id"
$env:ACE_ENGINE_SIGN="your-sign"
```

然后运行示例：

```bash
python test_my_sdk.py ./test.jpg
```