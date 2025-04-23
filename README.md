# Pixiv收藏下载器

一个用于自动下载并同步Pixiv收藏图片的Python工具。支持定时任务、断点续传、失败重试、多图下载等功能。

## ✨ 特性

- 🔄 **定时同步**：自动定期检查并下载新收藏的图片
- 🖼️ **多图支持**：自动为多图作品创建单独文件夹
- 🔁 **断点续传**：记录下载历史，支持从中断处继续
- 🔔 **通知提醒**：支持Webhook通知（如企业微信、钉钉等）
- 🚀 **失败重试**：自动重试下载失败的项目
- 🌐 **镜像支持**：可配置Pixiv镜像域名加速下载
- 🔌 **网络选项**：支持ByPassSniApi免代理模式

## 🚀 快速开始

### 前提条件

- Python 3.6+
- Pixiv账号及刷新令牌（Refresh Token）

### 安装

1. 克隆仓库或直接下载[发布页](https://github.com/SanaeMio/PixivBookmarkDownloader/releases)的zip压缩包：

```bash
git clone https://github.com/SanaeMio/PixivBookmarkDownloader.git
cd PixivBookmarkDownloader
```

2. 安装依赖：

```bash
pip install -r requirements.txt
```

### 配置选项

在项目根目录修改`.env`文件并配置参数

### 启动

```bash
python pixiv_bookmark_downloader.py
```
### 使用批处理文件启动（Windows）

Windows用户可以直接双击`start.bat`文件启动程序


## 📝 Webhook配置

支持自定义Webhook通知，在`webhook_config.json`中配置通知模板。支持以下变量：

- `{total}`: 总计处理图片数
- `{success}`: 成功下载数
- `{fail}`: 失败数
- `{time}`: 当前时间

示例：
```json
{
  "title": "收藏夹增量下载完成，新增{success}张",
  "content": "🚀 本次共处理{total}张图片，✅ 成功{success}张，❌ 失败{fail}张\n⏰ 推送时间：{time}"
}
```

## 📋 常见问题

**Q: 如何获取Pixiv的刷新令牌？**  
A: 可通过第三方工具如[pixiv-auth](https://github.com/upbit/pixivpy/issues/158)获取。

**Q: 下载失败怎么办？**  
A: 程序会自动记录失败项并在下次运行时重试。也可检查网络连接。

**Q: 为什么需要设置镜像域名？**  
A: Pixiv原始域名在某些地区可能无法直接访问，设置镜像可解决此问题。

## 📜 许可证

本项目采用MIT许可证。详见[LICENSE](LICENSE)文件。

---

如有问题或建议，欢迎提交Issue或Pull Request！
