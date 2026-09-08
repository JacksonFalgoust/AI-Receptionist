import { describe, expect, it } from 'vitest'

import { can, canAny, PERMISSIONS } from './permissions'

describe('permissions', () => {
  it('grants owners and administrators everything', () => {
    for (const permission of PERMISSIONS) {
      expect(can('owner', permission)).toBe(true)
      expect(can('administrator', permission)).toBe(true)
    }
  })

  it('withholds billing, user admin, and security from managers (PRD 4.2)', () => {
    expect(can('manager', 'manage:billing')).toBe(false)
    expect(can('manager', 'manage:users')).toBe(false)
    expect(can('manager', 'view:security')).toBe(false)
    expect(can('manager', 'view:conversations')).toBe(true)
  })

  it('limits analysts to reporting, with no configuration access', () => {
    expect(can('analyst', 'view:analytics')).toBe(true)
    expect(can('analyst', 'manage:configuration')).toBe(false)
    expect(can('analyst', 'manage:workflows')).toBe(false)
  })

  it('gives viewers no management capability at all', () => {
    const managePermissions = PERMISSIONS.filter((p) => p.startsWith('manage:'))
    expect(canAny('viewer', managePermissions)).toBe(false)
  })
})
