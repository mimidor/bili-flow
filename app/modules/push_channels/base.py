from abc import ABC, abstractmethod
from typing import Dict, Any, List


class BaseChannel(ABC):
    """推送渠道基类"""

    channel_name: str = ""

    @abstractmethod
    def send(self, content_data: Dict[str, Any]) -> bool:
        """
        发送内容

        Args:
            content_data: 内容数据
                - type: "video" | "dynamic"
                - title/text: 标题或文本
                - uploader_name: 作者/UP主名称
                - summary: 摘要（视频或动态总结）
                - details: Markdown 详细内容
                - doc_url: 飞书总结文档链接
                - url: 链接
                - images: 本地图片路径列表
                - image_urls: 图片URL列表
                - pub_time: 发布时间字符串
                - timestamp: 发布时间戳或时间对象
                - tags: 标签列表
                - stocks: 股票列表

        Returns:
            bool: 是否发送成功
        """
        pass

    def send_text(self, text: str) -> bool:
        """发送纯文本（可选实现）"""
        raise NotImplementedError

    def batch_send(self, content_list: List[Dict[str, Any]]) -> bool:
        """批量发送（可选实现）"""
        raise NotImplementedError
