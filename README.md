# ACEngine Client SDK

ACEngine Client SDK 是一个用于调用 AceEngine 图像质量评价服务的 Python 客户端。它会将本地图片上传到远程 AceEngine API，并返回对应算法的评分结果。

## 安装

从 GitHub 仓库安装：

```bash
pip install git+https://github.com/YuqiPlus/ACEngine-Client.git
```

本地开发安装：

```bash
pip install -e .
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