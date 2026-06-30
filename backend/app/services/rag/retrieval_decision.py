import json
from typing import Any

from app.repositories.retrieval_settings_repository import (
    DEFAULT_RETRIEVAL_SETTINGS,
)
from app.services.rag.types import ChainInput, RetrievalDecision


def normalize_retrieval_settings(settings: dict[str, Any] | None) -> dict:
    """规范化知识库检索设置，保证链路内部总能拿到完整字段。"""
    normalized = dict(DEFAULT_RETRIEVAL_SETTINGS)
    if isinstance(settings, dict):
        normalized.update({
            key: value
            for key, value in settings.items()
            if value is not None and key in DEFAULT_RETRIEVAL_SETTINGS
        })
    return normalized


def should_run_query_router(inputs: ChainInput) -> bool:
    """判断本轮是否需要调用 Router LLM。"""
    settings = normalize_retrieval_settings(inputs.get("retrieval_settings"))
    return (
        settings["retrieval_mode"] == "auto"
        and bool(settings["enable_query_router"])
    )


def build_configured_retrieval_decision(inputs: ChainInput) -> RetrievalDecision:
    """当配置跳过 Router LLM 时，生成确定性的路由结果。"""
    settings = normalize_retrieval_settings(inputs.get("retrieval_settings"))
    query = str(inputs.get("standalone_question") or inputs.get("input") or "")
    mode = settings["retrieval_mode"]

    if mode == "never":
        return {
            "need_retrieval": False,
            "rewritten_query": query,
            "reason": "当前知识库设置为永不检索",
        }

    if mode == "always":
        return {
            "need_retrieval": True,
            "rewritten_query": query,
            "reason": "当前知识库设置为强制检索",
        }

    return {
        "need_retrieval": True,
        "rewritten_query": query,
        "reason": "Query Router 已关闭，默认执行知识库检索",
    }


def append_reason_once(reason: str, suffix: str) -> str:
    """向路由原因追加说明，避免相同配置原因重复出现。"""
    if suffix in reason:
        return reason
    return f"{reason}；{suffix}" if reason else suffix


def normalize_retrieval_decision(
    decision: dict[str, Any] | None,
) -> RetrievalDecision:
    """规范化检索路由结果，异常或缺失时保守选择检索。"""
    if not isinstance(decision, dict):
        return {
            "need_retrieval": True,
            "final_need_retrieval": True,
            "llm_need_retrieval": None,
            "rewritten_query": "",
            "reason": "路由结果无效，保守执行知识库检索",
            "llm_reason": "路由结果无效",
            "override_applied": True,
            "override_reason": "路由结果无效，保守执行知识库检索",
        }

    need_retrieval = decision.get("need_retrieval", True)
    if isinstance(need_retrieval, str):
        need_retrieval = need_retrieval.strip().lower()
        need_retrieval = need_retrieval not in {"false", "0", "no", "否"}
    rewritten_query = str(decision.get("rewritten_query") or "").strip()
    reason = str(decision.get("reason") or "").strip()

    normalized: RetrievalDecision = {
        "need_retrieval": bool(need_retrieval),
        "final_need_retrieval": bool(need_retrieval),
        "rewritten_query": rewritten_query,
        "reason": reason or "未提供原因",
        "llm_reason": str(
            decision.get("llm_reason") or reason or "未提供原因",
        ).strip(),
        "override_applied": bool(decision.get("override_applied", False)),
        "override_reason": str(decision.get("override_reason") or "").strip(),
    }

    llm_need_retrieval = decision.get("llm_need_retrieval")
    if isinstance(llm_need_retrieval, bool):
        normalized["llm_need_retrieval"] = llm_need_retrieval
    elif "llm_need_retrieval" not in decision:
        normalized["llm_need_retrieval"] = bool(need_retrieval)
    else:
        normalized["llm_need_retrieval"] = None

    final_need_retrieval = decision.get("final_need_retrieval")
    if isinstance(final_need_retrieval, bool):
        normalized["final_need_retrieval"] = final_need_retrieval
        normalized["need_retrieval"] = final_need_retrieval

    return normalized


