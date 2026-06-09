import React, { useEffect, useMemo, useState } from 'react';
import {
  Box,
  Grid,
  Paper,
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
  Divider,
} from '@mui/material';
import api from '../../api/axios';
import DataTable from '../../components/common/DataTable';

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

const INITIAL_MEMBER_FORM = {
  employee_id: '',
  full_name: '',
  official_email: '',
  contact_number: '',
  designation: '',
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
  const [orgs, setOrgs] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [orgForm, setOrgForm] = useState(INITIAL_ORG_FORM);
  const [memberForm, setMemberForm] = useState(INITIAL_MEMBER_FORM);
  const [selectedClientOrgId, setSelectedClientOrgId] = useState('');
  const [selectedEmployeeIds, setSelectedEmployeeIds] = useState([]);
  const [message, setMessage] = useState({ type: '', text: '' });
  const [loading, setLoading] = useState(false);

  const baseOrg = useMemo(() => orgs.find((org) => org.is_base), [orgs]);
  const clientOrgs = useMemo(() => orgs.filter((org) => !org.is_base), [orgs]);
  const selectedClientOrg = useMemo(
    () => clientOrgs.find((org) => String(org.id) === String(selectedClientOrgId)) || null,
    [clientOrgs, selectedClientOrgId]
  );
  const clientMembers = useMemo(() => {
    if (!selectedClientOrgId) return [];
    return employees.filter((employee) =>
      Array.isArray(employee.organisations) &&
      employee.organisations.some((orgId) => String(orgId) === String(selectedClientOrgId))
    );
  }, [employees, selectedClientOrgId]);
  const memberColumns = useMemo(() => [
    { field: 'employee_id', headerName: 'Employee ID', minWidth: 130, flex: 0.8 },
    { field: 'full_name', headerName: 'Name', minWidth: 180, flex: 1.2 },
    { field: 'official_email', headerName: 'Email', minWidth: 220, flex: 1.4 },
    { field: 'contact_number', headerName: 'Contact', minWidth: 140, flex: 1 },
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
          color={params.value === 'inactive' ? 'default' : params.value === 'on_leave' ? 'warning' : 'success'}
          sx={{ textTransform: 'capitalize', fontWeight: 600 }}
        />
      ),
    },
  ], []);

  const baseEmployees = useMemo(() => {
    if (!baseOrg) return [];
    return employees.filter((employee) =>
      Array.isArray(employee.organisations) && employee.organisations.includes(baseOrg.id)
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

  useEffect(() => {
    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleOrgFormChange = (field) => (event) => {
    const value = field === 'logo' ? event.target.files?.[0] || null : event.target.value;
    setOrgForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleMemberFormChange = (field) => (event) => {
    setMemberForm((prev) => ({ ...prev, [field]: event.target.value }));
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
      const text = error.response?.data?.detail || 'Unable to create organisation.';
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

    if (!selectedEmployeeIds.length && !memberForm.employee_id) {
      setMessage({ type: 'error', text: 'Select base employees or add a new member.' });
      return;
    }

    const payload = {
      employee_ids: selectedEmployeeIds,
      new_members: [],
    };

    if (memberForm.employee_id) {
      if (!memberForm.full_name || !memberForm.official_email || !memberForm.contact_number) {
        setMessage({ type: 'error', text: 'New member requires ID, name, email, and contact number.' });
        return;
      }
      payload.new_members.push({
        employee_id: memberForm.employee_id,
        full_name: memberForm.full_name,
        official_email: memberForm.official_email,
        contact_number: memberForm.contact_number,
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
    } catch (error) {
      const text = typeof error.response?.data === 'string'
        ? error.response.data
        : error.response?.data?.detail || 'Unable to add members.';
      setMessage({ type: 'error', text });
    } finally {
      setLoading(false);
    }
  };

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

      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3, minHeight: 340 }}>
            <Typography variant="h6" fontWeight={700} mb={2}>
              {baseOrg ? 'Create Client Organisation' : 'Create Base Organisation'}
            </Typography>

            <Typography sx={{ mb: 2, color: 'text.secondary' }}>
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
              multiline
              minRows={2}
              sx={{ mb: 2 }}
            />
            <TextField
              label="City"
              value={orgForm.city}
              onChange={handleOrgFormChange('city')}
              fullWidth
              size="small"
              sx={{ mb: 2 }}
            />
            <TextField
              label="Country"
              value={orgForm.country}
              onChange={handleOrgFormChange('country')}
              fullWidth
              size="small"
              sx={{ mb: 2 }}
            />
            <Button component="label" variant="outlined" size="small" sx={{ mb: 2 }}>
              Upload Logo
              <input type="file" hidden accept="image/*" onChange={handleOrgFormChange('logo')} />
            </Button>
            {orgForm.logo && (
              <Chip label={orgForm.logo.name} size="small" sx={{ mb: 2, ml: 1 }} />
            )}
            <Box display="flex" justifyContent="flex-end" mt={2}>
              <Button
                variant="contained"
                onClick={handleCreateOrganisation}
                disabled={loading}
              >
                {baseOrg ? 'Create Client Organisation' : 'Create Base Organisation'}
              </Button>
            </Box>
          </Paper>
        </Grid>

        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3, minHeight: 340 }}>
            <Typography variant="h6" fontWeight={700} mb={2}>
              Base Organisation
            </Typography>
            {baseOrg ? (
              <Box sx={{ display: 'flex', gap: 2, alignItems: 'flex-start' }}>
                <OrganisationLogo org={baseOrg} size={52} />
                <Box>
                  <Typography variant="subtitle1" fontWeight={600}>
                    {baseOrg.name}
                  </Typography>
                  <Typography sx={{ color: 'text.secondary', mb: 1 }}>
                    {baseOrg.address}
                  </Typography>
                  <Typography>{baseOrg.city}, {baseOrg.country}</Typography>
                </Box>
              </Box>
            ) : (
              <Typography color="text.secondary">
                No base organisation exists yet. Create one first.
              </Typography>
            )}
            <Divider sx={{ my: 2 }} />
            <Typography variant="h6" fontWeight={700} mb={2}>
              Existing Organisations
            </Typography>
            {orgs.length === 0 ? (
              <Typography color="text.secondary">No organisations yet.</Typography>
            ) : (
              orgs.map((org) => (
                <Paper
                  key={org.id}
                  variant="outlined"
                  sx={{
                    p: 2,
                    mb: 1,
                    bgcolor: org.is_base ? 'action.hover' : 'background.paper',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 2,
                  }}
                >
                  <OrganisationLogo org={org} size={48} />
                  <Box sx={{ minWidth: 0 }}>
                    <Typography fontWeight={600}>{org.name}</Typography>
                    <Typography variant="body2" color="text.secondary">
                      {org.is_base ? 'Base organisation' : 'Client organisation'} • {org.city}, {org.country}
                    </Typography>
                  </Box>
                </Paper>
              ))
            )}
          </Paper>
        </Grid>

        {baseOrg && (
          <Grid item xs={12}>
            <Paper sx={{ p: 3 }}>
              <Box
                sx={{
                  display: 'flex',
                  alignItems: { xs: 'stretch', md: 'center' },
                  justifyContent: 'space-between',
                  flexDirection: { xs: 'column', md: 'row' },
                  gap: 2,
                  mb: 2,
                }}
              >
                <Box>
                  <Typography variant="h6" fontWeight={700}>
                    Client Organisation Dashboard
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {selectedClientOrg
                      ? `${selectedClientOrg.name} members`
                      : 'Select a client organisation to view members'}
                  </Typography>
                </Box>
                <FormControl size="small" sx={{ minWidth: { xs: '100%', md: 280 } }}>
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
              </Box>

              {clientOrgs.length === 0 ? (
                <Typography color="text.secondary">Create a client organisation to view its member dashboard.</Typography>
              ) : (
                <DataTable
                  rows={clientMembers}
                  columns={memberColumns}
                  loading={loading}
                  searchable
                  pageSize={5}
                />
              )}
            </Paper>
          </Grid>
        )}

        {baseOrg && (
          <Grid item xs={12}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" fontWeight={700} mb={2}>
                Add Members to Client Organisation
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={12} md={4}>
                  <FormControl fullWidth size="small" sx={{ mb: 2 }}>
                    <InputLabel id="client-org-select-label">Client Organisation</InputLabel>
                    <Select
                      labelId="client-org-select-label"
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
                  {selectedClientOrg && (
                    <Typography variant="body2" color="text.secondary">
                      Selected client: {selectedClientOrg.name} ({selectedClientOrg.city}, {selectedClientOrg.country})
                    </Typography>
                  )}
                </Grid>

                <Grid item xs={12} md={8}>
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
                </Grid>

                <Grid item xs={12} md={3}>
                  <TextField
                    label="Employee ID"
                    value={memberForm.employee_id}
                    onChange={handleMemberFormChange('employee_id')}
                    fullWidth
                    size="small"
                    sx={{ mb: 2 }}
                  />
                </Grid>
                <Grid item xs={12} md={3}>
                  <TextField
                    label="Full Name"
                    value={memberForm.full_name}
                    onChange={handleMemberFormChange('full_name')}
                    fullWidth
                    size="small"
                    sx={{ mb: 2 }}
                  />
                </Grid>
                <Grid item xs={12} md={3}>
                  <TextField
                    label="Official Email"
                    value={memberForm.official_email}
                    onChange={handleMemberFormChange('official_email')}
                    fullWidth
                    size="small"
                    sx={{ mb: 2 }}
                  />
                </Grid>
                <Grid item xs={12} md={3}>
                  <TextField
                    label="Contact Number"
                    value={memberForm.contact_number}
                    onChange={handleMemberFormChange('contact_number')}
                    fullWidth
                    size="small"
                    sx={{ mb: 2 }}
                  />
                </Grid>
                <Grid item xs={12} md={6}>
                  <TextField
                    label="Designation (optional)"
                    value={memberForm.designation}
                    onChange={handleMemberFormChange('designation')}
                    fullWidth
                    size="small"
                    sx={{ mb: 2 }}
                  />
                </Grid>
              </Grid>
              <Box display="flex" justifyContent="flex-end" mt={1}>
                <Button
                  variant="contained"
                  onClick={handleAddMembers}
                  disabled={loading || !selectedClientOrgId}
                >
                  Add Members
                </Button>
              </Box>
            </Paper>
          </Grid>
        )}
      </Grid>
    </Box>
  );
}

export default Organisations;
