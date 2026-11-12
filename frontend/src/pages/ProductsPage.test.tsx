import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { resetStore } from '@/mocks/store'
import { AppError } from '@/services/errors'
import { productService, resetMockProducts } from '@/services/productService'
import { renderWithProviders, seedSession } from '@/test/renderWithProviders'

import { ProductsPage } from './ProductsPage'

describe('ProductsPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    resetStore()
    resetMockProducts()
    seedSession()
  })

  it('lists products and filters by search', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ProductsPage />)
    expect(await screen.findByText('Canoe')).toBeInTheDocument()
    await user.type(screen.getByLabelText('Search products'), 'tent')
    expect(await screen.findByText('6-person Tent')).toBeInTheDocument()
    await vi.waitFor(() => expect(screen.queryByText('Canoe')).not.toBeInTheDocument())
  })

  it('adds a product', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ProductsPage />)
    await screen.findByText('Canoe')
    await user.click(screen.getByRole('button', { name: 'Add product' }))
    const dialog = screen.getByRole('dialog', { name: 'Add product' })
    await user.type(within(dialog).getByLabelText('Name'), 'Kayak')
    await user.clear(within(dialog).getByLabelText('Price (USD)'))
    await user.type(within(dialog).getByLabelText('Price (USD)'), '30')
    await user.click(within(dialog).getByRole('button', { name: 'Add product' }))
    expect(await screen.findByText('Kayak')).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('requires a name', async () => {
    const user = userEvent.setup()
    const create = vi.spyOn(productService, 'create')
    renderWithProviders(<ProductsPage />)
    await screen.findByText('Canoe')
    await user.click(screen.getByRole('button', { name: 'Add product' }))
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Add product' }))
    expect(screen.getByText('Name is required.')).toBeInTheDocument()
    expect(create).not.toHaveBeenCalled()
  })

  it('edits a product without offering creation-only fields', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ProductsPage />)
    await screen.findByText('Canoe')
    await user.click(screen.getByRole('button', { name: 'Edit Canoe' }))
    const dialog = screen.getByRole('dialog', { name: 'Edit product' })
    expect(within(dialog).queryByLabelText('Tracking')).not.toBeInTheDocument()
    const name = within(dialog).getByLabelText('Name')
    await user.clear(name)
    await user.type(name, 'Big Canoe')
    await user.click(within(dialog).getByRole('button', { name: 'Save changes' }))
    expect(await screen.findByText('Big Canoe')).toBeInTheDocument()
  })

  it('deletes a product after confirming', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ProductsPage />)
    await screen.findByText('Paddle')
    await user.click(screen.getByRole('button', { name: 'Delete Paddle' }))
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Delete' }))
    await vi.waitFor(() => expect(screen.queryByText('Paddle')).not.toBeInTheDocument())
  })

  it('keeps the product when delete is cancelled', async () => {
    const user = userEvent.setup()
    const remove = vi.spyOn(productService, 'remove')
    renderWithProviders(<ProductsPage />)
    await screen.findByText('Paddle')
    await user.click(screen.getByRole('button', { name: 'Delete Paddle' }))
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Cancel' }))
    expect(remove).not.toHaveBeenCalled()
    expect(screen.getByText('Paddle')).toBeInTheDocument()
  })

  it('shows the save error inside the form', async () => {
    const user = userEvent.setup()
    vi.spyOn(productService, 'create').mockRejectedValue(
      new AppError({ kind: 'validation', title: 'Invalid', description: 'SKU already taken.' }),
    )
    renderWithProviders(<ProductsPage />)
    await screen.findByText('Canoe')
    await user.click(screen.getByRole('button', { name: 'Add product' }))
    const dialog = screen.getByRole('dialog')
    await user.type(within(dialog).getByLabelText('Name'), 'X')
    await user.click(within(dialog).getByRole('button', { name: 'Add product' }))
    expect(await within(dialog).findByText('SKU already taken.')).toBeInTheDocument()
  })
})
