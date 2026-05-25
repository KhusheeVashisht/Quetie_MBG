import { _buildHeaders } from './api'

export async function createAdmin(payload: { username: string; password: string; email?: string; is_super_admin?: boolean }) {
  const resp = await fetch('/api/admins', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ..._buildHeaders('POST') },
    credentials: 'same-origin',
    body: JSON.stringify(payload),
  })
  if (!resp.ok) {
    const txt = await resp.text()
    throw new Error(txt || 'Create admin failed')
  }
  return resp.json()
}

export async function updateAdmin(adminId: number, payload: { email?: string | null; password?: string; is_active?: boolean; is_super_admin?: boolean }) {
  const resp = await fetch(`/api/admins/${adminId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ..._buildHeaders('PATCH') },
    credentials: 'same-origin',
    body: JSON.stringify(payload),
  })
  if (!resp.ok) throw new Error(await resp.text() || 'Update failed')
  return resp.json()
}

export async function deactivateAdmin(adminId: number) {
  const resp = await fetch(`/api/admins/${adminId}`, {
    method: 'DELETE',
    headers: _buildHeaders('DELETE'),
    credentials: 'same-origin',
  })
  if (!resp.ok) throw new Error(await resp.text() || 'Deactivate failed')
  return resp.json()
}

export async function permanentlyDeleteAdmin(adminId: number) {
  const resp = await fetch(`/api/admins/${adminId}/permanent`, {
    method: 'DELETE',
    headers: _buildHeaders('DELETE'),
    credentials: 'same-origin',
  })
  if (!resp.ok) throw new Error(await resp.text() || 'Delete failed')
  return resp.json()
}

export async function listRoles() {
  const resp = await fetch('/api/roles', { headers: _buildHeaders('GET'), credentials: 'same-origin' })
  if (!resp.ok) {
    if (resp.status === 401) throw new Error('Session expired. Please log in again.')
    if (resp.status === 403) throw new Error('Role catalog is only available to super admins.')
    throw new Error('Fetch roles failed')
  }
  return resp.json()
}

export async function assignRole(adminId: number, roleId: number) {
  const resp = await fetch(`/api/admins/${adminId}/roles/${roleId}`, { method: 'POST', headers: _buildHeaders('POST'), credentials: 'same-origin' })
  if (!resp.ok) throw new Error(await resp.text() || 'Assign role failed')
  return resp.json()
}

export async function removeRole(adminId: number, roleId: number) {
  const resp = await fetch(`/api/admins/${adminId}/roles/${roleId}`, { method: 'DELETE', headers: _buildHeaders('DELETE'), credentials: 'same-origin' })
  if (!resp.ok) throw new Error(await resp.text() || 'Remove role failed')
  return resp.json()
}

export async function listAdminDetails(adminId: number) {
  const resp = await fetch(`/api/admins/${adminId}`, { headers: _buildHeaders('GET'), credentials: 'same-origin' })
  if (!resp.ok) throw new Error(await resp.text() || 'Fetch admin failed')
  return resp.json()
}
