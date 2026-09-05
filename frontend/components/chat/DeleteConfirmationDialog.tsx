"use client";

import { useEffect, useState } from "react";

import type { DeleteConfirmation } from "@/types";

import {
  respondToDeleteConfirmation,
} from "@/api/tasks";

type DeleteConfirmationDialogProps = {
  confirmation: DeleteConfirmation | null;
  onClose?: () => void;
};

// ---------------------------------------------------------------------------
// Delete confirmation dialog
// ---------------------------------------------------------------------------

export function DeleteConfirmationDialog({
  confirmation,
  onClose,
}: DeleteConfirmationDialogProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isOpen, setIsOpen] = useState(true);

  // -------------------------------------------------------------------------
  // IMPORTANT:
  //
  // Every new confirmation gets a fresh dialog.
  // -------------------------------------------------------------------------

  useEffect(() => {
    if (confirmation) {
      setIsOpen(true);
      setError(null);
      setIsSubmitting(false);
    }
  }, [confirmation?.confirmationId]);

  if (!confirmation || !isOpen) {
    return null;
  }

  async function handleConfirmation(
    confirmed: boolean,
  ) {
    if (isSubmitting) {
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      await respondToDeleteConfirmation(
        confirmation.reqId,
        confirmation.taskId,
        confirmation.confirmationId,
        confirmed,
      );
    } catch {
      setError(
        confirmed
          ? "The file could not be deleted. Please try again."
          : "The cancellation could not be completed. Please try again.",
      );

      setIsSubmitting(false);
      return;
    }

    // -----------------------------------------------------------------------
    // Backend successfully accepted the operation.
    //
    // Hide the dialog immediately.
    //
    // The WebSocket will separately receive:
    //   DELETE_COMPLETED
    //   DELETE_CANCELLED
    //   DELETE_FAILED
    //
    // and update task state.
    // -----------------------------------------------------------------------

    setIsSubmitting(false);
    setIsOpen(false);

    // Call parent callback only if one was actually provided.
    onClose?.();
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-5"
      role="dialog"
      aria-modal="true"
      aria-labelledby="delete-confirmation-title"
    >
      <div className="w-full max-w-[520px] rounded-[8px] border border-[#deded9] bg-[#fafaf8] p-6 shadow-xl">

        <h2
          id="delete-confirmation-title"
          className="m-0 mb-2 text-lg font-semibold text-[#1e1e1c]"
        >
          Confirm deletion
        </h2>

        <p className="mb-4 text-sm leading-[1.6] text-[#5a5a54]">
          AgentOS wants to delete the following file:
        </p>

        <div className="mb-5 rounded-[5px] border border-[#deded9] bg-[#f0f0ec] px-3 py-2.5">
          <p className="m-0 break-all font-mono text-xs leading-[1.6] text-[#3f3f3a]">
            {confirmation.path}
          </p>
        </div>

        {confirmation.recursive && (
          <p className="mb-4 text-sm font-medium text-[#b84343]">
            This operation will recursively delete the selected directory and
            its contents.
          </p>
        )}

        <p className="mb-5 text-sm leading-[1.6] text-[#74746f]">
          This action is destructive and cannot be automatically undone.
        </p>

        {error && (
          <p className="mb-4 text-sm leading-[1.5] text-[#b84343]">
            {error}
          </p>
        )}

        <div className="flex justify-end gap-2.5">

          <button
            type="button"
            disabled={isSubmitting}
            onClick={() => handleConfirmation(false)}
            className="
              rounded-[5px]
              border border-[#cfcfca]
              bg-[#fafaf8]
              px-4 py-2
              text-sm
              text-[#3f3f3a]
              transition
              hover:bg-[#f0f0ec]
              disabled:cursor-not-allowed
              disabled:opacity-50
            "
          >
            Cancel
          </button>

          <button
            type="button"
            disabled={isSubmitting}
            onClick={() => handleConfirmation(true)}
            className="
              rounded-[5px]
              border border-[#b84343]
              bg-[#b84343]
              px-4 py-2
              text-sm
              font-medium
              text-white
              transition
              hover:opacity-90
              disabled:cursor-not-allowed
              disabled:opacity-50
            "
          >
            {isSubmitting ? "Processing…" : "Delete"}
          </button>

        </div>
      </div>
    </div>
  );
}