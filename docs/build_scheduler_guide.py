from datetime import date
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


OUT = Path(__file__).with_name("global_agent_scheduler_guide.docx")
BLUE = "2E74B5"
DARK_BLUE = "1F4D78"
LIGHT_BLUE = "E8EEF5"
LIGHT_GRAY = "F2F4F7"
MUTED = "555555"


def set_cell_shading(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell, top=80, start=120, bottom=80, end=120):
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    margins = tc_pr.first_child_found_in("w:tcMar")
    if margins is None:
        margins = OxmlElement("w:tcMar")
        tc_pr.append(margins)
    for side, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = margins.find(qn(f"w:{side}"))
        if node is None:
            node = OxmlElement(f"w:{side}")
            margins.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_table_geometry(table, widths):
    table.autofit = False
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    tbl = table._tbl
    tbl_pr = tbl.tblPr
    tbl_w = tbl_pr.find(qn("w:tblW"))
    if tbl_w is None:
        tbl_w = OxmlElement("w:tblW")
        tbl_pr.append(tbl_w)
    tbl_w.set(qn("w:w"), str(sum(widths)))
    tbl_w.set(qn("w:type"), "dxa")
    tbl_ind = tbl_pr.find(qn("w:tblInd"))
    if tbl_ind is None:
        tbl_ind = OxmlElement("w:tblInd")
        tbl_pr.append(tbl_ind)
    tbl_ind.set(qn("w:w"), "120")
    tbl_ind.set(qn("w:type"), "dxa")
    grid = tbl.tblGrid
    for child in list(grid):
        grid.remove(child)
    for width in widths:
        col = OxmlElement("w:gridCol")
        col.set(qn("w:w"), str(width))
        grid.append(col)
    for row in table.rows:
        for cell, width in zip(row.cells, widths):
            tc_pr = cell._tc.get_or_add_tcPr()
            tc_w = tc_pr.find(qn("w:tcW"))
            if tc_w is None:
                tc_w = OxmlElement("w:tcW")
                tc_pr.append(tc_w)
            tc_w.set(qn("w:w"), str(width))
            tc_w.set(qn("w:type"), "dxa")
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            set_cell_margins(cell)


def set_font(run, name="Calibri", size=11, color="000000", bold=False, italic=False):
    run.font.name = name
    run._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), name)
    run._element.get_or_add_rPr().rFonts.set(qn("w:hAnsi"), name)
    run.font.size = Pt(size)
    run.font.color.rgb = RGBColor.from_string(color)
    run.bold = bold
    run.italic = italic


def style_paragraph(paragraph, before=0, after=6, line=1.25):
    fmt = paragraph.paragraph_format
    fmt.space_before = Pt(before)
    fmt.space_after = Pt(after)
    fmt.line_spacing = line


def add_text(doc, text, style=None, before=0, after=6, line=1.25):
    p = doc.add_paragraph(style=style)
    style_paragraph(p, before, after, line)
    run = p.add_run(text)
    set_font(run)
    return p


def add_bullet(doc, text):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.left_indent = Inches(0.375)
    p.paragraph_format.first_line_indent = Inches(-0.188)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.line_spacing = 1.25
    set_font(p.add_run(text))
    return p


def add_number(doc, text):
    p = doc.add_paragraph(style="List Number")
    p.paragraph_format.left_indent = Inches(0.375)
    p.paragraph_format.first_line_indent = Inches(-0.188)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.line_spacing = 1.25
    set_font(p.add_run(text))
    return p


def add_code(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.18)
    p.paragraph_format.right_indent = Inches(0.18)
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.line_spacing = 1.0
    pPr = p._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), "F4F6F9")
    pPr.append(shd)
    run = p.add_run(text)
    set_font(run, name="Consolas", size=9, color="1F2937")
    return p


