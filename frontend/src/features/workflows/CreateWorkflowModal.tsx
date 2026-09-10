import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { Button } from '@/components/ui/Button'
import { Field } from '@/components/ui/Field'
import { Input } from '@/components/ui/Input'
import { Modal } from '@/components/ui/Modal'
import { Textarea } from '@/components/ui/Textarea'
import { useToast } from '@/components/ui/ToastProvider'
import { paths } from '@/routes/paths'
import { toAppError } from '@/services/errors'
import { workflowService } from '@/services/workflowService'
import type { Workflow } from '@/types'

/** Shared with `WorkflowsPage`'s list query, so a created workflow appears immediately if the user comes back. */
export const WORKFLOWS_KEY = ['workflows']

export interface CreateWorkflowModalProps {
  isOpen: boolean
  onClose: () => void
}

/**
 * US-8.1's Create workflow CTA. `workflowService.create` only needs a name,
 * so this is a two-field form rather than a full page — the workflow lands
 * as a draft and the admin is handed straight to US-8.2's editor (still a
 * stub until C7, the same handoff C1 made to C2).
 */
export function CreateWorkflowModal({ isOpen, onClose }: CreateWorkflowModalProps) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [nameError, setNameError] = useState<string | null>(null)
  const queryClient = useQueryClient()
  const toast = useToast()
  const navigate = useNavigate()

  const create = useMutation({
    mutationFn: () =>
      workflowService.create({
        name: name.trim(),
        description: description.trim() || undefined,
      }),
    onSuccess: (workflow) => {
      queryClient.setQueryData<Workflow[]>(WORKFLOWS_KEY, (current) =>
        current ? [workflow, ...current] : [workflow],
      )
      toast.show('Workflow created.', { tone: 'success' })
      reset()
      onClose()
      navigate(paths.workflow(workflow.id))
    },
    onError: (error) => {
      toast.show(toAppError(error).description, { tone: 'danger' })
    },
  })

  function reset() {
    setName('')
    setDescription('')
    setNameError(null)
  }

  function handleClose() {
    // A create in flight must land before the dialog can be dismissed — a
    // delayed success firing after Cancel would otherwise force-navigate the
    // user away and toast a creation they believed they'd called off.
    if (create.isPending) return
    reset()
    onClose()
  }

  function handleSubmit() {
    if (!name.trim()) {
      setNameError('Name is required.')
      return
    }
    setNameError(null)
    create.mutate()
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="Create workflow"
      actions={
        <>
          <Button variant="ghost" onClick={handleClose} disabled={create.isPending}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} isLoading={create.isPending}>
            Create workflow
          </Button>
        </>
      }
    >
      <Field label="Name" htmlFor="workflow-name" error={nameError ?? undefined}>
        <Input
          value={name}
          onChange={(event) => {
            setName(event.target.value)
            setNameError(null)
          }}
          autoFocus
        />
      </Field>
      <Field label="Description (optional)" htmlFor="workflow-description">
        <Textarea
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          rows={3}
        />
      </Field>
    </Modal>
  )
}
