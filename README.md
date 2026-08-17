# 机会画报 · Opportunity Gazette

每日机会雷达的精品阅读站。内容先经过统一质量关，再生成静态页面并发布到 GitHub Pages。

- 正式网站：https://hsbrxlb.github.io/opportunity-gazette/
- 公开仓库：https://github.com/hsbrxlb/opportunity-gazette
- 更新方式：现有“每日机会雷达”自动任务每天 13:00 运行，默认处理前一天。

网站只发布“封面级”和“编辑精选”，并把市场机会与实战案例分开。当天没有精品时会保留日期状态页，不用弱信号填版面。`noindex` 只降低被搜索引擎收录的概率，网站本身仍是公开网址。

## 本地检查

```bash
npm install
npm run audit:content
npm run build
npm run audit:secrets
```

安全发布由本机的 `publish_opportunity_gazette` 入口负责：只提交通过审核的数据和封面，不强制推送；构建或推送失败时保留上一版网站。

网页版迁移链路使用公开数据仓库 [`hsbrxlb/opportunity-gazette-pipeline`](https://github.com/hsbrxlb/opportunity-gazette-pipeline)：GitHub Actions 先收集候选，普通 ChatGPT 定时任务精审并写入 `reviewed/YYYY-MM-DD.json`，本仓库在 13:40 合并新条目、保留既有条目、校验并部署。没有 reviewed 文件时不会改变上一版网站。

历史审核账本保存在本机日报目录，不进入公共仓库。公开仓库只包含通过审核的结构化条目和安全统计。
