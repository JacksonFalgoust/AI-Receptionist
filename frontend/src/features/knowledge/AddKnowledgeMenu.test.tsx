import { describe, expect, it } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

import { AddKnowledgeMenu } from './AddKnowledgeMenu'

function renderMenu() {
  render(
    <MemoryRouter>
      <AddKnowledgeMenu />
    </MemoryRouter>,
  )
}

async function openMenu() {
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: 'Add knowledge' }))
  return within(screen.getByRole('menu'))
}

describe('AddKnowledgeMenu', () => {
  it('keeps the actions behind one trigger until asked for', async () => {
    renderMenu()
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()

    const menu = await openMenu()
    expect(menu.getByRole('menuitem', { name: 'Create FAQ' })).toBeInTheDocument()
  })

  it('offers all six actions PRD §16.3 asks for', async () => {
    renderMenu()
    const menu = await openMenu()

    expect(menu.getAllByRole('menuitem').map((item) => item.textContent?.trim())).toEqual([
      'Create FAQ',
      'Add text',
      'Upload document',
      'Add URL',
      'Create policy',
      'Add business information',
    ])
  })

  it('seeds the editor with the type the action names', async () => {
    renderMenu()
    const menu = await openMenu()

    expect(menu.getByRole('menuitem', { name: 'Create FAQ' })).toHaveAttribute(
      'href',
      '/concierge/knowledge/new?type=faq',
    )
    expect(menu.getByRole('menuitem', { name: 'Create policy' })).toHaveAttribute(
      'href',
      '/concierge/knowledge/new?type=policy',
    )
    expect(menu.getByRole('menuitem', { name: 'Upload document' })).toHaveAttribute(
      'href',
      '/concierge/knowledge/new?type=document',
    )
    expect(menu.getByRole('menuitem', { name: 'Add URL' })).toHaveAttribute(
      'href',
      '/concierge/knowledge/new?type=url',
    )
  })

  it('leaves the type open for business information, so every type stays reachable', async () => {
    // Six actions cannot preselect ten types. This one opens the editor with
    // the Type field free, which is what keeps procedure, product, service,
    // pricing and location reachable at all.
    renderMenu()
    const menu = await openMenu()

    expect(menu.getByRole('menuitem', { name: 'Add business information' })).toHaveAttribute(
      'href',
      '/concierge/knowledge/new',
    )
  })

  it('promotes Upload document to a shortcut beside the menu', async () => {
    // The prototype puts uploading one click away rather than two; it stays in
    // the menu as well, so the six actions are listed together in one place.
    renderMenu()

    const shortcut = screen.getByRole('link', { name: 'Upload document' })
    expect(shortcut).toHaveAttribute('href', '/concierge/knowledge/new?type=document')
  })
})
