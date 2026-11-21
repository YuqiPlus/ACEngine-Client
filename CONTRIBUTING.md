# 开发与验证

本文面向修改 SDK 源码的贡献者。使用已发布 SDK 的安装方法和调用示例见 [README](README.md)，版本发布流程见 [PUBLISHING](PUBLISHING.md)。

## 安装源码

```bash
git clone https://github.com/YuqiPlus/ACEngine-Client.git
cd ACEngine-Client
python -m venv .venv
```

Linux / macOS 激活环境：

```bash
source .venv/bin/activate
```

Windows PowerShell 激活环境：

```powershell
.venv\Scripts\Activate.ps1
```

安装可编辑版本及构建工具：

```bash
python -m pip install -e .
python -m pip install build twine
```

代理和证书由开发者本机配置，不要在 SDK 中固定代理地址或关闭 HTTPS 证书验证。

## 运行测试

```bash
python -m unittest discover -s tests -v
```

协议测试使用隔离的本机 HTTP 服务，不需要业务 API-Key，不调用实际模型，也不产生调用费用。

## 真实服务联调

以下脚本位于源码仓库，不随 SDK 的 wheel 安装。

配置环境变量：

```bash
export ACE_ENGINE_ACCESS_KEY_ID="your-key-id"
export ACE_ENGINE_ACCESS_KEY_SECRET="your-key-secret"
```

Windows PowerShell：

```powershell
$env:ACE_ENGINE_ACCESS_KEY_ID="your-key-id"
$env:ACE_ENGINE_ACCESS_KEY_SECRET="your-key-secret"
```

调用真实服务：

```bash
python test_my_sdk.py photo.png --model mnet
python test_my_sdk.py photo.png --model icaa17k --idempotency-key your-persisted-key
python test_my_sdk.py photo.png --model iqa --selections exposure noise
```

脚本还支持 `ACE_ENGINE_BASE_URL`、`ACE_ENGINE_API_PREFIX`、`ACE_ENGINE_TOKEN`，以及兼容的 `ACE_ENGINE_SIGN`。API-Key 和登录令牌选择一种鉴权方式。

联调会执行模型并按服务端规则计费，请使用专用测试账号核对响应、任务状态和账单。协议测试通过不能替代真实模型验证。

## 检查发行包

```bash
python -m build
python -m twine check --strict dist/*
```

`setup.py` 将 README 写入发行包的项目介绍，因此 README 应面向通过 pip 安装的使用者。源码安装、仓库脚本及测试步骤放在本文，上传和发布操作放在 PUBLISHING 中。
