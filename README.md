# 三角洲皮肤市场邮件监控

这个仓库通过 GitHub Actions 每 20 分钟截取一次以下两个页面，并将图片发送到 QQ 邮箱：

- T0/T1
- 三倍

## 配置方法

1. 在 GitHub 新建一个仓库，建议名称为 `delta-market-monitor`。
2. 将本目录中的全部文件上传到仓库，必须保留 `.github/workflows/market-monitor.yml` 的完整目录结构。
3. 打开仓库的 **Settings**。
4. 在左侧选择 **Secrets and variables → Actions**。
5. 点击 **New repository secret**，添加：
   - 名称：`QQ_EMAIL`，值：你的完整 QQ 邮箱地址。
   - 名称：`QQ_SMTP_AUTH_CODE`，值：QQ 邮箱 SMTP 授权码，不是 QQ 密码。
   - 名称：`SITE_USERNAME`，值：监控网站登录账号。
   - 名称：`SITE_PASSWORD`，值：监控网站登录密码。
6. 打开仓库的 **Actions** 页面，选择 **Market screenshot email**。
7. 点击 **Run workflow** 手动运行一次。
8. 收到带有两张截图的测试邮件后，无需再操作，定时任务会在每小时第 7、27、47 分钟自动执行。

## 安全说明

- 不要把邮箱授权码直接写进任何代码文件。
- 仓库只需要默认的只读内容权限。
- 不要给不可信的人仓库写入权限，因为具有写权限的人可以修改工作流来使用仓库 Secrets。
- 如果授权码泄露，请立即在 QQ 邮箱撤销并生成新授权码，然后更新 `QQ_SMTP_AUTH_CODE`。

## 注意

GitHub 的定时任务不是秒级调度，高负载时可能延迟。当前设置避开了整点，在每小时第 7、27、47 分钟运行。

