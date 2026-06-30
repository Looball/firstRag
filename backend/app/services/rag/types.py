from typing import Any
from uuid import UUID

from langchain_core.documents import Document

type RetrievedDocs = list[Document]
type ChainInput = dict[str, Any]
type RagStreamEvent = dict[str, Any]
type RetrievalDecision = dict[str, Any]

MAX_KNOWLEDGE_PROFILE_FILES = 30
