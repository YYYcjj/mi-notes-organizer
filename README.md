# 📝 小米笔记内容整理工具

> 导出 → 清洗 → 分类 → **云端网页浏览**

## 两种使用方式

### 🌐 方式一：启动 Web 服务（推荐）

```bash
git clone https://github.com/YYYcjj/mi-notes-organizer.git
cd mi-notes-organizer
pip install -e .

# 把导出的笔记放到 data/ 目录，然后：
minotes serve data --port 8080
```

浏览器打开 `http://localhost:8080`，即可**在线浏览、搜索、按分类筛选**所有笔记。

支持深色主题、移动端适配、Markdown 渲染。

### 💻 方式二：本地 CLI 整理

```bash
# 一键整理：解析 + 清洗 + 分类 + 生成 Markdown
minotes organize /path/to/notes.zip -o ./my-notes

# 分步操作
minotes parse /path/to/notes          # 预览
minotes markdown /path/to/notes       # 只生成 Markdown
minotes site /path/to/notes           # 只生成静态站点
```

## 功能

| 功能 | 说明 |
|------|------|
| 🔍 多格式解析 | ZIP / JSON (mi-note-export) / Markdown 目录 |
| 🧹 内容清洗 | HTML→Markdown、去空行、格式修复 |
| 🏷️ 智能分类 | 关键词自动归类（技术/交易/生活/工作/学习/随笔） |
| 📊 标签提取 | jieba 分词自动提取关键词 |
| 🌐 Web 服务 | FastAPI 后端，浏览器直接浏览笔记 |
| 📄 Markdown输出 | 按分类归档，YAML frontmatter |

## 输出结构

```
output/
├── README.md              # 笔记索引
├── 交易/
│   ├── DOGE合约复盘.md
│   └── SRSI策略优化.md
├── 技术/
│   └── ...
└── site/
    └── index.html
```

## 自定义分类

编辑 `src/config.py`：

```python
category_keywords = {
    "技术": ["代码", "编程", "Python", ...],
    "交易": ["交易", "合约", "做空", "止损", ...],
    # 添加你自己的分类
}
```

## 部署

```bash
# CloudStudio / 任意服务器
pip install -e .
minotes serve data --host 0.0.0.0 --port 8080
```

## License

MIT
