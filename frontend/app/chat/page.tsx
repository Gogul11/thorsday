'use client'

import { useEffect, useState } from 'react'

import ChatPanel from '@/components/chat/ChatPanel'
import { TaskActivity } from '@/components/activity/TaskActivity'
import { TaskList } from '@/components/sidebar/TaskList'
import { useTaskSubscriptions } from '@/hooks/useTaskSubscriptions'
import { createTask, getTasks, getTask } from '@/api/tasks'
import type { TaskRecord } from '@/types'

export default function ChatPage () {
  const [tasks, setTasks] = useState<TaskRecord[]>([])
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  // Subscribe to live events for any running/queued tasks
  useTaskSubscriptions(tasks, setTasks)

  // ---------------------------------------------------------------------------
  // Load task history on mount (GPT-style sidebar)
  // ---------------------------------------------------------------------------
  useEffect(() => {
    async function loadHistory () {
      try {
        const history = await getTasks()
        setTasks(
          history.map(t => ({
            ...t,
            req_id: '', // no active WS for historical tasks
            events: [], // event timeline not stored in summary
            messages: (t as TaskRecord).messages ?? []
          }))
        )
      } catch {
        // History is non-critical — silently ignore fetch errors
      }
    }
    void loadHistory()
  }, [])

  // ---------------------------------------------------------------------------
  // When user selects a task from sidebar — fetch full details (messages)
  // ---------------------------------------------------------------------------
  async function handleSelectTask (taskId: string) {
    setSelectedTaskId(taskId)

    // Check if we already have messages loaded for this task
    const existing = tasks.find(t => t.task_id === taskId)
    const existing = tasks.find(
      t =>
        (t.task_id && t.task_id === taskId) || (t.req_id && t.req_id === taskId)
    )
    if (existing && existing.messages.length > 0) return

    // Fetch full task including messages[]
    const full = await getTask(taskId)
    if (!full) return
    // Only fetch from backend if we have a real persistent task_id
    const persistentId = existing?.task_id || taskId
    if (!persistentId || (existing && persistentId === existing.req_id)) return

    setTasks(current =>
      current.map(t =>
        t.task_id === taskId
          ? { ...t, messages: full.messages ?? [], response: full.response }
          : t
      )
    )
    try {
      // Fetch full task including messages[]
      const full = await getTask(persistentId)
      if (!full) return

      setTasks(current =>
        current.map(t =>
          (t.task_id && t.task_id === persistentId) ||
          (existing?.req_id && t.req_id === existing.req_id)
            ? { ...t, messages: full.messages ?? [], response: full.response }
            : t
        )
      )
    } catch {
      // ignore
    }
  }

  // ---------------------------------------------------------------------------
  // Submit a new task or follow-up
  // ---------------------------------------------------------------------------
  const selectedTask = tasks.find(t => t.task_id === selectedTaskId)
  const selectedTask = tasks.find(
    t =>
      (t.task_id && t.task_id === selectedTaskId) ||
      (t.req_id && t.req_id === selectedTaskId)
  )

  async function submitTask (prompt: string) {
    setIsSubmitting(true)
    setSubmitError(null)

    // If a task is selected and completed, treat as follow-up on that task
    const followUpTaskId =
      selectedTask && selectedTask.status === 'completed'
        ? selectedTask.task_id
        : ''

    try {
      const created = await createTask(prompt, followUpTaskId)

      if (followUpTaskId) {
        // Follow-up: update the existing task back to running with new req_id
        // and append the human message optimistically so UI feels instant
        setTasks(current =>
          current.map(t =>
            t.task_id === followUpTaskId
              ? {
                  ...t,
                  req_id: created.req_id,
                  status: 'queued',
                  error: null,
                  messages: [
                    ...t.messages,
                    {
                      role: 'human' as const,
                      content: prompt,
                      timestamp: new Date().toISOString()
                    }
                  ]
                }
              : t
          )
        )
      } else {
        // New task
        const task: TaskRecord = {
          task_id: '', // filled in by kernel's task.CREATED event
          req_id: created.req_id,
          title: prompt.slice(0, 80),
          created_at: new Date().toISOString(),
          status: created.status,
          messages: [
            {
              role: 'human',
              content: prompt,
              timestamp: new Date().toISOString()
            }
          ],
          response: null,
          error: null,
          events: [],
          plan: []
        }

        setTasks(current => [task, ...current])
        // Select by req_id temporarily — will be updated to task_id once
        // the kernel sends task.CREATED with the real task_id
        setSelectedTaskId(created.req_id)
      }
    } catch (error) {
      setSubmitError(
        error instanceof Error ? error.message : 'Could not submit task.'
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  // Once the kernel fills in task_id for a newly created task, update
  // the selectedTaskId from the temporary req_id to the real task_id
  useEffect(() => {
    if (!selectedTaskId) return
    const task = tasks.find(
      t =>
        t.req_id === selectedTaskId && t.task_id && t.task_id !== selectedTaskId
    )
    if (task) {
      setSelectedTaskId(task.task_id)
    }
  }, [tasks, selectedTaskId])

  return (
    <main
      className={`grid h-dvh min-h-screen overflow-hidden ${
        sidebarCollapsed
          ? 'grid-cols-[64px_minmax(420px,1fr)_310px]'
          : 'grid-cols-[228px_minmax(420px,1fr)_310px]'
      }`}
    >
      <TaskList
        tasks={tasks}
        selectedTaskId={selectedTaskId ?? ''}
        onSelect={handleSelectTask}
        onNewTask={() => {
          setSelectedTaskId(null)
          setSidebarCollapsed(false)
        }}
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed(c => !c)}
      />

      <ChatPanel
        selectedTask={selectedTask}
        selectedTask={selectedTask ?? null}
        isSubmitting={isSubmitting}
        submitError={submitError}
        onSubmit={submitTask}
        onDeleteConfirmationClose={() => {
          if (selectedTask) {
            setTasks(current =>
              current.map(t =>
                (selectedTask.task_id && t.task_id === selectedTask.task_id) ||
                (selectedTask.req_id && t.req_id === selectedTask.req_id)
                  ? { ...t, delete_confirmation: null }
                  : t
              )
            )
          }
        }}
      />

      <TaskActivity task={selectedTask} />
    </main>
  )
}
