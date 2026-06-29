import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Tabs,
  Tab,
  TextField,
  Button,
  Chip,
  IconButton,
  MenuItem,
  Tooltip,
  Snackbar,
  Alert,
  Grid,
  Typography,
  Paper,
} from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';
import DataTable from '../../components/common/DataTable';
import ConfirmDialog from '../../components/common/ConfirmDialog';
import api from '../../api/axios';
import { useAuth } from '../../context/AuthContext';

const CORE_PROCESSES = [
  { code: '01AOS', name: 'AEIS Operating Process' },
  { code: '02BDP', name: 'Business Development Process' },
  { code: '03HRP', name: 'Peoples Process' },
  { code: '04OPS', name: 'Operations Management Process' },
  { code: '05QCP', name: 'Quality Assurance & Compliance Process' },
  { code: '06TMP', name: 'Technology Management Process' },
  { code: '07FIN', name: 'Finance Process' },
  { code: '08TRD', name: 'Training & Development Process' },
  { code: '09ILP', name: 'Innovation Lab Process' },
];

const STATUS_COLOR = {
  pending: 'warning',
  confirmed: 'success',
  rejected: 'error',
};

const EMPTY_FORM = {
  full_name: '',
  employee_id: '',
  email: '',
  contact_number: '',
  department: '',
  designation: '',
  date_of_joining: '',
  core_process: '',
  reporting_manager: '',
  notes: '',
};

const formatApiErrors = (data) => {
  if (!data) return 'Submission failed.';
  if (typeof data === 'string') return data;
  if (data.detail) return data.detail;

  return Object.entries(data)
    .map(([field, messages]) => {
      const label = field.replaceAll('_', ' ');
      const text = Array.isArray(messages) ? messages.join(' ') : String(messages);
      return `${label}: ${text}`;
    })
    .join(' ');
};

function TabPanel({ value, index, children }) {
  return value === index ? <Box sx={{ pt: 2 }}>{children}</Box> : null;
}

