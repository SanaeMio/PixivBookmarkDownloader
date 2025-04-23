import os
import json
import time
import random
import schedule
import logging
import requests
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from pixivpy3 import ByPassSniApi,AppPixivAPI

load_dotenv()

class PixivDownloader:
    def __init__(self):
        # 初始化日志系统（最先执行）
        self._init_logger()

        # 初始化配置项
        self.config = {
            "user_id": os.getenv("USER_ID"),
            "download_path": Path(os.getenv("DOWNLOAD_PATH", "./downloads")),
            "refresh_token": os.getenv("REFRESH_TOKEN"),
            "interval": int(os.getenv("INTERVAL_MINUTES", 60)),
            "webhook_url": os.getenv("WEBHOOK_URL"),
            "mirror_domain": os.getenv("MIRROR_DOMAIN", "i.pixiv.cat"),
            "api_interval": float(os.getenv("API_INTERVAL", 5)),
            "dl_interval": float(os.getenv("DOWNLOAD_INTERVAL", 3)),
            "jitter": float(os.getenv("JITTER", 1)),
            "record_file": Path(__file__).parent / "downloaded.json",
            "debug": os.getenv("DEBUG_MODE", "false").lower() == "true",
            "create_folder": os.getenv("CREATE_FOLDER_FOR_MULTI", "true").lower() == "true",
            "start_after": os.getenv("START_AFTER", ""), 
            "use_bypass_api": os.getenv("USE_BYPASS_API", "false").lower() == "true", 
            "downloaded": set(),
            "failed": dict(),
            "webhook_template": self._load_webhook_template()
        }

        # 初始化API客户端
        if self.config["use_bypass_api"]:
            self.logger.info("使用ByPassSniApi模式（免代理）")
            self.api = ByPassSniApi()
            self.api.require_appapi_hosts()
        else:
            self.logger.info("使用AppPixivAPI模式")
            self.api = AppPixivAPI()

        # 首次检查（不加载记录）
        self.check_bookmarks(first_run=True)

    def _init_logger(self):
        """初始化日志系统"""
        logging.basicConfig(
            level=logging.DEBUG if os.getenv("DEBUG_MODE", "false").lower() == "true" else logging.INFO,
            format="[%(asctime)s] %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info("日志系统初始化完成")

    def _load_webhook_template(self):
        """加载Webhook模板配置"""
        template_path = Path(__file__).parent / "webhook_config.json"
        try:
            if template_path.exists():
                with open(template_path, encoding="utf-8") as f:
                    template = json.load(f)
                    self.logger.info("Webhook模板加载成功")
                    return template
            self.logger.warning("未找到Webhook模板文件，跳过通知配置")
            return {}
        except Exception as e:
            self.logger.error(f"加载Webhook模板失败: {str(e)}")
            return {}

    def _authenticate(self):
        """API认证"""
        try:
            self.logger.info("执行API认证...")
            self.api.auth(refresh_token=self.config["refresh_token"])
            self.logger.info("认证成功")
            return True
        except Exception as e:
            self.logger.error(f"认证失败: {str(e)}")
            return False

    def _load_records(self):
        """加载下载记录"""
        if self.config["record_file"].exists():
            try:
                with open(self.config["record_file"], encoding="utf-8") as f:
                    data = json.load(f)
                    self.config["downloaded"] = set(data.get("downloaded_ids", []))
                    self.config["failed"] = data.get("failed", {})
                self.logger.info(f"加载历史记录：成功{len(self.config['downloaded'])}条，失败{len(self.config['failed'])}条")
            except Exception as e:
                self.logger.error(f"加载记录文件失败: {str(e)}")
        else:
            self.logger.info("未找到历史记录文件，将创建新记录")

    def _save_records(self):
        """保存记录"""
        data = {
            "downloaded_ids": list(self.config["downloaded"]),
            "failed": self.config["failed"]
        }
        try:
            with open(self.config["record_file"], "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.logger.debug("记录文件已保存")
        except Exception as e:
            self.logger.error(f"保存记录失败: {str(e)}")

    def _get_interval(self, base_interval):
        """生成随机间隔"""
        interval = max(0.1, base_interval + random.uniform(-self.config["jitter"], self.config["jitter"]))
        return interval

    def _replace_domain(self, url):
        """动态替换域名"""
        new_url = url.replace("i.pximg.net", self.config["mirror_domain"], 1)
        return new_url

    def _send_webhook(self, success, total, failed):
        """发送Webhook通知"""
        if not self.config["webhook_url"] or not self.config["webhook_template"]:
            self.logger.debug("未配置Webhook，跳过通知")
            return

        try:
            # 准备模板数据
            template = self.config["webhook_template"].copy()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 替换占位符
            template["title"] = template.get("title", "").replace("{success}", str(success))
            template["content"] = template.get("content", "")\
                .replace("{total}", str(total))\
                .replace("{success}", str(success))\
                .replace("{fail}", str(failed))\
                .replace("{time}", now)

            self.logger.debug(f"准备发送Webhook: {template}")

            # 发送请求
            response = requests.post(
                self.config["webhook_url"],
                json=template,
                timeout=10
            )
            self.logger.info(f"Webhook通知已发送，状态码: {response.status_code}")
        except Exception as e:
            self.logger.error(f"发送Webhook失败: {str(e)}")

    def _process_failed(self):
        """处理失败记录"""
        if not self.config["failed"]:
            self.logger.debug("没有失败记录需要重试")
            return 0, 0

        self.logger.info(f"开始重试{len(self.config['failed'])}个失败作品")
        total_s, total_f = 0, 0
        retry_list = list(self.config["failed"].items())

        for illust_id, urls in retry_list:
            self.logger.info(f"开始重试作品 {illust_id} ({len(urls)}张)")
            s, f = self._download_illust(illust_id, urls, is_retry=True)
            total_s += s
            total_f += f
            time.sleep(self._get_interval(self.config["api_interval"]))

        self.logger.info(f"重试完成：成功{total_s}张，失败{total_f}张")
        return total_s, total_f

    def _download_illust(self, illust_id, urls, is_retry=False):
        """下载作品核心逻辑"""
        success = 0
        failed_urls = []

        # 确定保存路径
        save_dir = self.config["download_path"]
        if self.config["create_folder"] and len(urls) > 1:
            save_dir = save_dir / illust_id
            save_dir.mkdir(parents=True, exist_ok=True)
            self.logger.debug(f"创建多图目录: {save_dir}")

        # 下载所有图片
        for idx, url in enumerate(urls):
            ext = url.split(".")[-1].split("?")[0]
            filename = f"{illust_id}_p{idx}.{ext}"
            
            try:
                self.logger.debug(f"开始下载: {filename}")
                time.sleep(self._get_interval(self.config["dl_interval"]))
                self.api.download(url, path=save_dir, name=filename)
                success += 1
                self.logger.debug(f"下载成功: {filename}")
            except Exception as e:
                self.logger.error(f"{'重试' if is_retry else ''}下载失败 {filename}: {str(e)}")
                failed_urls.append(url)

        # 更新记录
        if success == len(urls):
            self.config["downloaded"].add(illust_id)
            if is_retry:
                del self.config["failed"][illust_id]
            self.logger.info(f"作品 {illust_id} 下载完成：成功{success}张")
        elif failed_urls:
            self.config["failed"][illust_id] = failed_urls
            if not is_retry:  # 新失败记录
                self.config["downloaded"].discard(illust_id)
            self.logger.warning(f"作品 {illust_id} 下载部分失败：成功{success}张，失败{len(failed_urls)}张")
        else:
            if is_retry:
                del self.config["failed"][illust_id]
            self.logger.error(f"作品 {illust_id} 下载全部失败")

        return success, len(urls)-success

    def check_bookmarks(self, first_run=False):
        """执行完整的检查流程"""
        if not self._authenticate():  # 每次检查前认证
            return

        self.logger.info("开始收藏检查" + ("（首次运行）" if first_run else ""))
        self._load_records()  # 检查时加载记录

        # 处理失败记录
        retry_s, retry_f = self._process_failed()
        total_s, total_f = 0, 0

        # 处理新收藏
        try:
            next_qs = None
            stop_flag = False
            start_processing = not self.config["start_after"]  # 是否开始处理

            while not stop_flag:
                time.sleep(self._get_interval(self.config["api_interval"]))

                try:
                    self.logger.debug("获取收藏列表...")
                    json_result = self.api.user_bookmarks_illust(
                        user_id=self.config["user_id"],
                        restrict="public",
                        **({"next_url": next_qs} if next_qs else {})
                    )
                    self.logger.info(f"获取到 {len(json_result.illusts)} 个作品")
                except Exception as e:
                    if "Invalid URL" in str(e):
                        self.logger.warning("分页参数失效，重置查询...")
                        next_qs = None
                        continue
                    raise

                # 处理作品
                for illust in json_result.illusts:
                    illust_id = str(illust.id)

                    # 检查是否到达起始点
                    if not start_processing:
                        if illust_id == self.config["start_after"]:
                            start_processing = True
                            self.logger.info(f"找到起始作品 {illust_id}，开始处理后续内容")
                        continue

                    # 检查是否已下载
                    if illust_id in self.config["downloaded"]:
                        self.logger.info(f"作品 {illust_id} 已下载，停止后续处理")
                        stop_flag = True
                        break

                    # 解析URL
                    try:
                        if illust.meta_pages:
                            urls = [self._replace_domain(p["image_urls"]["original"]) for p in illust.meta_pages]
                        else:
                            urls = [self._replace_domain(illust.meta_single_page["original_image_url"])]
                        self.logger.debug(f"作品 {illust_id} 解析完成，共 {len(urls)} 张图片")
                    except KeyError as e:
                        self.logger.error(f"作品 {illust_id} 数据异常: {str(e)}")
                        continue

                    # 下载作品
                    s, f = self._download_illust(illust_id, urls)
                    total_s += s
                    total_f += f

                    if f > 0:
                        stop_flag = True
                        break

                # 检查分页
                if stop_flag or not json_result.next_url:
                    break
                next_qs = json_result.next_url

            # 汇总统计
            total_s += retry_s
            total_f += retry_f
            total = total_s + total_f

            if total > 0:
                self._save_records()
                self._send_webhook(total_s, total, total_f)
                self.logger.info(f"处理完成：总计{total}张（成功{total_s}，失败{total_f}）")
            else:
                self.logger.info("没有新内容需要处理")

        except Exception as e:
            self.logger.error(f"检查过程中发生错误: {str(e)}")
        finally:
            if first_run:
                self.logger.info("首次检查完成，定时任务已启动")

    def run(self):
        """启动定时任务"""
        schedule.every(self.config["interval"]).minutes.do(self.check_bookmarks)
        self.logger.info(f"定时监控已启动，间隔：{self.config['interval']}分钟")
        
        while True:
            schedule.run_pending()
            time.sleep(1)

if __name__ == "__main__":
    try:
        downloader = PixivDownloader()
        downloader.run()
    except KeyboardInterrupt:
        print("\n程序已安全退出")
    except Exception as e:
        print(f"启动失败: {str(e)}")