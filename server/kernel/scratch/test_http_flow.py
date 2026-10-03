import asyncio
import requests
import sys

sys.path.insert(0, "kernel")

from repository.task_repo import DB_get_all_tasks, DB_get_task
from services.task_runner import run_task


async def test_backend_and_kernel_flow():
    print("--- Testing Full Backend & Kernel Task Persistence Flow ---")

    # 1. Simulate Turn 1: New task (task_id = "")
    prompt_1 = "My name is Mohan, remember this"
    req_id_1 = "test-req-http-1"
    print(f"\n[Turn 1] User prompt: '{prompt_1}'")

    resp_1 = await run_task(prompt_1, req_id_1, task_id="")
    print(f"[Turn 1] Kernel Response: {resp_1}")

    # Fetch the newly created task_id from MongoDB
    all_tasks = await DB_get_all_tasks()
    task_id = all_tasks[0]["task_id"]
    print(f"[Turn 1] Task ID saved in DB: {task_id}")

    # Verify messages stored in DB after Turn 1
    doc_1 = await DB_get_task(task_id)
    print(f"[Turn 1] DB Messages count: {len(doc_1.get('messages', []))}")
    for m in doc_1.get("messages", []):
        print(f"  - {m['role']}: {m['content']}")

    # 2. Simulate Turn 2: Follow-up (task_id = persistent task_id)
    prompt_2 = "whats my name"
    req_id_2 = "test-req-http-2"
    print(f"\n[Turn 2] User prompt: '{prompt_2}' with task_id='{task_id}'")

    resp_2 = await run_task(prompt_2, req_id_2, task_id=task_id)
    print(f"[Turn 2] Kernel Response: {resp_2}")

    # Verify messages stored in DB after Turn 2
    doc_2 = await DB_get_task(task_id)
    print(f"[Turn 2] DB Messages count after turn 2: {len(doc_2.get('messages', []))}")
    for m in doc_2.get("messages", []):
        print(f"  - {m['role']}: {m['content']}")


if __name__ == "__main__":
    asyncio.run(test_backend_and_kernel_flow())
