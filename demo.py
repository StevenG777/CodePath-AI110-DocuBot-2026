"""
Non-interactive DocuBot demo.

Runs a small set of queries through all three modes so the difference
between naive generation, retrieval-only, and RAG is visible side by side.

Usage:
    python demo.py                # runs the default demo queries
    python demo.py "your query"   # runs a single custom query
"""

import sys
from dotenv import load_dotenv
load_dotenv()

from docubot import DocuBot
from llm_client import GeminiClient

DEMO_QUERIES = [
    "How does a client refresh an access token?",   # naive vs grounded gap
    "What environment variables are required for authentication?",  # RAG shines
    "Is there any mention of payment processing in these docs?",    # correct refusal
]


def rule(char="="):
    print(char * 72)


def main():
    queries = [sys.argv[1]] if len(sys.argv) > 1 else DEMO_QUERIES

    try:
        llm = GeminiClient()
        has_llm = True
    except RuntimeError as exc:
        print(f"LLM disabled ({exc}); running retrieval-only.\n")
        llm, has_llm = None, False

    bot = DocuBot(docs_folder="docs", llm_client=llm)
    print(f"Loaded {len(bot.documents)} docs: "
          f"{', '.join(f for f, _ in bot.documents)}\n")

    for q in queries:
        rule()
        print(f"QUERY: {q}")
        rule()

        # Retrieval only
        snippets = bot.retrieve(q)
        print("\n[Retrieval only] top snippets:")
        if not snippets:
            print("  (no snippets cleared the score threshold)")
        for fname, chunk in snippets:
            first_line = chunk.strip().splitlines()[0]
            print(f"  - {fname}: {first_line[:70]}")

        if has_llm:
            # Naive
            print("\n[Naive LLM] (no retrieval):")
            naive = bot.llm_client.naive_answer_over_full_docs(q, bot.full_corpus_text())
            print("  " + naive.strip().replace("\n", "\n  "))

            # RAG
            print("\n[RAG] (retrieval + grounded LLM):")
            print("  " + bot.answer_rag(q).strip().replace("\n", "\n  "))

        print()


if __name__ == "__main__":
    main()
