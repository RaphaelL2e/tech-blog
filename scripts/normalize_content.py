#!/usr/bin/env python3
"""Normalize Raphael Lab article metadata without changing published URLs."""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
POSTS = ROOT / "content" / "posts"
VALID_TOPICS = {
    "java-spring": "Java 与 Spring",
    "distributed-systems": "分布式与微服务",
    "database-middleware": "数据库与中间件",
    "system-engineering": "系统设计与工程效能",
    "ai-engineering": "AI 工程化",
    "computer-science": "计算机基础",
    "archive": "历史归档",
}

CN_DIGITS = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def chinese_number(value: str) -> int | None:
    value = value.strip()
    if value.isdigit():
        return int(value)
    if value == "十":
        return 10
    if "十" in value:
        left, right = value.split("十", 1)
        tens = CN_DIGITS.get(left, 1)
        ones = CN_DIGITS.get(right, 0)
        return tens * 10 + ones
    if len(value) == 1:
        return CN_DIGITS.get(value)
    return None


def split_document(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?", text, flags=re.S)
    if not match:
        raise ValueError("missing YAML front matter")
    meta = yaml.safe_load(match.group(1)) or {}
    if not isinstance(meta, dict):
        raise ValueError("front matter is not an object")
    return meta, text[match.end():]


def classify(title: str, meta: dict) -> str:
    categories = " ".join(str(item) for item in (meta.get("categories") or []))
    tags = " ".join(str(item) for item in (meta.get("tags") or []))
    value = f"{title} {categories} {tags}".lower()
    if "spring ai面试八股文" in value:
        return "ai-engineering"
    rules = [
        ("ai-engineering", ("ai大模型", "agent", "openclaw", "deepseek", "gpt", "llm", "大模型", "人工智能")),
        ("database-middleware", ("mysql", "redis", "kafka", "elasticsearch", "zookeeper", "mongodb", "newsql", "数据库", "消息队列", "索引", "sql", "oracle", "oralce")),
        ("distributed-systems", ("分布式", "微服务", "服务注册", "服务发现", "服务熔断", "服务治理", "网关", "负载均衡", "配置中心", "链路追踪", "限流", "一致性哈希")),
        ("java-spring", ("java", "spring", "jvm", "juc", "hashmap", "arraylist", "threadlocal", "aqs", "synchronized", "volatile", "reentrantlock", "cas", "线程池", "原子类", "设计模式")),
        ("system-engineering", ("系统分析", "系统设计", "系统架构", "系统质量", "建模", "devops", "ddd", "持续交付", "技术债", "软件测试")),
        ("computer-science", ("计算机网络", "tcp", "udp", "http", "https", "dns", "操作系统", "linux", "算法", "数据结构", "二叉树", "链表", "数组", "排序", "github", "html", "maven")),
    ]
    for topic, needles in rules:
        if any(needle in value for needle in needles):
            return topic
    return "archive"


SERIES_PATTERNS = [
    ("java-design-patterns", re.compile(r"java设计模式[（(]?([\d一二三四五六七八九十]+)[）)]?", re.I)),
    ("spring-ai-interview", re.compile(r"SpringAI面试八股文（([\d一二三四五六七八九十]+)）", re.I)),
    ("spring-interview", re.compile(r"Spring面试八股文（([\d一二三四五六七八九十]+)）", re.I)),
    ("distributed-systems-interview", re.compile(r"分布式系统面试八股文（([\d一二三四五六七八九十]+)）")),
    ("microservices-interview", re.compile(r"微服务面试八股文（([\d一二三四五六七八九十]+)）")),
    ("database-interview", re.compile(r"数据库面试八股文（([\d一二三四五六七八九十]+)）")),
    ("ai-llm-interview", re.compile(r"AI大模型面试八股文（([\d一二三四五六七八九十]+)）", re.I)),
    ("computer-network", re.compile(r"计算机网络面试八股文（([\d一二三四五六七八九十]+)）")),
    ("operating-system", re.compile(r"操作系统面试八股文（([\d一二三四五六七八九十]+)）")),
]


def detect_series(title: str) -> tuple[str, int] | None:
    compact = title.replace(" ", "")
    if "GoF23设计模式全总结" in compact:
        return "java-design-patterns", 23
    for key, pattern in SERIES_PATTERNS:
        match = pattern.search(compact)
        if match:
            order = chinese_number(match.group(1))
            if order:
                return key, order
    distributed_special = {
        "分布式定时任务与工作流引擎": 7,
        "分布式监控与告警系统实战": 8,
        "分布式配置中心与配置治理": 9,
    }
    for prefix, order in distributed_special.items():
        if prefix in compact:
            return "distributed-systems-interview", order
    system_patterns = [
        ("系统静态分析建模", 1), ("系统动态行为建模", 2), ("系统设计模式实战", 3),
        ("系统架构设计实战", 4), ("系统质量属性设计", 5), ("分布式系统设计实战", 6),
        ("系统分析与设计（七）", 7), ("系统分析与设计（八）", 8), ("系统分析与设计（九）", 9),
    ]
    for prefix, order in system_patterns:
        if prefix in compact:
            return "system-design", order
    return None


def plain_text(body: str) -> str:
    chunks: list[str] = []
    in_fence = False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            continue
        if in_fence or not stripped or stripped.startswith(("#", "|", "<", "---")):
            continue
        cleaned = re.sub(r"!\[[^]]*]\([^)]*\)", "", stripped)
        cleaned = re.sub(r"\[([^]]+)]\([^)]*\)", r"\1", cleaned)
        cleaned = re.sub(r"[`*_>#]+", "", cleaned)
        cleaned = re.sub(r"^[-+\d.)\s]+", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if len(cleaned) >= 16 and re.search(r"[A-Za-z\u4e00-\u9fff]", cleaned):
            chunks.append(cleaned)
        if sum(len(item) for item in chunks) >= 180:
            break
    return " ".join(chunks)


def description_for(title: str, body: str, current: object) -> str:
    if isinstance(current, str) and len(current.strip()) >= 35:
        return re.sub(r"\s+", " ", current).strip()[:180]
    source = plain_text(body)
    if len(source) < 50:
        source = f"本文围绕「{title}」整理核心概念、实现思路与工程中的常见问题，帮助读者建立可以用于实践和复习的结构化理解。"
    sentence = source[:150].rstrip("，,; ")
    if sentence[-1:] not in "。！？.!?":
        sentence += "。"
    return sentence


TAG_ALIASES = {
    "jvm": "JVM", "java": "Java", "spring": "Spring", "spring boot": "Spring Boot",
    "mysql": "MySQL", "redis": "Redis", "kafka": "Kafka", "linux": "Linux",
    "http": "HTTP", "https": "HTTPS", "tcp": "TCP", "udp": "UDP", "ai": "AI",
    "elasticsearch": "Elasticsearch", "docker": "Docker", "kubernetes": "Kubernetes",
}


def normalize_tags(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    output: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = re.sub(r"\s+", " ", str(raw)).strip()
        if not value:
            continue
        canonical = TAG_ALIASES.get(value.casefold(), value)
        key = canonical.casefold()
        if key not in seen:
            seen.add(key)
            output.append(canonical)
        if len(output) == 5:
            break
    return output


def normalize_headings(body: str) -> tuple[str, int]:
    lines = body.splitlines()
    in_fence = False
    first_content_seen = False
    changes = 0
    output: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            output.append(line)
            continue
        if not in_fence and re.match(r"^#\s+", line):
            changes += 1
            if not first_content_seen:
                first_content_seen = True
                continue
            line = "#" + line
        if stripped:
            first_content_seen = True
        output.append(line)
    return "\n".join(output).strip() + "\n", changes


def year_of(value: object) -> int:
    if isinstance(value, (date, datetime)):
        return value.year
    match = re.match(r"(\d{4})", str(value or ""))
    return int(match.group(1)) if match else 2000


def ordered_meta(meta: dict) -> dict:
    preferred = ["title", "slug", "date", "updated", "description", "topic", "series", "series_order", "level", "status", "featured", "tags", "categories", "draft"]
    result = {key: meta[key] for key in preferred if key in meta}
    result.update({key: value for key, value in meta.items() if key not in result})
    return result


def normalize(path: Path, write: bool) -> tuple[bool, int, str]:
    meta, body = split_document(path)
    original_meta = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False, width=120)
    original_body = body
    title = str(meta.get("title") or path.stem).strip()
    topic = classify(title, meta)
    meta["title"] = title
    meta["description"] = description_for(title, body, meta.get("description"))
    meta["topic"] = topic
    meta["categories"] = [VALID_TOPICS[topic]]
    meta["tags"] = normalize_tags(meta.get("tags"))
    meta["status"] = "maintained" if year_of(meta.get("date")) >= 2025 else "archived"
    meta["level"] = meta.get("level") or "intermediate"
    if "updated" not in meta:
        meta["updated"] = meta.get("date")
    if isinstance(meta.get("updated"), (date, datetime)):
        meta["updated"] = meta["updated"].isoformat()
    detected = detect_series(title)
    if detected:
        meta["series"], meta["series_order"] = detected
    if title in {
        "分布式系统面试八股文（十）——30道高频综合面试题大串讲",
        "AI大模型面试八股文（六）——大模型系统设计与工程实践",
        "Spring面试八股文（十）——Spring Boot条件装配深度解析与ConfigurationProperties最佳实践",
    }:
        meta["featured"] = True
    body = body.replace("作者：飞哥的 AI 折腾日记", "作者：李亚飞 · Raphael Lab")
    body = body.replace("作者：飞哥的AI折腾日记", "作者：李亚飞 · Raphael Lab")
    body = body.replace("](/秘钥链接.md)", "](/posts/秘钥连接/)")
    body = body.replace("](/posts/秘钥链接/)", "](/posts/秘钥连接/)")
    body = body.replace("](/categories/java/)", "](/posts/?topic=java-spring)")
    body = body.replace("](/tags/jvm/)", "](/search/?q=JVM)")
    body, heading_changes = normalize_headings(body)
    meta = ordered_meta(meta)
    dumped = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False, width=120).strip()
    changed = dumped != original_meta.strip() or body != original_body
    if write and changed:
        path.write_text(f"---\n{dumped}\n---\n\n{body}", encoding="utf-8")
    return changed, heading_changes, topic


def validate() -> list[str]:
    errors: list[str] = []
    slugs: Counter[str] = Counter()
    for path in sorted(POSTS.glob("*.md")):
        if path.name == "_index.md":
            continue
        try:
            meta, body = split_document(path)
        except Exception as exc:
            errors.append(f"{path.name}: {exc}")
            continue
        slugs[(meta.get("slug") or path.stem).casefold()] += 1
        for key in ("title", "date", "description", "topic", "status"):
            if not meta.get(key):
                errors.append(f"{path.name}: missing {key}")
        if meta.get("topic") not in VALID_TOPICS:
            errors.append(f"{path.name}: invalid topic {meta.get('topic')}")
        if len(meta.get("tags") or []) > 5:
            errors.append(f"{path.name}: more than 5 tags")
        _, body_h1_count = normalize_headings(body)
        if body_h1_count:
            errors.append(f"{path.name}: body contains H1")
        if meta.get("series") and not meta.get("series_order"):
            errors.append(f"{path.name}: series without series_order")
    for slug, count in slugs.items():
        if count > 1:
            errors.append(f"duplicate slug: {slug}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="write normalized content")
    parser.add_argument("--check", action="store_true", help="validate normalized content")
    args = parser.parse_args()
    changed = headings = 0
    topics: Counter[str] = Counter()
    if not args.check or args.write:
        for path in sorted(POSTS.glob("*.md")):
            if path.name == "_index.md":
                continue
            try:
                was_changed, heading_count, topic = normalize(path, args.write)
            except Exception as exc:
                print(f"ERROR {path.name}: {exc}", file=sys.stderr)
                return 1
            changed += int(was_changed)
            headings += heading_count
            topics[topic] += 1
        mode = "updated" if args.write else "would update"
        print(f"{mode} {changed} articles; normalized {headings} body H1 headings")
        print("topics:", ", ".join(f"{key}={value}" for key, value in sorted(topics.items())))
    if args.check:
        errors = validate()
        if errors:
            print("validation failed:")
            print("\n".join(f"- {error}" for error in errors))
            return 1
        print("content validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
