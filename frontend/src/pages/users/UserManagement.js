import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
  MenuItem,
  Chip,
  IconButton,
  Tooltip,
  Snackbar,
  Alert,
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import BlockIcon from '@mui/icons-material/Block';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import DataTable from '../../components/common/DataTable';
import ConfirmDialog from '../../components/common/ConfirmDialog';
import api from '../../api/axios';

const ROLES = [
  { value: 'super_admin', label: 'Super Admin' },
  { value: 'hr', label: 'HR' },
  { value: 'it_specialist', label: 'IT Specialist' },
  { value: 'employee', label: 'Employee' },
];

const ROLE_COLORS = {
  super_admin: 'error',
  hr: 'secondary',
  it_specialist: 'primary',
  employee: 'default',
};

const EMPTY_FORM = { full_name: '', email: '', password: '', role: 'employee' };

function UserManagement() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editUser, setEditUser] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [confirmDialog, setConfirmDialog] = useState({ open: false, user: null });
  const [snack, setSnack] = useState({ open: false, msg: '', severity: 'success' });

  const showSnack = (msg, severity = 'success') =>
    setSnack({ open: true, msg, severity });

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/auth/users/');
      const data = Array.isArray(res.data) ? res.data : res.data.results || [];
      setRows(data.map((u) => ({ ...u, id: u.id || u.pk })));
    } catch {
      showSnack('Failed to load users.', 'error');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  const openAdd = () => {
    setEditUser(null);
    setForm(EMPTY_FORM);
    setDialogOpen(true);
  };

  const openEdit = (user) => {
    setEditUser(user);
    setForm({ full_name: user.full_name || '', email: user.email, password: '', role: user.role });
    setDialogOpen(true);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      if (editUser) {
        const payload = { full_name: form.full_name, role: form.role };
        if (form.password) payload.password = form.password;
        await api.patch(`/auth/users/${editUser.id}/`, payload);
        showSnack('User updated successfully.');
      } else {
        await api.post('/auth/users/', form);
        showSnack('User created successfully.');
      }
      setDialogOpen(false);
      fetchUsers();
    } catch (err) {
      const msg = err.response?.data?.email?.[0] || err.response?.data?.detail || 'Save failed.';
      showSnack(msg, 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleToggleActive = async () => {
    const user = confirmDialog.user;
    try {
      await api.patch(`/auth/users/${user.id}/`, { is_active: !user.is_active });
      showSnack(`User ${user.is_active ? 'deactivated' : 'activated'}.`);
      fetchUsers();
    } catch {
      showSnack('Action failed.', 'error');
    } finally {
      setConfirmDialog({ open: false, user: null });
    }
  };

  const columns = [
    { field: 'full_name', headerName: 'Full Name', flex: 1, minWidth: 150 },
    { field: 'email', headerName: 'Email', flex: 1.5, minWidth: 200 },
    {
      field: 'role',
      headerName: 'Role',
      width: 150,
      renderCell: ({ value }) => (
        <Chip
          label={(value || '').replace('_', ' ')}
          color={ROLE_COLORS[value] || 'default'}
          size="small"
          sx={{ textTransform: 'capitalize' }}
        />
      ),
    },
    {
      field: 'is_active',
      headerName: 'Status',
      width: 110,
      renderCell: ({ value }) => (
        <Chip
          label={value ? 'Active' : 'Inactive'}
          color={value ? 'success' : 'default'}
          size="small"
        />
      ),
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 120,
      sortable: false,
      renderCell: ({ row }) => (
        <Box>
          <Tooltip title="Edit Role">
            <IconButton size="small" onClick={() => openEdit(row)}>
              <EditIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title={row.is_active ? 'Deactivate' : 'Activate'}>
            <IconButton
              size="small"
              color={row.is_active ? 'error' : 'success'}
              onClick={() => setConfirmDialog({ open: true, user: row })}
            >
              {row.is_active ? (
                <BlockIcon fontSize="small" />
              ) : (
                <CheckCircleIcon fontSize="small" />
              )}
            </IconButton>
          </Tooltip>
        </Box>
      ),
    },
  ];

  return (
    <Box>
      <DataTable
        title="User Management"
        rows={rows}
        columns={columns}
        loading={loading}
        onAdd={openAdd}
        addLabel="Add User"
        searchable
      />

      {/* Add / Edit Dialog */}
      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editUser ? 'Edit User' : 'Add New User'}</DialogTitle>
        <DialogContent sx={{ pt: '12px !important' }}>
          <TextField
            label="Full Name"
            fullWidth
            margin="normal"
            value={form.full_name}
            onChange={(e) => setForm({ ...form, full_name: e.target.value })}
          />
          <TextField
            label="Email"
            type="email"
            fullWidth
            margin="normal"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            disabled={!!editUser}
          />
          <TextField
            label={editUser ? 'New Password (leave blank to keep)' : 'Password'}
            type="password"
            fullWidth
            margin="normal"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            required={!editUser}
          />
          <TextField
            select
            label="Role"
            fullWidth
            margin="normal"
            value={form.role}
            onChange={(e) => setForm({ ...form, role: e.target.value })}
          >
            {ROLES.map((r) => (
              <MenuItem key={r.value} value={r.value}>
                {r.label}
              </MenuItem>
            ))}
          </TextField>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setDialogOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleSave} disabled={saving}>
            {saving ? 'Saving...' : 'Save'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Confirm Toggle */}
      <ConfirmDialog
        open={confirmDialog.open}
        title={confirmDialog.user?.is_active ? 'Deactivate User' : 'Activate User'}
        message={`Are you sure you want to ${
          confirmDialog.user?.is_active ? 'deactivate' : 'activate'
        } ${confirmDialog.user?.email}?`}
        onConfirm={handleToggleActive}
        onCancel={() => setConfirmDialog({ open: false, user: null })}
        confirmLabel={confirmDialog.user?.is_active ? 'Deactivate' : 'Activate'}
        confirmColor={confirmDialog.user?.is_active ? 'error' : 'success'}
      />

      <Snackbar
        open={snack.open}
        autoHideDuration={4000}
        onClose={() => setSnack({ ...snack, open: false })}
      >
        <Alert severity={snack.severity} onClose={() => setSnack({ ...snack, open: false })}>
          {snack.msg}
        </Alert>
      </Snackbar>
    </Box>
  );
}

export default UserManagement;
