import os
import csv
import time
import requests
from dotenv import load_dotenv

HERE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(HERE, "..", ".env"))

API_TOKEN = os.environ["COZE_API_TOKEN"]
BOT_ID = os.environ["COZE_BOT_ID"]
API_BASE = os.environ.get("COZE_API_BASE", "https://api.coze.com")

CASES_PATH = os.path.normpath(
    os.path.join(HERE, "..", "docs", "test_cases.csv")
)
RESULTS_PATH = os.path.normpath(
    os.path.join(HERE, "..", "docs", "test_results.csv")
)

FIELDNAMES = [
    "id",
    "type",
    "input",
    "expected_keywords",
    "hits",
    "total_expected",
    "passed",
    "answer",
    "latency",
    "error",
]


def call_bot(text, user_id="eval-user"):
    url = f"{API_BASE}/v3/chat"
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json",
    }
    body = {
        "bot_id": BOT_ID,
        "user_id": user_id,
        "stream": False,
        "auto_save_history": True,
        "additional_messages": [
            {"role": "user", "content": text, "content_type": "text"}
        ],
    }

    start = time.time()
    try:
        r = requests.post(url, headers=headers, json=body, timeout=120)
        if r.status_code != 200:
            return {
                "error": f"HTTP {r.status_code}: {r.text[:300]}",
                "latency": round(time.time() - start, 2),
            }

        d = r.json()
        chat_id = d.get("data", {}).get("id")
        conv_id = d.get("data", {}).get("conversation_id")
        if not chat_id or not conv_id:
            return {
                "error": f"no id: {str(d)[:200]}",
                "latency": round(time.time() - start, 2),
            }

        for _ in range(30):
            time.sleep(2)
            p = requests.get(
                f"{API_BASE}/v3/chat/retrieve",
                params={"chat_id": chat_id, "conversation_id": conv_id},
                headers=headers,
                timeout=30,
            )
            if p.status_code == 200 and p.json().get("data", {}).get("status") == "completed":
                break

        m = requests.get(
            f"{API_BASE}/v3/chat/message/list",
            params={"chat_id": chat_id, "conversation_id": conv_id},
            headers=headers,
            timeout=30,
        )
        answer = ""
        if m.status_code == 200:
            for msg in m.json().get("data", []):
                if msg.get("type") == "answer" and msg.get("role") == "assistant":
                    answer += msg.get("content", "")

        return {
            "answer": answer,
            "latency": round(time.time() - start, 2),
            "error": "",
        }
    except Exception as e:
        return {"error": str(e), "latency": round(time.time() - start, 2)}


def main():
    with open(CASES_PATH, encoding="utf-8") as f:
        cases = list(csv.DictReader(f))

    results = []
    for i, case in enumerate(cases, 1):
        print(f"[{i}/{len(cases)}] {case['input'][:60]}...")
        r = call_bot(case["input"])

        expected = [
            k.strip() for k in case["expected_keywords"].split(",") if k.strip()
        ]
        ans = r.get("answer", "")
        hits = sum(1 for kw in expected if kw.lower() in ans.lower())
        passed = hits >= max(1, len(expected) // 2)

        results.append(
            {
                "id": case["id"],
                "type": case["type"],
                "input": case["input"],
                "expected_keywords": case["expected_keywords"],
                "hits": hits,
                "total_expected": len(expected),
                "passed": passed,
                "answer": ans,
                "latency": r.get("latency", ""),
                "error": r.get("error", ""),
            }
        )
        time.sleep(1)

    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
    with open(RESULTS_PATH, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        w.writeheader()
        w.writerows(results)

    passed = sum(1 for r in results if r["passed"])
    print(f"\nPassed: {passed}/{len(results)} ({100 * passed // len(results)}%)")


if __name__ == "__main__":
    main()