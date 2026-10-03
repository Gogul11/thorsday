import sys
sys.path.insert(0, 'kernel')
from services.context_pager import context_pager, ACTIVE_RAM_WINDOW

TASK_ID = 'test-task-review-demo-2'

# ---------------------------------------------------------------
# Simulate 30 conversation turns (10 above the 20-message window)
# ---------------------------------------------------------------
messages = []
for i in range(30):
    role = 'human' if i % 2 == 0 else 'ai'
    if i == 2:
        content = 'The database schema uses a tasks collection in MongoDB with UUID primary keys.'
    elif i == 4:
        content = 'We decided the kernel and backend communicate exclusively via Redis pub/sub.'
    elif i == 6:
        content = 'The active RAM window for context is capped at 20 messages.'
    else:
        content = f'Turn {i}: This is message number {i} in the conversation.'
    messages.append({'role': role, 'content': content, 'timestamp': f'2026-10-03T{i:02d}:00:00'})

N = len(messages)
overflow = messages[:N - ACTIVE_RAM_WINDOW]
print(f'Total messages: {N}')
print(f'Overflow (to page out): {len(overflow)}')
print(f'Active window (in RAM): {N - ACTIVE_RAM_WINDOW}')
print()

# ---------------------------------------------------------------
# Phase 1: Page-Out
# ---------------------------------------------------------------
paged = context_pager.page_out_messages(TASK_ID, overflow, base_index=0)
print(f'PAGE_OUT result: {paged} pages persisted to swap partition')
stats = context_pager.get_swap_stats(TASK_ID)
print(f'Swap stats: {stats}')
print()

# ---------------------------------------------------------------
# Phase 2: Page-In with a query referencing early turns
# ---------------------------------------------------------------
query = 'What did we decide about the database schema and MongoDB collection?'
print(f'PAGE_IN query: "{query}"')
hits = context_pager.page_in_relevant_context(TASK_ID, query)
print(f'PAGE_IN results: {len(hits)} pages retrieved above tau=0.55')
for h in hits:
    print(f'  [MsgIdx={h["message_index"]} | Sim={h["similarity"]:.4f} | Role={h["role"]}]')
    txt = h["text"]
    print(f'    > {txt[:80]}...' if len(txt) > 80 else f'    > {txt}')
print()

# ---------------------------------------------------------------
# Phase 3: Format the page-in block
# ---------------------------------------------------------------
if hits:
    block = context_pager.format_page_in_block(hits)
    print('FORMAT_PAGE_IN_BLOCK output (first 8 lines):')
    for line in block.splitlines()[:8]:
        print(f'  {line}')
