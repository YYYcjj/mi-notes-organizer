# 小米笔记内容整理工具

> 📝 解析小米笔记导出文件 → 清洗格式化 → 智能分类标签 → 生成可浏览的知识库网站

## 为什么需要这个工具？

小米笔记的**导出**工具已经有不少了（[mi-note-export](https://github.com/idootop/mi-note-export)、[mi-notes-exporter](https://github.com/Horizen5/mi-notes-exporter) 等），但导出后的笔记往往是一堆零散的 Markdown 文件，缺少整理和呈现。

这个工具专注做**导出之后**的事：

| 功能 | 说明 |
|------|------|
| 🔍 多格式解析 | 支持 ZIP / JSON (mi-note-export) / Markdown 目录 |
| 🧹 内容清洗 | 去除空行、HTML转Markdown、修复格式问题 |
| 🏷️ 智能分类 | 基于关键词自动归类（技术/交易/生活/工作/学习/随笔） |
| 📊 标签提取 | jieba 分词自动提取关键词标签 |
| 📄 Markdown输出 | 按分类归档，带 YAML frontmatter |
| 🌐 静态站点 | 单文件 HTML，支持搜索/分类筛选/移动端适配 |

## 快速开始

```bash
# 1. 安装
git clone https://github.com/YYYcjj/mi-notes-organizer.git
cd mi-notes-organizer
pip install -e .

# 2. 使用
# 一键整理（解析+清洗+分类+生成 Markdown + 静态站点）
minotes organize /path/to/your/notes.zip -o ./my-notes

# 或者分步操作
minotes parse /path/to/notes          # 预览解析结果
minotes markdown /path/to/notes       # 只生成 Markdown
minotes site /path/to/notes           # 只生成静态站点
```

## 支持的输入格式

### 1. 小米笔记 ZIP 导出
直接从手机「设置 → 小米云服务 → 笔记 → 导出」获取

### 2. mi-note-export 的 notes.json
```bash
minotes organize notes.json -o ./output
```

### 3. Markdown 目录
```bash
minotes organize ./my-markdown-notes -o ./output
```

## 输出结构

```
output/
├── README.md              # 笔记索引（可 GitHub 直接浏览）
├── 技术/
│   ├── Python异步编程.md
│   └── Docker部署笔记.md
├── 交易/
│   ├── DOGE合约复盘.md
│   └── SRSI策略优化.md
├── 生活/
│   └── ...
├── 其他/
│   └── ...
└── site/
    └── index.html         # 静态站点（浏览器直接打开）
```

## 自定义分类

编辑 `src/config.py` 中的 `category_keywords`：

```python
category_keywords = {
    "技术": ["代码", "编程", "Python", "JavaScript", ...],
    "交易": ["交易", "合约", "做多", "做空", "止损", ...],
    # 添加你自己的分类...
}
```

## 项目结构

```
mi-notes-organizer/
├── src/
│   ├── cli.py            # 命令行入口
│   ├── config.py         # 配置（分类关键词等）
│   ├── models.py         # 数据模型
│   ├── parsers/          # 解析器（ZIP/JSON/Markdown）
│   ├── organizers/       # 整理器（清洗/分类/标签）
│   └── generators/       # 生成器（Markdown/静态站点）
├── tests/
├── pyproject.toml
└── README.md
```

## License

MIT
