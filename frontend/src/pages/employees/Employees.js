import React, { useState, useEffect, useCallback, useMemo } from 'react';
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
  Avatar,
  useMediaQuery,
  useTheme,
  FormControl,
  InputLabel,
  Select,
  OutlinedInput,
  Checkbox,
  ListItemText,
  Stack,
  Typography,
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import DataTable from '../../components/common/DataTable';
import ConfirmDialog from '../../components/common/ConfirmDialog';
import EmployeeLink from '../../components/common/EmployeeLink';
import api from '../../api/axios';
import { useAuth } from '../../context/AuthContext';

const STATUS_OPTIONS = ['active', 'inactive', 'on_leave'];
const STATUS_COLORS = { active: 'success', inactive: 'default', on_leave: 'warning' };

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

const EMPTY_FORM = {
  employee_id: '',
  full_name: '',
  alias_name: '',
  official_email: '',
  contact_number: '',
  core_process_code: '',
  designation: '',
  date_of_joining: '',
  status: 'active',
  organisations: [],
};

const getOrgInitials = (name = '') =>
  name
    .split(' ')
    .filter(Boolean)
    .map((part) => part[0])
    .join('')
    .toUpperCase()
    .slice(0, 2) || 'OR';

const getLogoUrl = (logo) => {
  if (!logo) return '';
  if (/^https?:\/\//i.test(logo)) return logo;
  const apiHost = process.env.REACT_APP_API_HOST || window.location.hostname || 'localhost';
  return `http://${apiHost}:8000${logo.startsWith('/') ? logo : `/${logo}`}`;
};

function OrgChip({ org, onClick }) {
  const logoUrl = getLogoUrl(org.logo);

  return (
    <Chip
      size="small"
      clickable
      onClick={onClick}
      avatar={
        logoUrl ? (
          <Avatar src={logoUrl} alt={org.name} sx={{ width: 30, height: 30 }} />
        ) : (
          <Avatar sx={{ width: 30, height: 30, fontSize: 11, bgcolor: org.is_base ? 'primary.main' : 'secondary.main' }}>
            {getOrgInitials(org.name)}
          </Avatar>
        )
      }
      sx={{
        height: 38,
        minWidth: 58,
        '& .MuiChip-avatar': { width: 30, height: 30, marginLeft: 0.5 },
        '& .MuiChip-label': { px: 0.75 },
      }}
    />
  );
}

function Employees() {
  const { hasRole } = useAuth();
  const theme = useTheme();
  const fullScreen = useMediaQuery(theme.breakpoints.down('sm'));
  const canEdit = hasRole('super_admin', 'hr');

  const [rows, setRows] = useState([]);
  const [organisations, setOrganisations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editRow, setEditRow] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [confirmDialog, setConfirmDialog] = useState({ open: false, row: null });
  const [snack, setSnack] = useState({ open: false, msg: '', severity: 'success' });
  const [selectedOrganisationId, setSelectedOrganisationId] = useState('');
  const [selectedCoreProcessCode, setSelectedCoreProcessCode] = useState('');

  const showSnack = (msg, severity = 'success') =>
    setSnack({ open: true, msg, severity });

  const fetchEmployees = useCallback(async (filters = {}) => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ scope: 'all' });
      if (filters.organisationId) params.set('organisation_id', filters.organisationId);
      if (filters.coreProcessCode) params.set('core_process_code', filters.coreProcessCode);
      const [empRes, orgRes] = await Promise.all([
        api.get(`/employees/?${params.toString()}`),
        api.get('/organisations/'),
      ]);
      const empData = Array.isArray(empRes.data) ? empRes.data : empRes.data.results || [];
      const orgData = Array.isArray(orgRes.data) ? orgRes.data : orgRes.data.results || [];
      setRows(empData.map((e) => ({ ...e, id: e.id || e.employee_id })));
      setOrganisations(orgData);
    } catch {
      showSnack('Failed to load employees or organisations.', 'error');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchEmployees();
  }, [fetchEmployees]);

  const selectedOrganisation = useMemo(
    () => organisations.find((org) => String(org.id) === String(selectedOrganisationId)) || null,
    [organisations, selectedOrganisationId]
  );

  const handleOrganisationFilter = (orgId) => {
    const nextId = String(selectedOrganisationId) === String(orgId) ? '' : String(orgId);
    setSelectedOrganisationId(nextId);
    fetchEmployees({ organisationId: nextId, coreProcessCode: selectedCoreProcessCode });
  };

  const clearOrganisationFilter = () => {
    setSelectedOrganisationId('');
    fetchEmployees({ coreProcessCode: selectedCoreProcessCode });
  };

  const handleOrganisationSelect = (event) => {
    const nextId = event.target.value || '';
    setSelectedOrganisationId(nextId);
    fetchEmployees({ organisationId: nextId, coreProcessCode: selectedCoreProcessCode });
  };

  const handleCoreProcessSelect = (event) => {
    const nextCode = event.target.value || '';
    setSelectedCoreProcessCode(nextCode);
    fetchEmployees({ organisationId: selectedOrganisationId, coreProcessCode: nextCode });
  };

  const clearCoreProcessFilter = () => {
    setSelectedCoreProcessCode('');
    fetchEmployees({ organisationId: selectedOrganisationId });
  };

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
      alias_name: row.alias_name || '',
      official_email: row.official_email || '',
      contact_number: row.contact_number || '',
      core_process_code: row.core_process_code || '',
      designation: row.designation || '',
      date_of_joining: row.date_of_joining || '',
      status: row.status || 'active',
      organisations: row.organisations || [],
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
      fetchEmployees({
        organisationId: selectedOrganisationId,
        coreProcessCode: selectedCoreProcessCode,
      });
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
      fetchEmployees({
        organisationId: selectedOrganisationId,
        coreProcessCode: selectedCoreProcessCode,
      });
    } catch {
      showSnack('Delete failed.', 'error');
    } finally {
      setConfirmDialog({ open: false, row: null });
    }
  };

  const columns = [
    { field: 'employee_id', headerName: 'Employee ID', width: 130 },
    {
      field: 'full_name',
      headerName: 'Full Name',
      flex: 1,
      minWidth: 150,
      renderCell: ({ row, value }) => <EmployeeLink employeeId={row.id}>{value}</EmployeeLink>,
    },
    { field: 'alias_name', headerName: 'Alias Name', flex: 1, minWidth: 130 },
    { field: 'official_email', headerName: 'Email', flex: 1.2, minWidth: 180 },
    { field: 'contact_number', headerName: 'Contact', width: 140 },
    {
      field: 'core_process_code',
      headerName: 'Process Code',
      width: 130,
      renderCell: ({ value }) =>
        value ? (
          <Chip label={value} size="small" variant="outlined" color="primary" />
        ) : '—',
    },
    { field: 'core_process_name', headerName: 'Core Process', flex: 1, minWidth: 200 },
    {
      field: 'organisation_details',
      headerName: 'Associated Organisation',
      flex: 1.8,
      minWidth: 260,
      renderCell: ({ value }) => (
        <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', alignItems: 'center' }}>
          {value && value.length > 0 ? (
            value.map((org) => (
              <OrgChip
                key={org.id}
                org={org}
                onClick={() => handleOrganisationFilter(org.id)}
              />
            ))
          ) : (
            '—'
          )}
        </Box>
      ),
    },
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
      <Stack
        direction={{ xs: 'column', sm: 'row' }}
        spacing={1.5}
        alignItems={{ xs: 'stretch', sm: 'center' }}
        justifyContent="space-between"
        sx={{ mb: 2 }}
      >
        <Stack spacing={0.5} sx={{ minWidth: 280, flex: 1 }}>
          <Typography variant="body2" color="text.secondary">
            {selectedOrganisation || selectedCoreProcessCode
              ? `Filtering by${selectedOrganisation ? ` organisation ${selectedOrganisation.name}` : ''}${selectedOrganisation && selectedCoreProcessCode ? ' and' : ''}${selectedCoreProcessCode ? ` core process ${selectedCoreProcessCode}` : ''}`
              : 'Showing all employees'}
          </Typography>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} sx={{ maxWidth: 760 }}>
            <FormControl size="small" sx={{ minWidth: 240, flex: 1 }}>
              <InputLabel id="employee-org-filter-label">Filter by organisation</InputLabel>
              <Select
                labelId="employee-org-filter-label"
                value={selectedOrganisationId}
                label="Filter by organisation"
                onChange={handleOrganisationSelect}
              >
                <MenuItem value="">All organisations</MenuItem>
                {organisations.map((org) => (
                  <MenuItem key={org.id} value={org.id}>
                    {org.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <FormControl size="small" sx={{ minWidth: 240, flex: 1 }}>
              <InputLabel id="employee-core-filter-label">Filter by core process</InputLabel>
              <Select
                labelId="employee-core-filter-label"
                value={selectedCoreProcessCode}
                label="Filter by core process"
                onChange={handleCoreProcessSelect}
              >
                <MenuItem value="">All core processes</MenuItem>
                {CORE_PROCESSES.map((cp) => (
                  <MenuItem key={cp.code} value={cp.code}>
                    {cp.code} - {cp.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Stack>
        </Stack>
        <Stack direction="row" spacing={1} sx={{ alignSelf: { xs: 'flex-start', sm: 'center' } }}>
          {selectedOrganisation && (
            <Button variant="outlined" size="small" onClick={clearOrganisationFilter}>
              Clear org
            </Button>
          )}
          {selectedCoreProcessCode && (
            <Button variant="outlined" size="small" onClick={clearCoreProcessFilter}>
              Clear process
            </Button>
          )}
        </Stack>
      </Stack>
      <DataTable
        title="Employees"
        rows={rows}
        columns={columns}
        loading={loading}
        onAdd={canEdit ? openAdd : undefined}
        addLabel="Add Employee"
        searchable
      />

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="md" fullWidth fullScreen={fullScreen}>
        <DialogTitle>{editRow ? 'Edit Employee' : 'Add Employee'}</DialogTitle>
        <DialogContent sx={{ pt: '12px !important' }}>
          <Grid container spacing={2}>
            {[
              { name: 'employee_id', label: 'Employee ID', disabled: !!editRow },
              { name: 'full_name', label: 'Full Name' },
              { name: 'alias_name', label: 'Alias Name' },
              { name: 'official_email', label: 'Email', type: 'email' },
              { name: 'contact_number', label: 'Contact Number' },
              { name: 'designation', label: 'Designation' },
            ].map((field) => (
              <Grid item xs={12} sm={4} key={field.name}>
                <TextField
                  label={field.label}
                  name={field.name}
                  type={field.type || 'text'}
                  fullWidth
                  value={form[field.name]}
                  onChange={handleChange}
                  disabled={field.disabled}
                />
              </Grid>
            ))}

            {/* Pulled out of the map so shrink + notched are explicit for native date input */}
            <Grid item xs={12} sm={4}>
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

            <Grid item xs={12} sm={8}>
              <TextField
                select
                label="Core Process"
                name="core_process_code"
                fullWidth
                value={form.core_process_code}
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
            <Grid item xs={12} sm={4}>
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
            <Grid item xs={12} sm={8}>
              <FormControl fullWidth>
                <InputLabel id="organisations-select-label">Organisations</InputLabel>
                <Select
                  labelId="organisations-select-label"
                  multiple
                  name="organisations"
                  value={form.organisations || []}
                  onChange={handleChange}
                  input={<OutlinedInput label="Organisations" />}
                  renderValue={(selected) => selected.map((id) => {
                    const org = organisations.find((o) => o.id === id);
                    return org ? org.name : id;
                  }).join(', ')}
                >
                  {organisations.map((org) => (
                    <MenuItem key={org.id} value={org.id}>
                      <Checkbox checked={(form.organisations || []).indexOf(org.id) > -1} />
                      <ListItemText primary={org.name} />
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)} sx={{ color: 'text.secondary' }}>Cancel</Button>
          <Button variant="contained" onClick={handleSave} disabled={saving}>
            {saving ? 'Savingâ€¦' : 'Save'}
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


