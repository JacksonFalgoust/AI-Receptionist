/**
 * Coordinates Escape-key handling across stacked overlays (Modal, Drawer,
 * Dropdown, ConfirmDialog via Modal). Without this, an Escape press while
 * e.g. a ConfirmDialog is open on top of a Drawer would fire both overlays'
 * handlers — the dialog resolves AND the drawer underneath closes. Only the
 * most-recently-registered (topmost) handler should respond.
 */
let stack: symbol[] = []

export function pushEscapeHandler(): symbol {
  const id = Symbol()
  stack = [...stack, id]
  return id
}

export function popEscapeHandler(id: symbol): void {
  stack = stack.filter((entry) => entry !== id)
}

export function isTopEscapeHandler(id: symbol): boolean {
  return stack[stack.length - 1] === id
}
