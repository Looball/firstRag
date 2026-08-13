"""结构优先的 parent/child 文档切分契约。"""

from dataclasses import dataclass

from langchain_core.documents import Document
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)


PARENT_CHUNK_SIZE = 2_000
PARENT_CHUNK_OVERLAP = 0
CHILD_CHUNK_SIZE = 600
CHILD_CHUNK_OVERLAP = 100
TEXT_SEPARATORS = ["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""]
MARKDOWN_HEADERS_TO_SPLIT_ON = [
    ("#", "h1"),
    ("##", "h2"),
    ("###", "h3"),
    ("####", "h4"),
    ("#####", "h5"),
    ("######", "h6"),
]
HIERARCHY_METADATA_KEYS = {
    "chunk_id",
    "chunk_index",
    "chunk_level",
    "parent_id",
    "parent_index",
    "parent_character_count",
    "child_id",
    "child_index",
}


@dataclass(frozen=True)
class ParentChildSplitResult:
    """一次批量切分产生的父块与可检索子块。"""

    parents: list[Document]
    children: list[Document]


def _clean_hierarchy_metadata(metadata: dict[str, object]) -> dict[str, object]:
    """移除旧层级字段，避免重建时沿用过期 identity。"""
    return {
        key: value
        for key, value in metadata.items()
        if key not in HIERARCHY_METADATA_KEYS
    }


def _build_parent_candidates(document: Document) -> list[Document]:
    """按结构边界构造 parent candidates，并对超长结构块做无 overlap fallback。"""
    parent_splitter = RecursiveCharacterTextSplitter(
        chunk_size=PARENT_CHUNK_SIZE,
        chunk_overlap=PARENT_CHUNK_OVERLAP,
        separators=TEXT_SEPARATORS,
    )
    base_metadata = _clean_hierarchy_metadata(dict(document.metadata))

    if document.metadata.get("content_format") != "markdown":
        return parent_splitter.split_documents([
            Document(
                page_content=document.page_content,
                metadata=base_metadata,
            )
        ])

    markdown_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=MARKDOWN_HEADERS_TO_SPLIT_ON,
        strip_headers=False,
    )
    sections = markdown_splitter.split_text(document.page_content)
    parents: list[Document] = []
    for section in sections:
        section.metadata = {
            **base_metadata,
            **section.metadata,
        }
        parents.extend(parent_splitter.split_documents([section]))
    return parents


def _build_children(parent: Document) -> list[Document]:
    """只在单个 parent 内生成有 overlap 的 child chunks。"""
    child_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHILD_CHUNK_SIZE,
        chunk_overlap=CHILD_CHUNK_OVERLAP,
        separators=TEXT_SEPARATORS,
    )
    return child_splitter.split_documents([parent])


def split_parent_child_documents(
    documents: list[Document],
) -> ParentChildSplitResult:
    """批量切分并在每个用户文件范围内分配连续 parent/child 序号。"""
    parents: list[Document] = []
    children: list[Document] = []
    next_parent_index_by_file: dict[tuple[str, str], int] = {}
    next_chunk_index_by_file: dict[tuple[str, str], int] = {}

    for document in documents:
        metadata = document.metadata
        sequence_key = (
            str(metadata.get("user_id") or ""),
            str(metadata.get("file_id") or metadata.get("source") or ""),
        )
        next_parent_index = next_parent_index_by_file.get(sequence_key, 0)
        next_chunk_index = next_chunk_index_by_file.get(sequence_key, 0)

        for candidate in _build_parent_candidates(document):
            if not candidate.page_content.strip():
                continue
            parent_index = next_parent_index
            parent_metadata = {
                **_clean_hierarchy_metadata(dict(candidate.metadata)),
                "chunk_level": "parent",
                "parent_index": parent_index,
            }
            parent = Document(
                page_content=candidate.page_content,
                metadata=parent_metadata,
            )
            parent_children = _build_children(parent)
            if not parent_children:
                continue

            next_parent_index += 1
            parents.append(parent)
            for child_index, child in enumerate(parent_children):
                child.metadata.update({
                    "chunk_level": "child",
                    "parent_index": parent_index,
                    "parent_character_count": len(parent.page_content),
                    "child_index": child_index,
                    "chunk_index": next_chunk_index,
                })
                next_chunk_index += 1
                children.append(child)

        next_parent_index_by_file[sequence_key] = next_parent_index
        next_chunk_index_by_file[sequence_key] = next_chunk_index

    return ParentChildSplitResult(parents=parents, children=children)
