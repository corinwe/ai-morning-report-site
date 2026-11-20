# 云车热点 · 下游读取说明

> 这是 AI 晨报的“云车热点”数据目录。云竹/其他下游 Agent 直接读这里，不要再去解析晨报正文。

## 文件位置

| 用途 | 路径 |
|:--|:--|
| 结构化 JSON（推荐程序读取） | `/root/ai-morning-report-site/data/hotspots/latest.json` |
| 最新 Markdown 片段（推荐直接引用） | `/root/ai-morning-report-site/reports/_hotspots_latest.md` |
| 按日期归档 JSON | `/root/ai-morning-report-site/data/hotspots/YYYY-MM-DD.json` |
| 按日期归档 Markdown | `/root/ai-morning-report-site/reports/_hotspots_YYYY-MM-DD.md` |
| 已合入的完整晨报 | `/root/ai-morning-report-site/reports/YYYY-MM-DD.md` 的 `## 三、云车热点（AI/数字化科技）` |

## JSON 字段

```json
{
  "date": "2026-11-20",
  "generated_at": "2026-11-20T23:15:15+08:00",
  "window_hours": 36,
  "source": "Hacker News Algolia (past window)",
  "items": [
    {
      "title": "...",
      "url": "原文链接",
      "hn_url": "HN 讨论链接",
      "source": "Hacker News",
      "source_type": "community",
      "points": 522,
      "comments": 247,
      "published_at": "2026-11-19",
      "category": "研究"
    }
  ]
}
```

## 位置约定

在 AI 晨报里，云车热点固定放在：

```
## 三、云车热点（AI/数字化科技）
```

也就是「二、模型与应用」之后、「四、创业与商业」之前。

## 下游使用规则

1. 引用时保留 `title / url / hn_url / points / comments / published_at`。
2. 不要把 `points` 写成“今日排名”；它只是 HN 分数，不是全网热度。
3. 热点只作为选题线索；写文章前仍要读原文，不能只凭标题写。
4. 资本/政策/人物/硬件类已被上游排除；下游不要把它们重新加回来。
