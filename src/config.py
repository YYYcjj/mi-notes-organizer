"""核心配置"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class OrganizerConfig:
    """整理器配置"""

    # 输入来源
    input_dir: Path = Path("data/input")
    # 输出目录
    output_dir: Path = Path("data/output")
    # 静态站点输出目录
    site_dir: Path = Path("data/site")

    # 分类规则
    auto_categorize: bool = True
    category_keywords: dict = field(default_factory=lambda: {
        "技术": ["代码", "编程", "Python", "JavaScript", "API", "数据库", "服务器", "Linux",
                 "Git", "Docker", "算法", "前端", "后端", "开源", "bug", "debug"],
        "交易": ["交易", "合约", "做多", "做空", "止损", "止盈", "K线", "趋势", "指标",
                 "BTC", "ETH", "DOGE", "ORDI", "APT", "SRSI", "MAE", "MFE"],
        "生活": ["旅行", "美食", "健身", "健康", "家居", "购物", "日常"],
        "工作": ["项目", "需求", "会议", "周报", "计划", "OKR", "复盘"],
        "学习": ["笔记", "教程", "读书", "课程", "考试", "学习"],
        "随笔": ["想法", "日记", "感悟", "记录"],
    })

    # 内容清洗
    remove_empty_lines: bool = True
    normalize_whitespace: bool = True
    extract_frontmatter: bool = True

    # 站点生成
    site_title: str = "我的笔记"
    site_description: str = "小米笔记整理知识库"
    items_per_page: int = 20

    # 搜索
    enable_search: bool = True
    search_index_path: Optional[Path] = None


DEFAULT_CONFIG = OrganizerConfig()
