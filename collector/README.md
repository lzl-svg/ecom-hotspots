# 采集器说明

全免费数据源（已实测可用）：

- 类目树：`/api/v4/pages/get_category_tree`（Shopee 印尼 / 马来 / 越南 三个站点均可用）
- 搜索联想词：`/api/v4/search/search_hint?keyword=...`（反映买家真实搜索需求）

运行方式：

```bash
python collector/run.py      # 采集并入库
python collector/export.py   # 生成前端 JSON
```

数据存于 `data/ecommerce.db`，前端数据导出到 `web/data/`。
