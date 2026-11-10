# 发布 ace-engine-sdk

本仓库通过 `.github/workflows/publish.yml` 手动发布。推送代码不会上传发行包；只有在 GitHub Actions 手动运行发布流程后，才会尝试创建 PyPI 项目并上传。

## 首次配置

1. 在 PyPI 验证注册邮箱，并启用双重验证。
2. 打开 https://pypi.org/manage/account/publishing/ ，在新增待创建项目的发布者（pending publisher）中选择 GitHub。
3. 填写以下内容并添加：

| 字段 | 值 |
| --- | --- |
| PyPI Project Name | `ace-engine-sdk` |
| Owner / GitHub owner | `YuqiPlus` |
| Repository name | `ACEngine-Client` |
| Workflow name | `publish.yml` |
| Environment name | `pypi` |

这里的 Owner 是 GitHub 仓库所有者，不是 PyPI 用户名。Workflow name 只填写文件名。配置 pending publisher 并不会立即发布，也不会预占包名；首次成功上传时才创建项目。

4. 在 GitHub 的 `YuqiPlus/ACEngine-Client` 仓库设置 → Environments 中建立 `pypi` 环境。其名称须与上表一致；可将允许发布的分支限制为 `main`。

这条方式使用 GitHub 的短期身份认证，不需要把 PyPI 密码或长期上传 Token 放进仓库。

## 获得推送与发布授权后

1. 核对版本号、CHANGELOG 与构建内容，确保 SDK 和 `.github/workflows/publish.yml` 已配套提交到 `main`。
2. 在 GitHub Actions 选择 **Publish to PyPI** → **Run workflow**，分支选择 `main`，版本填写 `0.2.0`。
3. 流程在固定的 Ubuntu 24.04 环境测试 Python 3.9、3.12、3.14，避免 `ubuntu-latest` 升级导致旧版 Python 无法安装；构建 wheel 与源码包，并严格检查元数据。指定版本必须与已安装包版本、`ace_engine.__version__` 一致。
4. 校验全部通过后，单独的发布任务通过 `pypi` 环境上传到正式 PyPI。工作流只接受手动触发，普通 push 和 PR 不会发布；在其他分支手动运行也不会进入发布。
5. 打开 https://pypi.org/project/ace-engine-sdk/0.2.0/ ，并在干净环境执行：

```bash
python -m pip install --index-url https://pypi.org/simple ace-engine-sdk==0.2.0
python -c "from ace_engine import AceClient, __version__; print(__version__)"
```

6. 确认安装可用后，再更新网站的待发布标记和安装说明。网站发布另行安排，SDK 上传不会部署网站或模型服务。

若修改工作流后重新发布，请从 `main` 点击 **Run workflow** 创建新运行。旧失败记录的 **Re-run jobs** 使用原提交的工作流，不会采用后续修复。

## 本地发布前检查

```bash
python -m unittest discover -s tests -v
python -m build
python -m twine check --strict dist/ace_engine_sdk-0.2.0*
```

测试不调用实际模型，不需要业务 API-Key。发布校验通过不等于已经上传；只有正式上传成功后，别人才能通过 `pip install ace-engine-sdk` 获取发行包。后续有代码变化时递增版本并重新构建，不能覆盖已经上传的同名文件。

官方说明：https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/
