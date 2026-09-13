import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { ConfirmDialogProvider } from './ConfirmDialog'
import { useConfirm } from './useConfirm'

function Harness({ tone = 'danger' }: { tone?: 'default' | 'danger' } = {}) {
  const confirm = useConfirm()
  const [result, setResult] = useState<string>('pending')

  return (
    <div>
      <p>Result: {result}</p>
      <button
        onClick={async () => {
          const confirmed = await confirm({
            title: 'Disconnect Booqable?',
            description: 'Features using this connection will stop working.',
            tone,
          })
          setResult(String(confirmed))
        }}
      >
        Disconnect
      </button>
    </div>
  )
}

describe('ConfirmDialogProvider / useConfirm', () => {
  it('resolves true when the confirm action is clicked, rendering the danger variant for a danger-tone confirm', async () => {
    const user = userEvent.setup()
    render(
      <ConfirmDialogProvider>
        <Harness />
      </ConfirmDialogProvider>,
    )

    await user.click(screen.getByRole('button', { name: 'Disconnect' }))
    const dialog = screen.getByRole('dialog', { name: 'Disconnect Booqable?' })
    expect(dialog).toHaveTextContent('Features using this connection will stop working.')
    expect(screen.getByRole('button', { name: 'Confirm' })).toHaveClass('bg-danger')

    await user.click(screen.getByRole('button', { name: 'Confirm' }))
    expect(await screen.findByText('Result: true')).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('resolves false when cancelled', async () => {
    const user = userEvent.setup()
    render(
      <ConfirmDialogProvider>
        <Harness />
      </ConfirmDialogProvider>,
    )

    await user.click(screen.getByRole('button', { name: 'Disconnect' }))
    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(await screen.findByText('Result: false')).toBeInTheDocument()
  })

  it('renders the primary variant (not danger) when tone is "default"', async () => {
    const user = userEvent.setup()
    render(
      <ConfirmDialogProvider>
        <Harness tone="default" />
      </ConfirmDialogProvider>,
    )

    await user.click(screen.getByRole('button', { name: 'Disconnect' }))
    expect(screen.getByRole('button', { name: 'Confirm' })).toHaveClass('bg-brand-solid')
  })
})
