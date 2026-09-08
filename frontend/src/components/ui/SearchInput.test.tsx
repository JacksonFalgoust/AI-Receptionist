import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { render, screen, act, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { SearchInput } from './SearchInput'

function Harness({ onSearch }: { onSearch: (value: string) => void }) {
  const [value, setValue] = useState('')
  return (
    <SearchInput value={value} onChange={setValue} onSearch={onSearch} aria-label="Search conversations" />
  )
}

describe('SearchInput', () => {
  it('reflects typed input immediately via onChange', async () => {
    const user = userEvent.setup()
    render(<Harness onSearch={vi.fn()} />)
    await user.type(screen.getByLabelText('Search conversations'), 'Dana')
    expect(screen.getByLabelText('Search conversations')).toHaveValue('Dana')
  })

  it('calls onSearch only after the debounce window elapses with no further typing', async () => {
    vi.useFakeTimers()
    const onSearch = vi.fn()
    render(<Harness onSearch={onSearch} />)

    const input = screen.getByLabelText('Search conversations') as HTMLInputElement
    fireEvent.change(input, { target: { value: 'Dana' } })
    expect(onSearch).not.toHaveBeenCalledWith('Dana')

    await act(() => {
      vi.advanceTimersByTime(300)
    })
    expect(onSearch).toHaveBeenLastCalledWith('Dana')
    vi.useRealTimers()
  })

  it('cancels a pending debounce call when the value changes again before the delay elapses', () => {
    vi.useFakeTimers()
    const onSearch = vi.fn()
    render(<Harness onSearch={onSearch} />)
    const input = screen.getByLabelText('Search conversations')

    fireEvent.change(input, { target: { value: 'D' } })
    act(() => {
      vi.advanceTimersByTime(200) // well under the 300ms debounce window
    })
    fireEvent.change(input, { target: { value: 'Dana' } })
    act(() => {
      vi.advanceTimersByTime(300)
    })

    expect(onSearch).toHaveBeenCalledTimes(1)
    expect(onSearch).toHaveBeenCalledWith('Dana')
    vi.useRealTimers()
  })

  it('does not call onSearch on mount even after the debounce window elapses, when the value never changes', () => {
    vi.useFakeTimers()
    const onSearch = vi.fn()
    render(<SearchInput value="Dana" onChange={() => {}} onSearch={onSearch} aria-label="Search conversations" />)

    act(() => {
      vi.advanceTimersByTime(300)
    })

    expect(onSearch).not.toHaveBeenCalled()
    vi.useRealTimers()
  })

  it('does not reset or re-fire the debounce when the parent re-renders with a fresh onSearch identity', () => {
    vi.useFakeTimers()
    const onSearchA = vi.fn()
    const { rerender } = render(
      <SearchInput value="" onChange={() => {}} onSearch={onSearchA} aria-label="Search conversations" />,
    )
    // Establish the mount-skip before the value ever changes.
    act(() => {
      vi.advanceTimersByTime(300)
    })
    expect(onSearchA).not.toHaveBeenCalled()

    rerender(<SearchInput value="Dana" onChange={() => {}} onSearch={onSearchA} aria-label="Search conversations" />)
    act(() => {
      vi.advanceTimersByTime(150) // partway through the debounce window
    })

    // Parent re-renders with a brand-new inline onSearch identity, but the
    // value hasn't changed — this must not reset the pending timer.
    const onSearchB = vi.fn()
    rerender(<SearchInput value="Dana" onChange={() => {}} onSearch={onSearchB} aria-label="Search conversations" />)
    act(() => {
      vi.advanceTimersByTime(150) // remainder of the debounce window
    })

    expect(onSearchB).toHaveBeenCalledTimes(1)
    expect(onSearchB).toHaveBeenCalledWith('Dana')
    expect(onSearchA).not.toHaveBeenCalled()
    vi.useRealTimers()
  })
})
