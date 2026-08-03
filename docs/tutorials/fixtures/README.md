# 教程示例素材

本目录保存小型、确定性、可清理的 FirstRAG 教程素材。所有正文都为本仓库专门编写的虚构内容，不包含私人数据、第三方文章、真实账号或可用凭据；这些仓库自编素材采用根目录 [`LICENSE`](../../../LICENSE) 中的 Apache License 2.0，版权归属见 [`NOTICE`](../../../NOTICE)。

## 素材清单

| 文件 | 类型 | 用途 | 来源 |
| --- | --- | --- | --- |
| [`credential_free_retrieval.txt`](credential_free_retrieval.txt) | TXT retrieval fixture | credential-free full-stack E2E 和入门检索练习。 | FirstRAG 项目自编合成文本。 |
| [`fictional_station.md`](fictional_station.md) | Markdown knowledge fixture | 观察 Markdown 标题、列表、重复查询词和 sources。 | FirstRAG 项目自编虚构资料。 |
| [`ocr_ground_truth.txt`](ocr_ground_truth.txt) | OCR ground truth | 生成不含第三方扫描件的 PNG OCR 练习卡。 | FirstRAG 项目自编合成文本。 |

机器可读清单位于 [`tutorial_manifest.json`](../tutorial_manifest.json)。文档门禁会验证清单中的素材存在、来源字段受支持，并对教程和素材执行敏感信息模式检查。

## 生成 OCR 练习卡

仓库不提交来源不明的 PDF 或图片。使用 Pillow 把 ground truth 生成到已忽略的 `tmp/` 目录：

```bash
conda run -n firstrag python scripts/generate_tutorial_ocr_fixture.py
```

默认输出：

```text
tmp/tutorial-fixtures/firstrag-synthetic-ocr-card.png
```

图片只包含 [`ocr_ground_truth.txt`](ocr_ground_truth.txt) 中的英文合成文本，并施加固定的轻微旋转和模糊。它适合观察图片入库、OCR 和 sources，不代表真实扫描件准确率；正式 OCR 退化门禁仍使用 `scripts/eval_pdf_ocr.py`。

## 安全和清理

- 不要把真实 API Key、JWT、密码、个人文件或生产导出数据替换进这些素材后提交。
- credential-free E2E 在独立 Compose project 中使用 TXT fixture，结束后自动删除 containers、network 和 volumes。
- OCR PNG 生成在 `tmp/`，使用完成后可以直接删除单个生成文件；它不是仓库事实源，ground truth 才是。
