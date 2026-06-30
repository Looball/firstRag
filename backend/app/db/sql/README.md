# Database SQL Baseline

`000_initial_schema.sql` 是当前项目尚未进入生产环境前整理出的完整 schema 基线，用于空数据库初始化。

后续数据库结构变化遵循增量 migration：

```text
000_initial_schema.sql
001_add_example_table.sql
002_add_example_column.sql
```

规则：

- 不再修改已经提交并被环境执行过的 migration 文件，除非项目仍处于明确的 rebaseline 阶段。
- 新增表、字段、索引、约束或默认值时，新增下一个编号的 SQL 文件。
- SQL 文件名使用三位递增编号和英文描述，例如 `001_create_message_tags.sql`。
- migration 内容应可在已有数据环境中安全执行，优先使用 `IF NOT EXISTS` 或显式兼容检查。
- 不从本地数据库导出 `ALTER TABLE ... OWNER TO ...` 这类绑定个人角色的语句。
