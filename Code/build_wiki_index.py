"""17-生产知识库实战 · 离线入库流水线（Ingestion）

生产 RAG 的离线半边：扫描仓库根目录学习笔记(00~16) → 按 ## 标题切块
→ 豆包 embedding → 持久化 JSON 索引（扮演向量库角色）。

增量更新：文件 md5 没变的跳过，变了的删旧块重新入库，删掉的文件移出索引。
用法: python Code/build_wiki_index.py [--rebuild]
"""
import hashlib
import json
import os
import re
import sys
from pathlib import Path

from openai import OpenAI

ROOT = Path(__file__).resolve().parent.parent          # 仓库根目录
INDEX_PATH = Path(__file__).resolve().parent / "wiki_index.json"
EMBED_MODEL = "doubao-embedding-vision"
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://ark.cn-beijing.volces.com/api/coding/v3",
)


def embed(texts: list[str]) -> list[list[float]]:
    """批量向量化。字符串直传——火山端点不吃 token id（见 08 笔记踩坑记录）"""
    out = []
    for i in range(0, len(texts), 10):  # 该端点单次最多 10 条
        resp = client.embeddings.create(model=EMBED_MODEL, input=texts[i:i + 10])
        out += [d.embedding for d in resp.data]
    return out


def chunk_file(path: Path) -> list[dict]:
    """按 ## 标题切块（结构化切块：顺着文档语义边界切，不是盲切字符数）。
    首个 ## 之前的元数据头（学习日期/定位/路线位置）单独成块——它对检索很有用。"""
    lines = path.read_text(encoding="utf-8").splitlines()
    page_title = next((l.lstrip("# ").strip() for l in lines if l.startswith("# ")), path.stem)
    chunks, head, buf = [], "开头·元数据", []
    for line in lines:
        if line.startswith("## "):
            if buf:
                chunks.append({"heading": head, "text": "\n".join(buf).strip()})
            head, buf = line[3:].strip(), [line]
        else:
            buf.append(line)
    if buf:
        chunks.append({"heading": head, "text": "\n".join(buf).strip()})
    return [{"file": path.name, "page": page_title, **c} for c in chunks if c["text"]]


def main():
    rebuild = "--rebuild" in sys.argv
    old = {"files": {}, "chunks": []}
    if not rebuild and INDEX_PATH.exists():
        old = json.loads(INDEX_PATH.read_text(encoding="utf-8"))

    # 全量扫文件算 md5。ponytail: 17 个文件秒算，不做 mtime/缓存优化
    files = sorted(p for p in ROOT.glob("*.md") if re.match(r"^\d{2}-", p.name))
    files_md5 = {p.name: hashlib.md5(p.read_bytes()).hexdigest() for p in files}

    # 增量逻辑：没变的文件保留旧块（连同旧向量，不重复调 API）
    chunks = [c for c in old["chunks"]
              if c["file"] in files_md5 and old["files"].get(c["file"]) == files_md5[c["file"]]]
    done = {c["file"] for c in chunks}
    todo = [p for p in files if p.name not in done]
    if todo:
        new_chunks = sum((chunk_file(p) for p in todo), [])
        # 向量化时把「页面标题 · 章节标题」拼进文本——标题是强语义信号
        vecs = embed([f"{c['page']} · {c['heading']}\n{c['text']}" for c in new_chunks])
        for c, v in zip(new_chunks, vecs):
            c["vec"] = v
        chunks += new_chunks

    removed = set(old["files"]) - set(files_md5)
    INDEX_PATH.write_text(
        json.dumps({"model": EMBED_MODEL, "files": files_md5, "chunks": chunks}, ensure_ascii=False),
        encoding="utf-8")
    msg = f"✅ 入库完成：{len(files)} 篇 → {len(chunks)} 块"
    if not rebuild:
        msg += f"（重入库 {len(todo)} 篇，跳过未变 {len(done)} 篇，移除 {len(removed)} 篇）"
    print(msg + f" → {INDEX_PATH.name}")


if __name__ == "__main__":
    main()
