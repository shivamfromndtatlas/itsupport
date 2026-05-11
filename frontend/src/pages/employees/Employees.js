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
  Grid,
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import DataTable from '../../components/common/DataTable';
import ConfirmDialog from '../../components/common/ConfirmDialog';
import api from '../../api/axios';
import { useAuth } from '../../context/AuthContext';

const STATUS_OPTIONS = ['active', 'inactive', 'on_leave'];
const STATUS_COLORS = { active: 'success', inactive: 'default', on_leave: 'warning' };

const EMPTY_FORM = {
  employee_id: '',
  full_name: '',
  email: '',
  contact_number: '',
  core_process: '',
  department: '',
  designation: '',
  date_of_joining: '',
  status: 'active',
};

function Employees() {
  const { hasRole } = useAuth();
  const canEdit = hasRole('super_admin', 'hr');

  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editRow, setEditRow] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [confirmDialog, setConfirmDialog] = useState({ open: false, row: null });
  const [snack, setSnack] = useState({ open: false, msg: '', severity: 'success' });

  const showSnack = (msg, severity = 'success') =>
    setSnack({ open: true, msg, severity });

  const fetchEmployees = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/employees/');
      const data = Array.isArray(res.data) ? res.data : res.data.results || [];
      setRows(data.map((e) => ({ ...e, id: e.id || e.employee_id })));
    } catch {
      showSnack('Failed to load employees.', 'error');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchEmployees();
  }, [fetchEmployees]);

  const openAdd = () => {
    setEditRow(null);
    setForm(EMPTY_FORM);
    setDialogOpen(true);
  };

  const openEdit = (row) => {
    setEditRow(row);
    setForm({
      employee_id: row.employee_id || '',
      full_name: row.full_name || '',
      email: row.email || '',
      contact_number: row.contact_number || '',
      core_process: row.core_process || '',
      department: row.department || '',
      designation: row.designation || '',
      date_of_joining: row.date_of_joining || '',
      status: row.status || 'active',
    });
    setDialogOpen(true);
  };

  const handleChange = (e) => setForm({ ...form, [e.target.name]: e.target.value });

  const handleSave = async () => {
    setSaving(true);
    try {
      if (editRow) {
        await api.patch(`/employees/${editRow.id}/`, form);
        showSnack('Employee updated.');
      } else {
        await api.post('/employees/', form);
        showSnack('Employee added.');
      }
      setDialogOpen(false);
      fetchEmployees();
    } catch (err) {
      showSnack(err.response?.data?.detail || 'Save failed.', 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    try {
      await api.delete(`/employees/${confirmDialog.row.id}/`);
      showSnack('Employee removed.');
      fetchEmployees();
    } catch {
      showSnack('Delete failed.', 'error');
    } finally {
      setConfirmDialog({ open: false, row: null });
    }
  };

  const columns = [
    { field: 'employee_id', headerName: 'Employee ID', width: 130 },
    { field: 'full_name', headerName: 'Full Name', flex: 1, minWidth: 150 },
    { field: 'email', headerName: 'Email', flex: 1.2, minWidth: 180 },
    { field: 'contact_number', headerName: 'Contact', width: 140 },
    { field: 'core_process', headerName: 'Core Process', flex: 1, minWidth: 140 },
    {
      field: 'status',
      headerName: 'Status',
      width: 120,
      renderCell: ({ value }) => (
        <Chip
          label={(value || '').replace('_', ' ')}
          color={STATUS_COLORS[value] || 'default'}
          size="small"
          sx={{ textTransform: 'capitalize' }}
        />
      ),
    },
    ...(canEdit
      ? [
          {
            field: 'actions',
            headerName: 'Actions',
            width: 100,
            sortable: false,
            renderCell: ({ row }) => (
              <Box>
                <Tooltip title="Edit">
                  <IconButton size="small" onClick={() => openEdit(row)}>
                    <EditIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              </Box>
            ),
          },
        ]
      : []),
  ];

  return (
    <Box>
      <DataTable
        title="Employees"
        rows={rows}
        columns={columns}
        loading={loading}
        onAdd={canEdit ? openAdd : undefined}
        addLabel="Add Employee"
        searchable
      />

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>{editRow ? 'Edit Employee' : 'Add Employee'}</DialogTitle>
        <DialogContent sx={{ pt: '12px !important' }}>
          <Grid container spacing={2}>
            {[
              { name: 'employee_id', label: 'Employee ID', disabled: !!editRow },
              { name: 'full_name', label: 'Full Name' },
              { name: 'email', label: 'Email', type: 'email' },
              { name: 'contact_number', label: 'Contact Number' },
              { name: 'core_process', label: 'Core Process' },
              { name: 'department', label: 'Department' },
              { name: 'designation', label: 'Designation' },
              { name: 'date_of_joining', label: 'Date of Joining', type: 'date', shrink: true },
            ].map((field) => (
              <Grid item xs={12} sm={6} key={field.name}>
                <TextField
                  label={field.label}
                  name={field.name}
                  type={field.type || 'text'}
                  fullWidth
                  value={form[field.name]}
                  onChange={handleChange}
                  disabled={field.disabled}
                  InputLabelProps={field.shrink ? { shrink: true } : undefined}
                />
              </Grid>
            ))}
            <Grid item xs={12} sm={6}>
              <TextField
                select
                label="Status"
                name="status"
                fullWidth
                value={form.status}
                onChange={handleChange}
              >
                {STATUS_OPTIONS.map((s) => (
                  <MenuItem key={s} value={s}>
                    {s.replace('_', ' ')}
                  </MenuItem>
                ))}
              </TextField>
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setDialogOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleSave} disabled={saving}>
            {saving ? 'Saving...' : 'Save'}
          </Button>
        </DialogActions>
      </Dialog>

      <ConfirmDialog
        open={confirmDialog.open}
        title="Remove Employee"
        message={`Remove ${confirmDialog.row?.full_name}?`}
        onConfirm={handleDelete}
        onCancel={() => setConfirmDialog({ open: false, row: null })}
        confirmLabel="Remove"
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

export default Employees;
