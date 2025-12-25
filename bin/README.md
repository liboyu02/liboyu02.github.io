# Google Scholar Publications Update

本目录包含自动抓取和更新 Google Scholar 出版物的工具。

## 快速开始

### 1. 手动更新 BibTeX（推荐）

如果你已经有从 Google Scholar 导出的 BibTeX：

1. 将内容粘贴到 `_bibliography/papers.bib`
2. 运行缩略图下载脚本：
   ```bash
   .venv/bin/python bin/add_previews.py
   ```

### 2. 自动抓取（需要 API Key）

由于 Google Scholar 反爬限制，推荐使用 SerpAPI：

```bash
# 设置 API Key
export SERPAPI_API_KEY="your-key-here"

# 抓取并更新
.venv/bin/python bin/fetch_scholar.py \
  --user mo4TKqkAAAAJ \
  --thumbnails \
  --max 50
```

## 工具说明

### `bin/fetch_scholar.py`

完整的 Google Scholar 抓取工具，支持：
- 按用户 ID 抓取所有出版物
- 自动生成 BibTeX 并写入 `_bibliography/papers.bib`
- 可选下载缩略图到 `assets/img/publication_preview/`
- 自动备份原始 bib 文件

**参数：**
- `--user`: Scholar 用户 ID（必需）
- `--max`: 最多抓取论文数（可选）
- `--thumbnails`: 下载缩略图（可选）
- `--serpapi-key`: SerpAPI Key（可选，或使用环境变量 `SERPAPI_API_KEY`）

### `bin/add_previews.py`

为现有 `papers.bib` 中的论文下载缩略图：
- 扫描 bib 条目的 `url` 或 `doi` 字段
- 尝试从页面抓取 og:image 元数据
- 下载图片到 `assets/img/publication_preview/`
- 自动添加 `preview` 字段到 bib 条目

**使用：**
```bash
.venv/bin/python bin/add_previews.py
```

## 目前状态

已为以下5篇论文配置好 BibTeX 和缩略图：
1. ✅ Dense Metric Depth Estimation (NeurIPS 2025)
2. ✅ EventAid (IEEE TPAMI 2025) - 真实缩略图
3. ✅ Monochromatic Event Deblurring (ICCV 2025W) - 占位图
4. ✅ EvDiG (CVPR 2024) - 占位图
5. ✅ Coherent Event Enhancement (ICCV 2023) - 占位图

所有缩略图位于：`assets/img/publication_preview/`

## 自定义缩略图

如需替换占位图为真实论文图片：
1. 准备图片（推荐 400x300 或类似比例）
2. 命名为 `<bibkey>.jpg` 或 `.png`
3. 放入 `assets/img/publication_preview/`
4. 确保 `papers.bib` 中对应条目有 `preview = {publication_preview/<bibkey>.jpg}`

## 依赖

所有依赖已在 `requirements.txt` 中：
- `scholarly`: Google Scholar 抓取
- `bibtexparser`: BibTeX 解析
- `requests`, `beautifulsoup4`: 网页抓取
- `Pillow`: 图片生成

安装：
```bash
.venv/bin/python -m pip install -r requirements.txt
```
