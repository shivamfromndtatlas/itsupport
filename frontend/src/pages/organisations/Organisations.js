import React, { useEffect, useMemo, useState } from 'react';
import {
  Box,
  CircularProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Divider,
  Grid,
  Paper,
  Stack,
  Typography,
  TextField,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  OutlinedInput,
  Checkbox,
  ListItemText,
  Alert,
  Chip,
  IconButton,
  Tooltip,
  useMediaQuery,
  useTheme,
  Tabs,
  Tab,
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import AddIcon from '@mui/icons-material/Add';
import PlaceIcon from '@mui/icons-material/Place';
import api from '../../api/axios';
import DataTable from '../../components/common/DataTable';
import EmployeeLink from '../../components/common/EmployeeLink';

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

const MULTI_SELECT_MENU_PROPS = {
  PaperProps: {
    style: {
      maxHeight: 300,
      width: 260,
    },
  },
};

const INITIAL_ORG_FORM = {
  name: '',
  address: '',
  city: '',
  country: '',
  logo: null,
};

const INITIAL_LOCATION_FORM = {
  name: '',
  address: '',
  city: '',
  country: '',
  notes: '',
};

const INITIAL_MEMBER_FORM = {
  employee_id: '',
  full_name: '',
  official_email: '',
  contact_number: '',
  designation: '',
};

const INITIAL_EDIT_FORM = {
  employee_id: '',
  full_name: '',
  alias_name: '',
  official_email: '',
  contact_number: '',
  core_process_code: '',
  designation: '',
  date_of_joining: '',
  status: 'active',
};

const getLogoUrl = (logo) => {
  if (!logo) return '';
  if (/^https?:\/\//i.test(logo)) return logo;
  const API_HOST = process.env.REACT_APP_API_HOST || window.location.hostname || 'localhost';
  return `http://${API_HOST}:8000${logo.startsWith('/') ? logo : `/${logo}`}`;
};

const getOrgInitials = (name = '') => (
  name
    .split(' ')
    .filter(Boolean)
    .map((part) => part[0])
    .join('')
    .toUpperCase()
    .slice(0, 2) || 'OR'
);

const extractErrorMessage = (error, fallback) => {
  const responseData = error?.response?.data;
  if (!responseData) return fallback;
  if (typeof responseData === 'string') return responseData;
  if (responseData.detail) return responseData.detail;
  const firstValue = Object.values(responseData).flat().find(Boolean);
  return firstValue || fallback;
};

function OrganisationLogo({ org, size = 52 }) {
  const logoUrl = getLogoUrl(org.logo);

  return (
    <Box
      sx={{
        width: size,
        height: size,
        flexShrink: 0,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      {logoUrl ? (
        <Box
          component="img"
          src={logoUrl}
          alt={`${org.name} logo`}
          sx={{
            maxWidth: '100%',
            maxHeight: '100%',
            objectFit: 'contain',
            display: 'block',
          }}
        />
      ) : (
        <Box
          sx={{
            width: size,
            height: size,
            borderRadius: 1,
            bgcolor: 'grey.100',
            color: 'text.secondary',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: size <= 48 ? 14 : 16,
            fontWeight: 700,
          }}
        >
          {getOrgInitials(org.name)}
        </Box>
      )}
    </Box>
  );
}

function Organisations() {
  const theme = useTheme();
  const fullScreen = useMediaQuery(theme.breakpoints.down('sm'));
  const [orgs, setOrgs] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [memberProfiles, setMemberProfiles] = useState([]);
  const [orgForm, setOrgForm] = useState(INITIAL_ORG_FORM);
  const [memberForm, setMemberForm] = useState(INITIAL_MEMBER_FORM);
  const [editMember, setEditMember] = useState(null);
  const [editForm, setEditForm] = useState(INITIAL_EDIT_FORM);
  const [deleteMember, setDeleteMember] = useState(null);
  const [selectedClientOrgId, setSelectedClientOrgId] = useState('');
  const [selectedEmployeeIds, setSelectedEmployeeIds] = useState([]);
  const [message, setMessage] = useState({ type: '', text: '' });
  const [loading, setLoading] = useState(false);
  const [savingMember, setSavingMember] = useState(false);
  const [tab, setTab] = useState(0);
  const [memberAddType, setMemberAddType] = useState('assign');

  // Location management state
  const [locationDialogOrg, setLocationDialogOrg] = useState(null);
  const [orgLocations, setOrgLocations] = useState([]);
  const [locationsLoading, setLocationsLoading] = useState(false);
  const [locationForm, setLocationForm] = useState(INITIAL_LOCATION_FORM);
  const [addingLocation, setAddingLocation] = useState(false);
  const [showAddLocationForm, setShowAddLocationForm] = useState(false);
  const [editingLocationId, setEditingLocationId] = useState(null);

  const baseOrg = useMemo(() => orgs.find((org) => org.is_base), [orgs]);
  const clientOrgs = useMemo(() => orgs.filter((org) => !org.is_base), [orgs]);
  const selectedClientOrg = useMemo(
    () => clientOrgs.find((org) => String(org.id) === String(selectedClientOrgId)) || null,
    [clientOrgs, selectedClientOrgId]
  );
  const clientMembers = useMemo(() => memberProfiles, [memberProfiles]);
  const baseEmployees = useMemo(() => {
    if (!baseOrg) return [];
    return employees.filter((employee) =>
      Array.isArray(employee.organisations) &&
      employee.organisations.some((orgId) => String(orgId) === String(baseOrg.id)) &&
      employee.organisations.every((orgId) => String(orgId) === String(baseOrg.id))
    );
  }, [employees, baseOrg]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [{ data: orgData }, { data: employeeData }] = await Promise.all([
        api.get('/organisations/'),
        api.get('/employees/'),
      ]);
      const orgList = Array.isArray(orgData) ? orgData : orgData.results || [];
      const employeesList = Array.isArray(employeeData) ? employeeData : employeeData.results || [];
      setOrgs(orgList);
      setEmployees(employeesList);
      if (!selectedClientOrgId && orgList.some((org) => !org.is_base)) {
        setSelectedClientOrgId(orgList.find((org) => !org.is_base).id);
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Unable to load organisations or employees.' });
    } finally {
      setLoading(false);
    }
  };

  const loadClientMembers = async (clientOrgId = selectedClientOrgId) => {
    if (!clientOrgId) {
      setMemberProfiles([]);
      return;
    }

    try {
      const { data } = await api.get(`/organisations/${clientOrgId}/member-profiles/`);
      setMemberProfiles(Array.isArray(data) ? data : data.results || []);
    } catch (error) {
      setMemberProfiles([]);
      setMessage({ type: 'error', text: 'Unable to load client organisation members.' });
    }
  };

  useEffect(() => {
    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    loadClientMembers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedClientOrgId]);

  const handleOrgFormChange = (field) => (event) => {
    const value = field === 'logo' ? event.target.files?.[0] || null : event.target.value;
    setOrgForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleMemberFormChange = (field) => (event) => {
    setMemberForm((prev) => ({ ...prev, [field]: event.target.value }));
  };

  function openEditMember(row) {
    setEditMember(row);
    setEditForm({
      employee_id: row.employee_id || '',
      full_name: row.full_name || '',
      alias_name: row.alias_name || '',
      official_email: row.official_email || '',
      contact_number: row.contact_number || '',
      core_process_code: row.core_process_code || '',
      designation: row.designation || '',
      date_of_joining: row.date_of_joining || '',
      status: row.status || 'active',
    });
  }

  const handleEditFormChange = (field) => (event) => {
    setEditForm((prev) => ({ ...prev, [field]: event.target.value }));
  };

  const handleCloseEditMember = () => {
    setEditMember(null);
    setEditForm(INITIAL_EDIT_FORM);
  };

  const handleCloseDeleteMember = () => {
    setDeleteMember(null);
  };

  const handleCreateOrganisation = async () => {
    const { name, address, city, country, logo } = orgForm;
    if (!name || !address || !city || !country) {
      setMessage({ type: 'error', text: 'Please fill all organisation fields.' });
      return;
    }

    const payload = new FormData();
    payload.append('name', name);
    payload.append('address', address);
    payload.append('city', city);
    payload.append('country', country);
    if (logo) payload.append('logo', logo);
    if (!baseOrg) payload.append('is_base', 'true');

    try {
      setLoading(true);
      await api.post('/organisations/', payload, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setMessage({ type: 'success', text: 'Organisation created successfully.' });
      setOrgForm(INITIAL_ORG_FORM);
      await loadData();
    } catch (error) {
      const text = extractErrorMessage(error, 'Unable to create organisation.');
      setMessage({ type: 'error', text });
    } finally {
      setLoading(false);
    }
  };

  const handleAddMembers = async () => {
    if (!selectedClientOrgId) {
      setMessage({ type: 'error', text: 'Select a client organisation first.' });
      return;
    }

    if (memberAddType === 'assign' && !selectedEmployeeIds.length) {
      setMessage({ type: 'error', text: 'Select one or more base employees to assign.' });
      return;
    }

    const payload = {
      employee_ids: memberAddType === 'assign' ? selectedEmployeeIds : [],
      new_members: [],
    };

    if (memberAddType === 'create') {
      if (!memberForm.full_name || !memberForm.official_email) {
        setMessage({ type: 'error', text: 'New member requires name and email.' });
        return;
      }
      payload.new_members.push({
        employee_id: memberForm.employee_id,
        full_name: memberForm.full_name,
        official_email: memberForm.official_email,
        contact_number: memberForm.contact_number || '',
        designation: memberForm.designation,
      });
    }

    try {
      setLoading(true);
      await api.post(`/organisations/${selectedClientOrgId}/members/`, payload);
      setMessage({ type: 'success', text: 'Members added to client organisation.' });
      setSelectedEmployeeIds([]);
      setMemberForm(INITIAL_MEMBER_FORM);
      await loadData();
      await loadClientMembers(selectedClientOrgId);
    } catch (error) {
      setMessage({ type: 'error', text: extractErrorMessage(error, 'Unable to add members.') });
    } finally {
      setLoading(false);
    }
  };

  const handleSaveMember = async () => {
    if (!editMember) return;
    if (!editForm.full_name || !editForm.official_email) {
      setMessage({ type: 'error', text: 'Employee name and email are required.' });
      return;
    }

    const payload = {
      ...editForm,
      employee: editMember.employee || editMember.id,
      contact_number: editForm.contact_number || '',
      date_of_joining: editForm.date_of_joining || null,
    };

    try {
      setSavingMember(true);
      await api.patch(`/organisations/${selectedClientOrgId}/member-profiles/`, payload);
      setMessage({ type: 'success', text: 'Employee details updated.' });
      handleCloseEditMember();
      await loadClientMembers(selectedClientOrgId);
    } catch (error) {
      setMessage({ type: 'error', text: extractErrorMessage(error, 'Unable to update employee details.') });
    } finally {
      setSavingMember(false);
    }
  };

  const handleDeleteMember = async () => {
    if (!deleteMember || !selectedClientOrgId) return;

    try {
      setLoading(true);
      await api.delete(`/organisations/${selectedClientOrgId}/member-profiles/`, {
        data: { employee: deleteMember.employee || deleteMember.id },
      });
      setMessage({ type: 'success', text: 'Employee removed from client organisation.' });
      handleCloseDeleteMember();
      await loadData();
      await loadClientMembers(selectedClientOrgId);
    } catch (error) {
      const responseData = error.response?.data;
      const text = responseData?.detail ||
        (typeof responseData === 'object' ? Object.values(responseData).flat().join(' ') : '') ||
        'Unable to delete employee from client organisation.';
      setMessage({ type: 'error', text });
    } finally {
      setLoading(false);
    }
  };

  // ----- Location handlers -----
  const openLocationDialog = async (org) => {
    setLocationDialogOrg(org);
    setShowAddLocationForm(false);
    setLocationForm(INITIAL_LOCATION_FORM);
    setEditingLocationId(null);
    setLocationsLoading(true);
    try {
      const { data } = await api.get(`/organisations/${org.id}/locations/`);
      setOrgLocations(Array.isArray(data) ? data : data.results || []);
    } catch {
      setOrgLocations([]);
    } finally {
      setLocationsLoading(false);
    }
  };

  const closeLocationDialog = () => {
    setLocationDialogOrg(null);
    setOrgLocations([]);
    setLocationForm(INITIAL_LOCATION_FORM);
    setShowAddLocationForm(false);
    setEditingLocationId(null);
  };

  const handleLocationFormChange = (field) => (e) => {
    setLocationForm((prev) => ({ ...prev, [field]: e.target.value }));
  };

  const handleAddLocation = async () => {
    if (!locationForm.name.trim()) {
      setMessage({ type: 'error', text: 'Location name is required.' });
      return;
    }
    try {
      setAddingLocation(true);
      if (editingLocationId) {
        const { data } = await api.patch(
          `/organisations/${locationDialogOrg.id}/locations/${editingLocationId}/edit/`,
          locationForm
        );
        setOrgLocations((prev) => prev.map((loc) => (loc.id === editingLocationId ? data : loc)));
        setMessage({ type: 'success', text: 'Location updated successfully.' });
      } else {
        const { data } = await api.post(`/organisations/${locationDialogOrg.id}/locations/add/`, locationForm);
        setOrgLocations((prev) => [...prev, data]);
        setMessage({ type: 'success', text: 'Location added successfully.' });
      }
      setLocationForm(INITIAL_LOCATION_FORM);
      setShowAddLocationForm(false);
      setEditingLocationId(null);
    } catch (error) {
      const text = error.response?.data?.detail ||
        (typeof error.response?.data === 'object' ? Object.values(error.response.data).flat().join(' ') : '') ||
        (editingLocationId ? 'Unable to update location.' : 'Unable to add location.');
      setMessage({ type: 'error', text });
    } finally {
      setAddingLocation(false);
    }
  };

  const handleEditLocation = (location) => {
    setEditingLocationId(location.id);
    setLocationForm({
      name: location.name || '',
      address: location.address || '',
      city: location.city || '',
      country: location.country || '',
      notes: location.notes || '',
    });
    setShowAddLocationForm(true);
  };

  const handleDeleteLocation = async (locationId) => {
    try {
      await api.delete(`/organisations/${locationDialogOrg.id}/locations/${locationId}/`);
      setOrgLocations((prev) => prev.filter((l) => l.id !== locationId));
      if (editingLocationId === locationId) {
        setEditingLocationId(null);
        setLocationForm(INITIAL_LOCATION_FORM);
        setShowAddLocationForm(false);
      }
    } catch {
      setMessage({ type: 'error', text: 'Unable to delete location.' });
    }
  };

  const memberColumns = [
    { field: 'employee_id', headerName: 'Employee ID', minWidth: 130, flex: 0.8 },
    {
      field: 'display_name',
      headerName: 'Name',
      minWidth: 180,
      flex: 1.2,
      renderCell: ({ row, value }) => (
        <EmployeeLink employeeId={row.employee || row.id}>
          {value}
        </EmployeeLink>
      ),
    },
    { field: 'official_email', headerName: 'Email', minWidth: 220, flex: 1.4 },
    {
      field: 'contact_number',
      headerName: 'Contact',
      minWidth: 140,
      flex: 1,
      valueGetter: (value) => value || '-',
    },
    { field: 'designation', headerName: 'Designation', minWidth: 170, flex: 1 },
    {
      field: 'status',
      headerName: 'Status',
      minWidth: 120,
      flex: 0.7,
      renderCell: (params) => (
        <Chip
          label={(params.value || 'active').replace(/_/g, ' ')}
          size="small"
          color={STATUS_COLORS[params.value] || 'default'}
          sx={{ textTransform: 'capitalize', fontWeight: 600 }}
        />
      ),
    },
    {
      field: 'actions',
      headerName: 'Actions',
      minWidth: 100,
      sortable: false,
      filterable: false,
      renderCell: ({ row }) => (
        <Stack direction="row" spacing={0.5}>
          <Tooltip title="Edit employee">
            <IconButton size="small" onClick={() => openEditMember(row)}>
              <EditIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Delete employee">
            <IconButton size="small" color="error" onClick={() => setDeleteMember(row)}>
              <DeleteIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Stack>
      ),
    },
  ];

  return (
    <Box>
      <Typography variant="h5" fontWeight={700} mb={2}>
        Organisation Management
      </Typography>

      {message.text && (
        <Alert severity={message.type} sx={{ mb: 3 }} onClose={() => setMessage({ type: '', text: '' })}>
          {message.text}
        </Alert>
      )}

      {/* Tab Header */}
      <Paper sx={{ mb: 3, borderRadius: 2 }}>
        <Tabs
          value={tab}
          onChange={(_, v) => setTab(v)}
          sx={{ borderBottom: 1, borderColor: 'divider', px: 2 }}
        >
          <Tab label="Members Dashboard" />
          <Tab label="Organisations Directory & Setup" />
        </Tabs>
      </Paper>

      {tab === 0 && (
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <Paper sx={{ p: 3, display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 2, borderRadius: 2 }}>
              <Box>
                <Typography variant="h6" fontWeight={700}>
                  Client Organisation Dashboard
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {selectedClientOrg
                    ? `Manage members and profiles for ${selectedClientOrg.name}`
                    : 'Select a client organisation to manage members'}
                </Typography>
              </Box>
              <FormControl size="small" sx={{ minWidth: 280 }}>
                <InputLabel id="client-dashboard-org-select-label">Client Organisation</InputLabel>
                <Select
                  labelId="client-dashboard-org-select-label"
                  value={selectedClientOrgId}
                  label="Client Organisation"
                  onChange={(e) => setSelectedClientOrgId(e.target.value)}
                >
                  {clientOrgs.map((org) => (
                    <MenuItem key={org.id} value={org.id}>
                      {org.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Paper>
          </Grid>

          {selectedClientOrgId ? (
            <>
              {/* Left side: Members table */}
              <Grid item xs={12} lg={8}>
                <Paper sx={{ p: 3, height: '100%', borderRadius: 2 }}>
                  <Typography variant="subtitle1" fontWeight={700} mb={2}>
                    Members List
                  </Typography>
                  {clientOrgs.length === 0 ? (
                    <Typography color="text.secondary">Create a client organisation to view its member dashboard.</Typography>
                  ) : (
                    <DataTable
                      rows={clientMembers}
                      columns={memberColumns}
                      loading={loading}
                      onRefresh={() => loadClientMembers(selectedClientOrgId)}
                      searchable
                      pageSize={5}
                      refreshLabel="Refresh"
                    />
                  )}
                </Paper>
              </Grid>

              {/* Right side: Add/Assign Members form */}
              <Grid item xs={12} lg={4}>
                <Paper sx={{ p: 3, height: '100%', display: 'flex', flexDirection: 'column', borderRadius: 2 }}>
                  <Typography variant="subtitle1" fontWeight={700} mb={2}>
                    Add Members to Client
                  </Typography>
                  
                  {/* Toggle between assigning base employees and creating a new employee */}
                  <Box sx={{ display: 'flex', gap: 1, mb: 3 }}>
                    <Button
                      variant={memberAddType === 'assign' ? 'contained' : 'outlined'}
                      size="small"
                      fullWidth
                      onClick={() => setMemberAddType('assign')}
                    >
                      Assign Base Employee
                    </Button>
                    <Button
                      variant={memberAddType === 'create' ? 'contained' : 'outlined'}
                      size="small"
                      fullWidth
                      onClick={() => setMemberAddType('create')}
                    >
                      Create New Profile
                    </Button>
                  </Box>

                  {memberAddType === 'assign' ? (
                    <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                      <Box>
                        <Typography variant="body2" color="text.secondary" mb={2}>
                          Assign existing employees from the base organisation ({baseOrg?.name || 'Base'}) to this client organisation.
                        </Typography>
                        <FormControl fullWidth size="small" sx={{ mb: 2 }}>
                          <InputLabel id="base-employee-select-label">Assign Base Employees</InputLabel>
                          <Select
                            labelId="base-employee-select-label"
                            multiple
                            value={selectedEmployeeIds}
                            onChange={(e) => setSelectedEmployeeIds(e.target.value)}
                            input={<OutlinedInput label="Assign Base Employees" />}
                            renderValue={(selected) => selected.map((id) => {
                              const emp = baseEmployees.find((item) => item.id === id);
                              return emp ? emp.full_name : id;
                            }).join(', ')}
                            MenuProps={MULTI_SELECT_MENU_PROPS}
                          >
                            {baseEmployees.map((employee) => (
                              <MenuItem key={employee.id} value={employee.id}>
                                <Checkbox checked={selectedEmployeeIds.indexOf(employee.id) > -1} />
                                <ListItemText primary={`${employee.full_name} (${employee.employee_id})`} />
                              </MenuItem>
                            ))}
                          </Select>
                        </FormControl>
                      </Box>
                      <Button
                        variant="contained"
                        onClick={handleAddMembers}
                        disabled={loading || selectedEmployeeIds.length === 0}
                        sx={{ mt: 2, alignSelf: 'flex-end' }}
                      >
                        Assign Members
                      </Button>
                    </Box>
                  ) : (
                    <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                      <Box>
                        <Typography variant="body2" color="text.secondary" mb={2}>
                          Register a new employee profile directly under {selectedClientOrg?.name}.
                        </Typography>
                        <TextField
                          label="Employee ID (optional)"
                          value={memberForm.employee_id}
                          onChange={handleMemberFormChange('employee_id')}
                          fullWidth
                          size="small"
                          helperText="Leave blank and the system will assign one automatically."
                          FormHelperTextProps={{ sx: { ml: 0 } }}
                          sx={{ mb: 2 }}
                        />
                        <TextField
                          label="Full Name"
                          value={memberForm.full_name}
                          onChange={handleMemberFormChange('full_name')}
                          fullWidth
                          size="small"
                          sx={{ mb: 2 }}
                        />
                        <TextField
                          label="Official Email"
                          value={memberForm.official_email}
                          onChange={handleMemberFormChange('official_email')}
                          fullWidth
                          size="small"
                          sx={{ mb: 2 }}
                        />
                        <TextField
                          label="Contact Number"
                          value={memberForm.contact_number}
                          onChange={handleMemberFormChange('contact_number')}
                          fullWidth
                          size="small"
                          sx={{ mb: 2 }}
                        />
                        <TextField
                          label="Designation (optional)"
                          value={memberForm.designation}
                          onChange={handleMemberFormChange('designation')}
                          fullWidth
                          size="small"
                          sx={{ mb: 2 }}
                        />
                      </Box>
                      <Button
                        variant="contained"
                        onClick={handleAddMembers}
                        disabled={loading || !memberForm.full_name || !memberForm.official_email}
                        sx={{ mt: 2, alignSelf: 'flex-end' }}
                      >
                        Create Member
                      </Button>
                    </Box>
                  )}
                </Paper>
              </Grid>
            </>
          ) : (
            <Grid item xs={12}>
              <Paper sx={{ p: 4, textAlign: 'center', borderRadius: 2 }}>
                <Typography color="text.secondary">
                  {clientOrgs.length === 0
                    ? 'No client organisations found. Create one in the Organisations Directory tab.'
                    : 'Please select a client organisation from the dropdown above to manage its members.'}
                </Typography>
              </Paper>
            </Grid>
          )}
        </Grid>
      )}

      {tab === 1 && (
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 3, minHeight: 340, borderRadius: 2 }}>
              <Typography variant="subtitle1" fontWeight={700} mb={2}>
                {baseOrg ? 'Create Client Organisation' : 'Create Base Organisation'}
              </Typography>

              <Typography variant="body2" sx={{ mb: 3, color: 'text.secondary' }}>
                {baseOrg
                  ? 'Create a client organisation once the base organisation is already configured.'
                  : 'Create the single base organisation. Existing employees will automatically belong to this organisation.'}
              </Typography>

              <TextField
                label="Organisation Name"
                value={orgForm.name}
                onChange={handleOrgFormChange('name')}
                fullWidth
                size="small"
                sx={{ mb: 2 }}
              />
              <TextField
                label="Address"
                value={orgForm.address}
                onChange={handleOrgFormChange('address')}
                fullWidth
                size="small"
                sx={{ mb: 2 }}
                multiline
                minRows={2}
              />
              <Grid container spacing={2} sx={{ mb: 2 }}>
                <Grid item xs={12} sm={6}>
                  <TextField
                    label="City"
                    value={orgForm.city}
                    onChange={handleOrgFormChange('city')}
                    fullWidth
                    size="small"
                  />
                </Grid>
                <Grid item xs={12} sm={6}>
                  <TextField
                    label="Country"
                    value={orgForm.country}
                    onChange={handleOrgFormChange('country')}
                    fullWidth
                    size="small"
                  />
                </Grid>
              </Grid>
              
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
                <Button component="label" variant="outlined" size="small">
                  Upload Logo
                  <input type="file" hidden accept="image/*" onChange={handleOrgFormChange('logo')} />
                </Button>
                {orgForm.logo && (
                  <Chip label={orgForm.logo.name} size="small" onDelete={() => handleOrgFormChange('logo')({ target: { files: [] } })} />
                )}
              </Box>

              <Box display="flex" justifyContent="flex-end">
                <Button
                  variant="contained"
                  onClick={handleCreateOrganisation}
                  disabled={loading}
                >
                  {baseOrg ? 'Create Client' : 'Create Base'}
                </Button>
              </Box>
            </Paper>
          </Grid>

          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 3, minHeight: 340, borderRadius: 2 }}>
              <Typography variant="subtitle1" fontWeight={700} mb={2}>
                Base Organisation
              </Typography>
              {baseOrg ? (
                <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', p: 2, border: '1px solid', borderColor: 'divider', borderRadius: 2, mb: 3 }}>
                  <OrganisationLogo org={baseOrg} size={52} />
                  <Box>
                    <Typography variant="subtitle2" fontWeight={600}>
                      {baseOrg.name}
                    </Typography>
                    <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 0.5 }}>
                      {baseOrg.address}
                    </Typography>
                    <Typography variant="caption" fontWeight={600}>{baseOrg.city}, {baseOrg.country}</Typography>
                  </Box>
                </Box>
              ) : (
                <Typography color="text.secondary" variant="body2" sx={{ mb: 3 }}>
                  No base organisation exists yet. Create one first.
                </Typography>
              )}
              
              <Typography variant="subtitle1" fontWeight={700} mb={2}>
                Existing Organisations ({orgs.length})
              </Typography>
              {orgs.length === 0 ? (
                <Typography color="text.secondary" variant="body2">No organisations yet.</Typography>
              ) : (
                <Box sx={{ maxHeight: 360, overflowY: 'auto', pr: 1 }}>
                  {orgs.map((org) => (
                    <Paper
                      key={org.id}
                      variant="outlined"
                      sx={{
                        p: 1.5,
                        mb: 1,
                        bgcolor: org.is_base ? 'action.hover' : 'background.paper',
                        borderRadius: 2,
                      }}
                    >
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                        <OrganisationLogo org={org} size={40} />
                        <Box sx={{ minWidth: 0, flex: 1 }}>
                          <Typography variant="body2" fontWeight={600} noWrap>{org.name}</Typography>
                          <Typography variant="caption" color="text.secondary" display="block">
                            {org.is_base ? 'Base organisation' : 'Client organisation'} • {org.city}, {org.country}
                          </Typography>
                        </Box>
                        <Tooltip title="Manage Locations">
                          <Button
                            size="small"
                            variant="outlined"
                            startIcon={<PlaceIcon fontSize="small" />}
                            onClick={() => openLocationDialog(org)}
                            sx={{ whiteSpace: 'nowrap', flexShrink: 0 }}
                          >
                            Locations
                          </Button>
                        </Tooltip>
                      </Box>
                    </Paper>
                  ))}
                </Box>
              )}
            </Paper>
          </Grid>
        </Grid>
      )}

      {/* Locations Management Dialog */}
      <Dialog
        open={Boolean(locationDialogOrg)}
        onClose={closeLocationDialog}
        maxWidth="sm"
        fullWidth
        fullScreen={fullScreen}
      >
        <DialogTitle>
          <Stack direction="row" alignItems="center" spacing={1}>
            <PlaceIcon color="primary" />
            <Box>
              <Typography variant="subtitle1" fontWeight={700}>
                Locations — {locationDialogOrg?.name}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Manage office / site locations for this organisation
              </Typography>
            </Box>
          </Stack>
        </DialogTitle>

        <DialogContent dividers>
          {locationsLoading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
              <CircularProgress />
            </Box>
          ) : (
            <>
              {orgLocations.length === 0 ? (
                <Box sx={{ textAlign: 'center', py: 3 }}>
                  <PlaceIcon sx={{ fontSize: 40, color: 'text.disabled', mb: 1 }} />
                  <Typography color="text.secondary" variant="body2">
                    No locations added yet. Add the first location below.
                  </Typography>
                </Box>
              ) : (
                <Stack spacing={1} sx={{ mb: 2 }}>
                  {orgLocations.map((loc) => (
                    <Paper
                      key={loc.id}
                      variant="outlined"
                      sx={{ p: 1.5, borderRadius: 2, display: 'flex', alignItems: 'flex-start', gap: 1.5 }}
                    >
                      <PlaceIcon fontSize="small" sx={{ mt: 0.3, color: 'primary.main', flexShrink: 0 }} />
                      <Box sx={{ flex: 1, minWidth: 0 }}>
                        <Typography variant="body2" fontWeight={600}>{loc.name}</Typography>
                        {(loc.address || loc.city || loc.country) && (
                          <Typography variant="caption" color="text.secondary">
                            {[loc.address, loc.city, loc.country].filter(Boolean).join(', ')}
                          </Typography>
                        )}
                        {loc.notes && (
                          <Typography variant="caption" display="block" color="text.secondary" sx={{ fontStyle: 'italic' }}>
                            {loc.notes}
                          </Typography>
                        )}
                      </Box>
                      <Tooltip title="Edit location">
                        <IconButton
                          size="small"
                          onClick={() => handleEditLocation(loc)}
                          sx={{ flexShrink: 0, color: 'primary.main' }}
                        >
                          <EditIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Delete location">
                        <IconButton
                          size="small"
                          color="error"
                          onClick={() => handleDeleteLocation(loc.id)}
                          sx={{ flexShrink: 0 }}
                        >
                          <DeleteIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </Paper>
                  ))}
                </Stack>
              )}

              <Divider sx={{ my: 2 }} />

              {!showAddLocationForm ? (
                <Button
                  startIcon={<AddIcon />}
                  variant="outlined"
                  size="small"
                  onClick={() => setShowAddLocationForm(true)}
                  fullWidth
                >
                  Add New Location
                </Button>
              ) : (
                <Box>
                  <Typography variant="subtitle2" fontWeight={600} mb={1.5}>
                    {editingLocationId ? 'Edit Location' : 'New Location'}
                  </Typography>
                  <TextField
                    label="Location Name *"
                    value={locationForm.name}
                    onChange={handleLocationFormChange('name')}
                    fullWidth
                    size="small"
                    sx={{ mb: 2 }}
                    placeholder="e.g. Head Office, Mumbai Branch, Site A"
                  />
                  <TextField
                    label="Address"
                    value={locationForm.address}
                    onChange={handleLocationFormChange('address')}
                    fullWidth
                    size="small"
                    multiline
                    minRows={2}
                    sx={{ mb: 2 }}
                  />
                  <Grid container spacing={2} sx={{ mb: 2 }}>
                    <Grid item xs={6}>
                      <TextField
                        label="City"
                        value={locationForm.city}
                        onChange={handleLocationFormChange('city')}
                        fullWidth
                        size="small"
                      />
                    </Grid>
                    <Grid item xs={6}>
                      <TextField
                        label="Country"
                        value={locationForm.country}
                        onChange={handleLocationFormChange('country')}
                        fullWidth
                        size="small"
                      />
                    </Grid>
                  </Grid>
                  <TextField
                    label="Notes (optional)"
                    value={locationForm.notes}
                    onChange={handleLocationFormChange('notes')}
                    fullWidth
                    size="small"
                    multiline
                    minRows={2}
                    sx={{ mb: 2 }}
                    placeholder="e.g. Main corporate office, 2nd floor"
                  />
                  <Stack direction="row" spacing={1} justifyContent="flex-end">
                    <Button
                      size="small"
                      onClick={() => {
                        setShowAddLocationForm(false);
                        setEditingLocationId(null);
                        setLocationForm(INITIAL_LOCATION_FORM);
                      }}
                      sx={{ color: 'text.secondary' }}
                    >
                      Cancel
                    </Button>
                    <Button
                      variant="contained"
                      size="small"
                      startIcon={editingLocationId ? <EditIcon /> : <AddIcon />}
                      onClick={handleAddLocation}
                      disabled={addingLocation || !locationForm.name.trim()}
                    >
                      {addingLocation ? (editingLocationId ? 'Saving...' : 'Adding...') : (editingLocationId ? 'Save Changes' : 'Add Location')}
                    </Button>
                  </Stack>
                </Box>
              )}
            </>
          )}
        </DialogContent>

        <DialogActions>
          <Button onClick={closeLocationDialog}>Close</Button>
        </DialogActions>
      </Dialog>

      {/* Edit Member Dialog */}
      <Dialog
        open={Boolean(editMember)}
        onClose={handleCloseEditMember}
        maxWidth="md"
        fullWidth
        fullScreen={fullScreen}
      >
        <DialogTitle>Edit Client Employee Details</DialogTitle>
        <DialogContent sx={{ pt: '12px !important' }}>
          <Grid container spacing={2}>
            <Grid item xs={12} sm={4}>
              <TextField
                label="Employee ID"
                value={editForm.employee_id}
                fullWidth
                disabled
              />
            </Grid>
            <Grid item xs={12} sm={4}>
              <TextField
                label="Client Name"
                value={editForm.full_name}
                onChange={handleEditFormChange('full_name')}
                fullWidth
              />
            </Grid>
            {editMember?.is_base_employee && (
              <Grid item xs={12} sm={4}>
                <TextField
                  label="Client Alias Name"
                  value={editForm.alias_name}
                  onChange={handleEditFormChange('alias_name')}
                  fullWidth
                />
              </Grid>
            )}
            <Grid item xs={12} sm={4}>
              <TextField
                label="Client Email"
                type="email"
                value={editForm.official_email}
                onChange={handleEditFormChange('official_email')}
                fullWidth
              />
            </Grid>
            <Grid item xs={12} sm={4}>
              <TextField
                label="Client Contact Number (optional)"
                value={editForm.contact_number}
                onChange={handleEditFormChange('contact_number')}
                fullWidth
              />
            </Grid>
            <Grid item xs={12} sm={4}>
              <TextField
                label="Client Designation"
                value={editForm.designation}
                onChange={handleEditFormChange('designation')}
                fullWidth
              />
            </Grid>
            <Grid item xs={12} sm={4}>
              <TextField
                type="date"
                label="Client Date of Joining"
                value={editForm.date_of_joining}
                onChange={handleEditFormChange('date_of_joining')}
                fullWidth
                InputLabelProps={{ shrink: true }}
                InputProps={{ notched: true }}
              />
            </Grid>
            <Grid item xs={12} sm={8}>
              <TextField
                select
                label="Core Process"
                value={editForm.core_process_code}
                onChange={handleEditFormChange('core_process_code')}
                fullWidth
                InputLabelProps={{ shrink: true }}
              >
                <MenuItem value="">None</MenuItem>
                {CORE_PROCESSES.map((process) => (
                  <MenuItem key={process.code} value={process.code}>
                    <Box>
                      <Box component="span" sx={{ fontWeight: 600, mr: 1, color: 'primary.main' }}>
                        {process.code}
                      </Box>
                      {process.name}
                    </Box>
                  </MenuItem>
                ))}
              </TextField>
            </Grid>
            <Grid item xs={12} sm={4}>
              <TextField
                select
                label="Status"
                value={editForm.status}
                onChange={handleEditFormChange('status')}
                fullWidth
              >
                {STATUS_OPTIONS.map((status) => (
                  <MenuItem key={status} value={status}>
                    {status.replace(/_/g, ' ')}
                  </MenuItem>
                ))}
              </TextField>
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseEditMember} sx={{ color: 'text.secondary' }}>
            Cancel
          </Button>
          <Button variant="contained" onClick={handleSaveMember} disabled={savingMember}>
            {savingMember ? 'Saving...' : 'Save'}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={Boolean(deleteMember)} onClose={handleCloseDeleteMember} fullScreen={fullScreen}>
        <DialogTitle>Delete Client Employee</DialogTitle>
        <DialogContent>
          <Typography>
            Remove {deleteMember?.full_name || deleteMember?.display_name || 'this employee'} from the selected client organisation?
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            This will detach the employee from the client organisation and delete the client profile for this organisation.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDeleteMember} sx={{ color: 'text.secondary' }}>
            Cancel
          </Button>
          <Button variant="contained" color="error" onClick={handleDeleteMember} disabled={loading}>
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

export default Organisations;
