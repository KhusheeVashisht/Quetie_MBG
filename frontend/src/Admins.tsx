import React, { useEffect, useState } from 'react'
import { listAdmins } from './api'
import {
  assignRole,
  createAdmin,
  deactivateAdmin,
  listRoles,
  permanentlyDeleteAdmin,
  removeRole,
  updateAdmin,
} from './adminApi'

export default function Admins({ onChanged }: { onChanged?: () => void }) {
  const [admins, setAdmins] = useState<any[]>([])
  const [roles, setRoles] = useState<any[]>([])
  const [error, setError] = useState<string | null>(null)
  const [rolesNotice, setRolesNotice] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [showCreate, setShowCreate] = useState(false)
  const [editingAdminId, setEditingAdminId] = useState<number | null>(null)
  const [assignRoleByAdmin, setAssignRoleByAdmin] = useState<Record<number, string>>({})
  const [newUsername, setNewUsername] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [newEmail, setNewEmail] = useState('')
  const [newAccessTier, setNewAccessTier] = useState<'moderator' | 'super_admin'>('moderator')
  const [editEmail, setEditEmail] = useState('')
  const [editPassword, setEditPassword] = useState('')
  const [editIsActive, setEditIsActive] = useState(true)
  const [editAccessTier, setEditAccessTier] = useState<'moderator' | 'super_admin'>('moderator')

  const assignableRoles = roles.filter(role => role.name !== 'super_admin')

  const refresh = async () => {
    setLoading(true)
    setError(null)
    setRolesNotice(null)
    try {
      const adminData = await listAdmins()
      setAdmins(adminData.admins || [])
      try {
        const roleData = await listRoles()
        setRoles(roleData.roles || [])
      } catch (roleErr: any) {
        setRoles([])
        setRolesNotice(roleErr?.message || 'Role catalog unavailable.')
      }
      onChanged?.()
    } catch (err: any) {
      setError(err.message || 'Failed to load admins')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  const startEdit = (admin: any) => {
    setEditingAdminId(admin.id)
    setEditEmail(admin.email || '')
    setEditPassword('')
    setEditIsActive(!!admin.is_active)
    setEditAccessTier(admin.is_super_admin ? 'super_admin' : 'moderator')
  }

  const submitCreate = async (event: React.FormEvent) => {
    event.preventDefault()
    setError(null)
    try {
      await createAdmin({ username: newUsername.trim(), password: newPassword, email: newEmail.trim() || undefined, is_super_admin: newAccessTier === 'super_admin' })
      setNewUsername('')
      setNewPassword('')
      setNewEmail('')
      setNewAccessTier('moderator')
      setShowCreate(false)
      await refresh()
    } catch (err: any) {
      setError(err.message || 'Create failed')
    }
  }

  const submitUpdate = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!editingAdminId) return
    setError(null)
    try {
      await updateAdmin(editingAdminId, {
        email: editEmail.trim() || null,
        password: editPassword.trim() || undefined,
        is_active: editIsActive,
        is_super_admin: editAccessTier === 'super_admin',
      })
      setEditingAdminId(null)
      await refresh()
    } catch (err: any) {
      setError(err.message || 'Update failed')
    }
  }

  const handleDeactivate = async (admin: any) => {
    if (!window.confirm(`Revoke access for ${admin.username}?`)) return
    setError(null)
    try {
      await deactivateAdmin(admin.id)
      await refresh()
    } catch (err: any) {
      setError(err.message || 'Deactivate failed')
    }
  }

  const handleDelete = async (admin: any) => {
    if (!window.confirm(`Permanently delete ${admin.username}?`)) return
    setError(null)
    try {
      await permanentlyDeleteAdmin(admin.id)
      await refresh()
    } catch (err: any) {
      setError(err.message || 'Delete failed')
    }
  }

  const handleAssignRole = async (adminId: number) => {
    const roleId = Number(assignRoleByAdmin[adminId])
    if (!roleId) return
    setError(null)
    try {
      await assignRole(adminId, roleId)
      setAssignRoleByAdmin(prev => ({ ...prev, [adminId]: '' }))
      await refresh()
    } catch (err: any) {
      setError(err.message || 'Assign role failed')
    }
  }

  const handleRemoveRole = async (adminId: number, roleId: number) => {
    setError(null)
    try {
      await removeRole(adminId, roleId)
      await refresh()
    } catch (err: any) {
      setError(err.message || 'Remove role failed')
    }
  }

  return (
    <section className="panel">
      <div className="panel__header">
        <div>
          <h3>RBAC</h3>
          <p>Manage admin accounts, roles, and access level safely from the private dashboard.</p>
        </div>
        <div className="panel__actions">
          <button className="button button--ghost" type="button" onClick={() => void refresh()}>
            Refresh
          </button>
          <button className="button" type="button" onClick={() => setShowCreate(v => !v)}>
            {showCreate ? 'Close create form' : 'New admin'}
          </button>
        </div>
      </div>

      {error && <div className="notice notice--error">{error}</div>}
      {rolesNotice && !error && <div className="notice notice--info">{rolesNotice}</div>}
      {loading && <div className="skeleton-row" />}

      {showCreate && (
        <form className="stack-form admin-form" onSubmit={submitCreate}>
          <div className="grid-2">
            <input className="field" placeholder="Username" value={newUsername} onChange={e => setNewUsername(e.target.value)} />
            <input className="field" placeholder="Email" value={newEmail} onChange={e => setNewEmail(e.target.value)} />
          </div>
          <input className="field" placeholder="Temporary password" type="password" value={newPassword} onChange={e => setNewPassword(e.target.value)} />
          <label className="field-group">
            Access tier
            <select className="field" value={newAccessTier} onChange={e => setNewAccessTier(e.target.value as 'moderator' | 'super_admin')}>
              <option value="moderator">Moderator</option>
              <option value="super_admin">Super admin</option>
            </select>
            <small>New users are created as moderators by default. Super admin can create users; moderators cannot.</small>
          </label>
          <button className="button" type="submit">Create admin</button>
        </form>
      )}

      {editingAdminId !== null && (
        <form className="stack-form admin-form" onSubmit={submitUpdate}>
          <div className="panel__header panel__header--compact">
            <div>
              <h4>Edit admin</h4>
              <p>Leave password blank to keep the current one.</p>
            </div>
            <button className="button button--ghost" type="button" onClick={() => setEditingAdminId(null)}>
              Cancel
            </button>
          </div>
          <div className="grid-2">
            <label className="field-group">
              Email
              <input className="field" value={editEmail} onChange={e => setEditEmail(e.target.value)} />
            </label>
            <label className="field-group">
              New password
              <input className="field" type="password" value={editPassword} onChange={e => setEditPassword(e.target.value)} />
            </label>
          </div>
          <div className="row-actions row-actions--left">
            <label className="checkbox-row"><input type="checkbox" checked={editIsActive} onChange={e => setEditIsActive(e.target.checked)} /> Active</label>
            <label className="field-group field-group--inline">
              Access tier
              <select className="field field--select" value={editAccessTier} onChange={e => setEditAccessTier(e.target.value as 'moderator' | 'super_admin')}>
                <option value="moderator">Moderator</option>
                <option value="super_admin">Super admin</option>
              </select>
            </label>
          </div>
          <p className="field-hint">Super admin can create users and manage access. Moderator can manage queue and filters, but cannot create new users.</p>
          <button className="button" type="submit">Save admin</button>
        </form>
      )}

      <div className="table-shell table-shell--admins">
        <table>
          <thead>
            <tr>
              <th>User</th>
              <th>Contact</th>
              <th>Flags</th>
              <th>Roles</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {admins.length === 0 && !loading && (
              <tr>
                <td colSpan={5}><div className="empty-state">No admin users found.</div></td>
              </tr>
            )}
            {admins.map(admin => (
              <tr key={admin.id}>
                <td>
                  <strong>{admin.username}</strong>
                  <small>{admin.created_at ? `Created ${new Date(admin.created_at).toLocaleDateString()}` : ''}</small>
                </td>
                <td>{admin.email || '—'}</td>
                <td>
                  <div className="row-badges">
                    <Pill tone={admin.is_active ? 'success' : 'danger'}>{admin.is_active ? 'active' : 'inactive'}</Pill>
                    <Pill tone={admin.is_super_admin ? 'info' : 'neutral'}>{admin.is_super_admin ? 'super admin' : 'moderator'}</Pill>
                  </div>
                </td>
                <td>
                  <div className="role-stack">
                    <div className="row-badges">
                      {(admin.roles || []).filter((role: any) => role.name !== 'super_admin').map((role: any) => (
                        <span className="pill pill--neutral" key={role.id}>
                          {role.name}
                          <button className="pill__close" type="button" onClick={() => void handleRemoveRole(admin.id, role.id)}>
                            ×
                          </button>
                        </span>
                      ))}
                    </div>
                    <div className="inline-form inline-form--compact">
                      <select className="field field--select" value={assignRoleByAdmin[admin.id] || ''} onChange={e => setAssignRoleByAdmin(prev => ({ ...prev, [admin.id]: e.target.value }))}>
                        <option value="">Custom role</option>
                        {assignableRoles.map(role => (
                          <option key={role.id} value={role.id}>{role.name}</option>
                        ))}
                      </select>
                      <button className="button button--ghost" type="button" onClick={() => void handleAssignRole(admin.id)}>
                        Add
                      </button>
                    </div>
                    <small className="field-hint">Access tier is separate: moderator or super admin. Only super admin can create users.</small>
                  </div>
                </td>
                <td>
                  <div className="row-actions row-actions--wrap">
                    <button className="button button--ghost" type="button" onClick={() => startEdit(admin)}>Edit</button>
                    <button className="button button--ghost" type="button" onClick={() => void handleDeactivate(admin)} disabled={!admin.is_active}>Revoke</button>
                    <button className="button button--danger" type="button" onClick={() => void handleDelete(admin)}>Delete</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function Pill({ tone = 'neutral', children }: { tone?: 'neutral' | 'success' | 'warning' | 'danger' | 'info'; children: React.ReactNode }) {
  return <span className={`pill pill--${tone}`}>{children}</span>
}