def parse_retrieval_decision(raw_output: str) -> RetrievalDecision:
    """解析 Router LLM 输出的 JSON 路由结果。

    Router 可能因为模型格式漂移输出 Markdown 代码块或额外说明。
    这里尽量抽取第一段 JSON；解析失败时保守走检索，避免知识库问题被误判。
    """
    text = raw_output.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()

    json_start = text.find("{")
    json_end = text.rfind("}")
    if json_start >= 0 and json_end >= json_start:
        text = text[json_start:json_end + 1]

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return normalize_retrieval_decision(None)

    return normalize_retrieval_decision(parsed)


def extract_chinese_ngrams(text: str, min_size: int = 2, max_size: int = 6) -> set[str]:
    """提取中文 ngram，用于判断问题和知识库画像是否有主题重合。"""
    terms: set[str] = set()
    buffer = []
    for char in text:
        if "\u4e00" <= char <= "\u9fff":
            buffer.append(char)
            continue

        if buffer:
            terms.update(build_ngrams_from_chars(buffer, min_size, max_size))
            buffer.clear()

    if buffer:
        terms.update(build_ngrams_from_chars(buffer, min_size, max_size))

    return terms


def build_ngrams_from_chars(
    chars: list[str],
    min_size: int,
    max_size: int,
) -> set[str]:
    """从连续中文字符中生成 ngram 集合。"""
    terms: set[str] = set()
    length = len(chars)
    for size in range(min_size, min(max_size, length) + 1):
        for start in range(0, length - size + 1):
            terms.add("".join(chars[start:start + size]))
    return terms


def should_force_retrieval_by_profile(question: str, profile: str) -> bool:
    """当问题关键词命中知识库文件画像时，强制走检索。

    Router 对“什么是诉讼法”这类问题可能判断成通用问答。但如果当前
    知识库文件名里有“民事诉讼法”，用户通常期待基于知识库回答并展示引用。
    因此这里用轻量 ngram 重合做确定性兜底。
    """
    question_terms = extract_chinese_ngrams(question)
    if not question_terms:
        return False

    profile_terms = extract_chinese_ngrams(profile)
    return bool(question_terms & profile_terms)


def finalize_retrieval_decision(inputs: ChainInput) -> RetrievalDecision:
    """结合 Router 结果和知识库画像生成最终检索决策。"""
    decision = normalize_retrieval_decision(
        inputs.get("raw_retrieval_decision"),
    )
    query = decision["rewritten_query"] or inputs.get(
        "standalone_question",
        "",
    )
    profile = str(inputs.get("knowledge_profile") or "")
    settings = normalize_retrieval_settings(inputs.get("retrieval_settings"))
    retrieval_mode = settings["retrieval_mode"]

    if retrieval_mode == "never":
        reason = "当前知识库设置为永不检索"
        return {
            "need_retrieval": False,
            "rewritten_query": query,
            "reason": append_reason_once(decision["reason"], reason),
        }

    if retrieval_mode == "always":
        reason = "当前知识库设置为强制检索"
        return {
            "need_retrieval": True,
            "rewritten_query": query,
            "reason": append_reason_once(decision["reason"], reason),
        }

    if not settings["enable_query_router"]:
        reason = "Query Router 已关闭，默认执行知识库检索"
        return {
            "need_retrieval": True,
            "rewritten_query": query,
            "reason": append_reason_once(decision["reason"], reason),
        }

    final_decision: RetrievalDecision = {
        **decision,
        "llm_need_retrieval": decision["need_retrieval"],
        "llm_reason": decision["reason"],
        "override_applied": False,
        "override_reason": "",
        "final_need_retrieval": decision["need_retrieval"],
    }

    if (
        not decision["need_retrieval"]
        and should_force_retrieval_by_profile(query, profile)
    ):
        override_reason = "问题关键词命中当前知识库文件画像，已强制检索"
        return {
            **final_decision,
            "need_retrieval": True,
            "final_need_retrieval": True,
            "rewritten_query": query,
            "override_applied": True,
            "override_reason": override_reason,
            "reason": (
                f"{decision['reason']}；{override_reason}"
            ),
        }

    return final_decision


def format_route_info(inputs: ChainInput) -> str:
    """将检索路由结果格式化为回答阶段的系统提示信息。"""
    decision = normalize_retrieval_decision(
        inputs.get("retrieval_decision"),
    )
    need_retrieval = "是" if decision["need_retrieval"] else "否"
    query = decision["rewritten_query"] or inputs.get(
        "standalone_question",
        "",
    )
    return (
        f"是否需要知识库检索：{need_retrieval}\n"
        f"检索/改写问题：{query}\n"
        f"判断原因：{decision['reason']}"
    )