function Onboarding() {
  const { hasRole } = useAuth();
  const canAdd = hasRole('hr', 'super_admin');
  const canAction = hasRole('super_admin', 'it_specialist');

  const [tab, setTab] = useState(0);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [confirmDialog, setConfirmDialog] = useState({ open: false, row: null, action: '' });
  const [snack, setSnack] = useState({ open: false, msg: '', severity: 'success' });

  const showSnack = (msg, severity = 'success') =>
    setSnack({ open: true, msg, severity });

  const fetchRequests = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/onboarding/');
      const data = Array.isArray(res.data) ? res.data : res.data.results || [];
      setRows(data.map((r) => ({ ...r, id: r.id || r.pk })));
    } catch {
      showSnack('Failed to load onboarding requests.', 'error');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRequests();
  }, [fetchRequests]);

  const handleChange = (e) => setForm({ ...form, [e.target.name]: e.target.value });

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      const payload = {
        full_name: form.full_name.trim(),
        employee_id: form.employee_id.trim(),
        personal_email: form.email.trim(),
        contact_number: form.contact_number.trim(),
        complete_address: form.notes.trim(),
        designation: form.designation.trim(),
        core_process: form.core_process,
        date_of_joining: form.date_of_joining,
        line_manager: form.reporting_manager.trim(),
      };

      await api.post('/onboarding/', payload);
      showSnack('New joiner request submitted.');
      setForm(EMPTY_FORM);
      fetchRequests();
      setTab(0);
    } catch (err) {
      showSnack(formatApiErrors(err.response?.data), 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const handleStatusChange = async () => {
    const { row, action } = confirmDialog;
    try {
      const endpoint = action === 'confirmed' ? 'confirm' : 'reject';
      const res = await api.post(`/onboarding/${row.id}/${endpoint}/`);
      showSnack(res.data?.detail || `Request ${action}.`);
      fetchRequests();
    } catch {
      showSnack('Action failed.', 'error');
    } finally {
      setConfirmDialog({ open: false, row: null, action: '' });
    }
  };

  const columns = [
    { field: 'full_name', headerName: 'Name', flex: 1, minWidth: 150 },
    { field: 'employee_id', headerName: 'Employee ID', width: 130 },
    { field: 'date_of_joining', headerName: 'DOJ', width: 120 },
    { field: 'department', headerName: 'Department', flex: 1 },
    {
      field: 'status',
      headerName: 'Status',
      width: 130,
      renderCell: ({ value }) => (
        <Chip
          label={(value || 'pending').replace('_', ' ')}
          color={STATUS_COLOR[value] || 'default'}
          size="small"
          sx={{ textTransform: 'capitalize' }}
        />
      ),
    },
    ...(canAction
      ? [
          {
            field: 'actions',
            headerName: 'Actions',
            width: 130,
            sortable: false,
            renderCell: ({ row }) =>
              row.status === 'pending' ? (
                <Box>
                  <Tooltip title="Confirm">
                    <IconButton
                      size="small"
                      color="success"
                      onClick={() =>
                        setConfirmDialog({ open: true, row, action: 'confirmed' })
                      }
                    >
                      <CheckCircleIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="Reject">
                    <IconButton
                      size="small"
                      color="error"
                      onClick={() =>
                        setConfirmDialog({ open: true, row, action: 'rejected' })
                      }
                    >
                      <CancelIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                </Box>
              ) : null,
          },
        ]
      : []),
  ];

  return (
    <Box>
      <Typography variant="h6" fontWeight={600} sx={{ mb: 2 }}>
        New Joiner Onboarding
      </Typography>

      <Paper sx={{ borderRadius: 2 }}>
        <Tabs
          value={tab}
          onChange={(_, v) => setTab(v)}
          sx={{ borderBottom: 1, borderColor: 'divider', px: 2 }}
        >
          <Tab label="New Joiner Requests" />
          {canAdd && <Tab label="Add New Request" />}
        </Tabs>

        <Box sx={{ p: 2 }}>
          <TabPanel value={tab} index={0}>
            <DataTable
              rows={rows}
              columns={columns}
              loading={loading}
              onRefresh={fetchRequests}
              searchable
              refreshLabel="Refresh"
            />
          </TabPanel>

          {canAdd && (
            <TabPanel value={tab} index={1}>
              <Grid container spacing={2}>
                {[
                  { name: 'full_name', label: 'Full Name' },
                  { name: 'employee_id', label: 'Employee ID' },
                  { name: 'email', label: 'Email', type: 'email' },
                  { name: 'contact_number', label: 'Contact Number' },
                  { name: 'department', label: 'Department' },
                  { name: 'designation', label: 'Designation' },
                  { name: 'reporting_manager', label: 'Reporting Manager' },
                ].map((field) => (
                  <Grid item xs={12} sm={6} key={field.name}>
                    <TextField
                      label={field.label}
                      name={field.name}
                      type={field.type || 'text'}
                      fullWidth
                      value={form[field.name]}
                      onChange={handleChange}
                    />
                  </Grid>
                ))}

                <Grid item xs={12} sm={6}>
                  <TextField
                    type="date"
                    label="Date of Joining"
                    name="date_of_joining"
                    fullWidth
                    value={form.date_of_joining}
                    onChange={handleChange}
                    InputLabelProps={{ shrink: true }}
                    InputProps={{ notched: true }}
                  />
                </Grid>

                <Grid item xs={12} sm={6}>
                  <TextField
                    select
                    label="Core Process"
                    name="core_process"
                    fullWidth
                    value={form.core_process}
                    onChange={handleChange}
                    InputLabelProps={{ shrink: true }}
                  >
                    {CORE_PROCESSES.map((cp) => (
                      <MenuItem key={cp.code} value={cp.code}>
                        <Box>
                          <Box component="span" sx={{ fontWeight: 600, mr: 1, color: 'primary.main' }}>
                            {cp.code}
                          </Box>
                          {cp.name}
                        </Box>
                      </MenuItem>
                    ))}
                  </TextField>
                </Grid>

                <Grid item xs={12}>
                  <TextField
                    label="Notes"
                    name="notes"
                    fullWidth
                    multiline
                    rows={3}
                    value={form.notes}
                    onChange={handleChange}
                  />
                </Grid>
                <Grid item xs={12}>
                  <Button
                    variant="contained"
                    onClick={handleSubmit}
                    disabled={submitting}
                    sx={{ mt: 1 }}
                  >
                    {submitting ? 'Submitting...' : 'Submit Request'}
                  </Button>
                </Grid>
              </Grid>
            </TabPanel>
          )}
        </Box>
      </Paper>

      <ConfirmDialog
        open={confirmDialog.open}
        title={`${confirmDialog.action === 'confirmed' ? 'Confirm' : 'Reject'} Request`}
        message={`Are you sure you want to ${confirmDialog.action === 'confirmed' ? 'confirm' : 'reject'} this request for ${confirmDialog.row?.full_name}?`}
        onConfirm={handleStatusChange}
        onCancel={() => setConfirmDialog({ open: false, row: null, action: '' })}
        confirmLabel={confirmDialog.action === 'confirmed' ? 'Confirm' : 'Reject'}
        confirmColor={confirmDialog.action === 'confirmed' ? 'success' : 'error'}
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

export default Onboarding;