def add_table(doc, headers, rows, widths):
    table = doc.add_table(rows=1, cols=len(headers))
    set_table_geometry(table, widths)
    for cell, text in zip(table.rows[0].cells, headers):
        set_cell_shading(cell, LIGHT_BLUE)
        p = cell.paragraphs[0]
        style_paragraph(p, 0, 4, 1.15)
        set_font(p.add_run(text), size=10, color=DARK_BLUE, bold=True)
    for row_index, values in enumerate(rows):
        cells = table.add_row().cells
        for cell, text in zip(cells, values):
            if row_index % 2:
                set_cell_shading(cell, "FAFBFC")
            p = cell.paragraphs[0]
            style_paragraph(p, 0, 4, 1.15)
            set_font(p.add_run(text), size=10)
    set_table_geometry(table, widths)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return table


def heading(doc, text, level=1):
    p = doc.add_paragraph(style=f"Heading {level}")
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    set_font(run, size={1: 16, 2: 13, 3: 12}[level], color=BLUE if level < 3 else DARK_BLUE, bold=True)
    return p


def build():
    doc = Document()
    section = doc.sections[0]
    section.top_margin = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin = Inches(1)
    section.right_margin = Inches(1)
    section.header_distance = Inches(0.492)
    section.footer_distance = Inches(0.492)

    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal._element.rPr.rFonts.set(qn("w:ascii"), "Calibri")
    normal._element.rPr.rFonts.set(qn("w:hAnsi"), "Calibri")
    normal.font.size = Pt(11)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.25
    for name, size, color, before, after in (
        ("Heading 1", 16, BLUE, 18, 10),
        ("Heading 2", 13, BLUE, 14, 7),
        ("Heading 3", 12, DARK_BLUE, 10, 5),
    ):
        style = doc.styles[name]
        style.font.name = "Calibri"
        style._element.rPr.rFonts.set(qn("w:ascii"), "Calibri")
        style._element.rPr.rFonts.set(qn("w:hAnsi"), "Calibri")
        style.font.size = Pt(size)
        style.font.color.rgb = RGBColor.from_string(color)
        style.font.bold = True
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.keep_with_next = True

    header = section.header.paragraphs[0]
    header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    set_font(header.add_run("AgentOS · Technical Reference"), size=9, color=MUTED)
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    set_font(footer.add_run("Global Agent Scheduler"), size=9, color=MUTED)

    title = doc.add_paragraph()
    title.paragraph_format.space_after = Pt(4)
    set_font(title.add_run("Global Agent Scheduler"), size=26, color=DARK_BLUE, bold=True)
    subtitle = doc.add_paragraph()
    subtitle.paragraph_format.space_after = Pt(14)
    set_font(subtitle.add_run("How scheduling, resource admission, Redis state, and recovery work in AgentOS"), size=13, color=MUTED)
    meta = doc.add_paragraph()
    meta.paragraph_format.space_after = Pt(16)
    set_font(meta.add_run(f"Implementation guide · Repository snapshot · {date.today().isoformat()}"), size=9, color=MUTED, italic=True)

    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(12)
    pPr = p._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), "F4F6F9")
    pPr.append(shd)
    set_font(p.add_run("Key takeaway\n"), size=11, color=DARK_BLUE, bold=True)
    set_font(p.add_run("The planner creates dependency-aware DAG steps. The global scheduler decides when each ready step may run, and the resource manager decides whether enough execution capacity is available."), size=11)

    heading(doc, "1. What was implemented", 1)
    add_text(doc, "The implementation is centered on a process-wide AgentScheduler shared by all tasks running in the kernel. It does not replace LangGraph dependency handling; it sits in front of the existing agent execution function.")
    add_table(doc, ["Component", "Responsibility", "Current implementation"], [
        ("Planner / DAG", "Select agents and express dependencies", "Existing planner and plan_steps state"),
        ("AgentScheduler", "Global ordering and dispatch", "Redis metadata, priority aging, fair selection, concurrent jobs"),
        ("ResourceManager", "Admission control", "3 global slots, 2 slots per task, token-budget checks"),
        ("Agent runtime", "Actual agent/tool execution", "Existing registered agent run functions"),
        ("Event bus", "Live observability", "Redis kernel_events forwarded to WebSocket"),
        ("Frontend", "Human-readable monitoring", "Timeline plus scheduler metrics panel"),
    ], [1800, 3000, 4560])

    heading(doc, "2. End-to-end execution flow", 1)
    for item in [
        "The planner produces plan_steps. Each step contains an id, agent name, dependencies, and purpose.",
        "The DAG executor finds a step whose dependencies are complete.",
        "That step is wrapped in a SchedulerJob and submitted to the global scheduler.",
        "The scheduler records the job in Redis and publishes AGENT_READY.",
        "The scheduler computes effective priority and selects a ready job.",
        "The resource manager grants or denies admission based on global slots, per-task slots, and token budget.",
        "An approved job is dispatched as an asyncio task. Independent jobs can run concurrently.",
        "The result returns to the DAG executor, which records the step result and unlocks dependent steps.",
    ]:
        add_number(doc, item)
    add_code(doc, "Planner → dependency-ready step → Redis READY metadata → priority selection\n       → resource admission → agent runtime → result → completed DAG step")

    heading(doc, "3. Scheduler algorithm", 1)
    add_text(doc, "Every queued job has a base priority and ready timestamp. Waiting jobs gain priority over time so that a low-priority task cannot starve indefinitely.")
    add_code(doc, "waiting_time = current_time - ready_at\neffective_priority = min(max_priority, base_priority + aging_factor * waiting_time)\nselected_job = argmax(effective_priority)")
    heading(doc, "3.1 Fairness and concurrency", 2)
    add_bullet(doc, "The scheduler selects the highest effective priority, with earlier ready time used as a tie-breaker.")
    add_bullet(doc, "It launches admitted jobs concurrently until the resource limits are reached.")
    add_bullet(doc, "When one job completes, the scheduler wakes and fills the available slot.")
    add_bullet(doc, "The configured time quantum is cooperative metadata. The scheduler does not forcibly cancel an in-flight LLM call.")

    heading(doc, "4. Resource manager", 1)
    add_text(doc, "ResourceManager is an in-process admission controller with Redis-visible scheduler records. It reserves capacity before execution and releases the active slot after the job finishes.")
    add_table(doc, ["Limit", "Default", "Meaning"], [
        ("Global slots", "3", "At most three agent executions are active in the kernel."),
        ("Per-task slots", "2", "One task cannot consume all global capacity."),
        ("Token budget", "50,000", "Estimated token usage allowed per task."),
        ("Retry limit", "3", "Quota/rate-limit errors are requeued before final failure."),
        ("Time quantum", "30 seconds", "Cooperative scheduling target; no hard cancellation."),
    ], [1800, 1500, 6060])
    add_text(doc, "Admission is temporary-denial when capacity is busy. A job waits until a slot becomes available. A job whose estimate is larger than the token budget is denied permanently and emits RESOURCE_DENIED plus AGENT_BLOCKED.")

    heading(doc, "5. Redis state and events", 1)
    add_text(doc, "The scheduler uses Redis for durable queue metadata and the existing kernel_events Pub/Sub channel for live UI updates.")
    add_table(doc, ["Redis key", "Purpose"], [
        ("agentos:scheduler:ready", "Sorted set containing READY/WAITING execution IDs."),
        ("agentos:scheduler:job:<execution_id>", "Hash containing task, step, agent, status, priority, ready time, and attempt."),
        ("kernel_events", "Live lifecycle and resource events forwarded to the frontend."),
    ], [3300, 6060])
    heading(doc, "5.1 Event lifecycle", 2)
    add_table(doc, ["Event", "When it is emitted"], [
        ("AGENT_READY", "A DAG step enters the scheduler queue."),
        ("AGENT_RUNNING", "A job is admitted and dispatched."),
        ("AGENT_WAITING", "A job is waiting for capacity or a provider retry."),
        ("AGENT_PREEMPTED", "A cooperative checkpoint requests requeue."),
        ("AGENT_COMPLETED", "The scheduled job returns successfully."),
        ("AGENT_FAILED", "The final execution attempt fails."),
        ("AGENT_BLOCKED", "The resource policy permanently blocks the job."),
        ("RESOURCE_APPROVED / DENIED", "Resource admission decision."),
    ], [3000, 6360])
    add_code(doc, '{\n  "task_id": "...", "step_id": "step_2",\n  "agent_name": "weather_agent", "execution_id": "...",\n  "status": "RUNNING", "priority": 5,\n  "effective_priority": 5.42, "queue_wait_ms": 210,\n  "attempt": 1\n}')

    heading(doc, "6. How the frontend reflects scheduling", 1)
    add_bullet(doc, "The WebSocket receives scheduler and resource events through the existing kernel listener.")
    add_bullet(doc, "The task timeline shows queued, dispatched, waiting, requeued, completed, blocked, and failed states.")
    add_bullet(doc, "The Task Activity panel shows the current scheduler status, agent, effective priority, queue position, wait time, active slots, and global queue size.")
    add_bullet(doc, "The plan graph remains separate: it shows DAG structure, while the timeline shows runtime scheduling behavior.")

    heading(doc, "7. Recovery: what is and is not implemented", 1)
    add_text(doc, "Recovery is intentionally documented precisely because there is an important boundary in the current implementation.")
    add_table(doc, ["Recovery capability", "Status"], [
        ("Persist READY and WAITING metadata in Redis", "Implemented"),
        ("Scan scheduler records at kernel startup", "Implemented"),
        ("Mark stale RUNNING records as INTERRUPTED", "Implemented"),
        ("Avoid claiming a completed execution again", "Execution IDs and completion metadata are recorded"),
        ("Reconstruct the original Python coroutine after a full kernel restart", "Not yet implemented"),
        ("Automatically resume an interrupted LLM/tool call", "Not yet implemented"),
    ], [5200, 4160])
    add_text(doc, "Why the limitation exists: a Python coroutine and its closures are process memory, not a serializable Redis payload. Full restart resumption requires durable task input, DAG state, idempotency keys, and a registry that can recreate the appropriate execution callback.")

    heading(doc, "8. Configuration", 1)
    add_text(doc, "The scheduler reads these optional environment variables; defaults are used when they are absent.")
    add_table(doc, ["Variable", "Default", "Purpose"], [
        ("SCHEDULER_GLOBAL_SLOTS", "3", "Global concurrency limit."),
        ("SCHEDULER_TASK_SLOTS", "2", "Per-task concurrency limit."),
        ("SCHEDULER_TOKEN_BUDGET", "50000", "Per-task estimated token budget."),
        ("SCHEDULER_AGING_FACTOR", "0.002", "Priority gained per second of waiting."),
        ("SCHEDULER_MAX_PRIORITY", "10", "Upper bound for effective priority."),
        ("SCHEDULER_TIME_QUANTUM", "30", "Cooperative quantum exposed in events."),
        ("SCHEDULER_RETRY_LIMIT", "3", "Maximum quota/rate-limit attempts."),
    ], [3300, 1500, 4560])

    heading(doc, "9. Verification performed", 1)
    add_bullet(doc, "Python compilation passed for kernel and backend modules.")
    add_bullet(doc, "Frontend TypeScript checking passed with tsc --noEmit.")
    add_bullet(doc, "Resource-manager smoke test confirmed global and per-task slot behavior.")
    add_bullet(doc, "Scheduler concurrency smoke test confirmed independent jobs run concurrently up to the configured limit.")

    heading(doc, "10. Relevant source files", 1)
    add_table(doc, ["File", "Role"], [
        ("server/kernel/services/agent_scheduler.py", "Scheduler, resource manager, Redis persistence, events, and recovery scan."),
        ("server/kernel/graphs/main_agent_graph.py", "Submits dependency-ready DAG steps to the scheduler."),
        ("server/kernel/main.py", "Starts the scheduler during kernel startup."),
        ("frontend/hooks/useTaskSubscriptions.ts", "Maps scheduler events into task state and timeline entries."),
        ("frontend/components/activity/TaskActivity.tsx", "Displays scheduler status and metrics."),
        ("frontend/types/index.ts", "Frontend scheduler event and snapshot types."),
    ], [4200, 5160])

    doc.core_properties.title = "Global Agent Scheduler - AgentOS Technical Reference"
    doc.core_properties.subject = "Scheduler, resource manager, Redis events, and recovery behavior"
    doc.core_properties.author = "AgentOS"
    doc.save(OUT)
    print(OUT)


if __name__ == "__main__":
    build()
