import React, { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Dialog,
  DialogContent,
  DialogTitle,
  Divider,
  Grid,
  MenuItem,
  Paper,
  Stack,
  TextField,
  Typography,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import ClearIcon from '@mui/icons-material/Clear';
import DevicesIcon from '@mui/icons-material/Devices';
import KeyIcon from '@mui/icons-material/Key';
import SaveIcon from '@mui/icons-material/Save';
import WifiTetheringIcon from '@mui/icons-material/WifiTethering';
import { DataGrid } from '@mui/x-data-grid';
import api from '../../api/axios';

const EMPTY_FORM = {
  name: '',
  base_url: 'https://webapi.teamviewer.com/api/v1',
  api_token: '',
  is_active: true,
};

const SUMMARY_FIELDS = [
  ['Device Name', 'name'],
  ['Type', 'source'],
  ['TeamViewer ID', 'teamviewer_id'],
  ['Device ID', 'teamviewer_device_id'],
  ['Online State', 'online_state'],
  ['Group ID', 'group_id'],
  ['Assigned', 'assigned_to'],
  ['Last Seen', 'last_seen'],
  ['Description', 'description'],
];

const formatFieldLabel = (key) =>
  String(key)
    .replace(/[_-]+/g, ' ')
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/^./, (char) => char.toUpperCase());

const formatFieldValue = (value) => {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
};

const flattenObject = (value, prefix = '') => {
  if (!value || typeof value !== 'object') return [];

  if (Array.isArray(value)) {
    return value.flatMap((item, index) => flattenObject(item, `${prefix}[${index}]`));
  }

  return Object.entries(value).flatMap(([key, nested]) => {
    const path = prefix ? `${prefix}.${key}` : key;
    if (nested && typeof nested === 'object') {
      const nestedRows = flattenObject(nested, path);
      return nestedRows.length ? nestedRows : [{ label: path, value: nested }];
    }
    return [{ label: path, value: nested }];
  });
};

const buildRawRows = (device) => {
  const normalized = Object.entries(device || {})
    .filter(([key]) => !['id', 'raw'].includes(key))
    .map(([key, value]) => ({ label: formatFieldLabel(key), value }));
  const raw = flattenObject(device?.raw || {}).map(({ label, value }) => ({
    label: formatFieldLabel(label),
    value,
  }));

  const seen = new Set();
  return [...normalized, ...raw].filter(({ label, value }) => {
    const rowKey = `${label}:${formatFieldValue(value)}`;
    if (seen.has(rowKey)) return false;
    seen.add(rowKey);
    return value !== null && value !== undefined && value !== '';
  });
};

const onlineStateColor = (state) => {
  const value = String(state || '').toLowerCase();
  if (value === 'online') return 'success';
  if (value === 'busy') return 'warning';
  if (value === 'offline') return 'default';
  return 'default';
};

function TeamViewerPanel() {
  const theme = useTheme();
  const fullScreen = useMediaQuery(theme.breakpoints.down('sm'));
  const [form, setForm] = useState(EMPTY_FORM);
  const [connection, setConnection] = useState(null);
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [message, setMessage] = useState(null);
  const [selectedState, setSelectedState] = useState('all');
  const [selectedSource, setSelectedSource] = useState('all');
  const [deviceSearch, setDeviceSearch] = useState('');
  const [selectedDevice, setSelectedDevice] = useState(null);
  const [managedGroupsWarning, setManagedGroupsWarning] = useState('');

  const showMessage = (severity, text) => setMessage({ severity, text });

  const loadConnection = async () => {
    setLoading(true);
    try {
      const res = await api.get('/integrations/teamviewer/connection/');
      if (res.data?.configured) {
        setConnection(res.data);
        setForm({
          name: res.data.name || '',
          base_url: res.data.base_url || EMPTY_FORM.base_url,
          api_token: '',
          is_active: res.data.is_active ?? true,
        });
      }
    } catch (err) {
      showMessage('error', 'Failed to load TeamViewer connection.');
    } finally {
      setLoading(false);
    }
  };

  const loadDevices = async () => {
    try {
      const res = await api.get('/integrations/teamviewer/devices/?limit=500');
      setDevices((res.data?.results || []).map((device, index) => ({
        id: device.teamviewer_device_id || index,
        ...device,
      })));
      setManagedGroupsWarning(res.data?.managed_groups_warning || '');
    } catch (err) {
      setDevices([]);
    }
  };

  useEffect(() => {
    loadConnection();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (connection?.last_test_status === 'success') {
      loadDevices();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connection]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload = { ...form };
      const res = await api.post('/integrations/teamviewer/connection/', payload);
      setConnection(res.data);
      setForm({ ...form, api_token: '' });
      showMessage('success', 'TeamViewer connection saved.');
    } catch (err) {
      showMessage('error', err.response?.data?.detail || 'Failed to save TeamViewer connection.');
    } finally {
      setSaving(false);
    }
  };

  const hasUnsavedSecret = Boolean(form.api_token);

  const handleTest = async () => {
    setTesting(true);
    try {
      const res = await api.post('/integrations/teamviewer/test/');
      await loadConnection();
      showMessage('success', res.data?.message || 'Connected to TeamViewer successfully.');
    } catch (err) {
      await loadConnection();
      showMessage('error', err.response?.data?.message || err.response?.data?.detail || 'TeamViewer connection test failed.');
    } finally {
      setTesting(false);
    }
  };

  const handleRefresh = async () => {
    await loadConnection();
    await loadDevices();
  };

  const columns = [
    {
      field: 'name',
      headerName: 'Device',
      flex: 1,
      minWidth: 180,
      renderCell: ({ row, value }) => (
        <Button
          variant="text"
          size="small"
          onClick={() => setSelectedDevice(row)}
          sx={{
            justifyContent: 'flex-start',
            minWidth: 0,
            p: 0,
            color: 'text.primary',
            fontWeight: 700,
            textTransform: 'none',
            '&:hover': { color: 'primary.main', backgroundColor: 'transparent' },
          }}
        >
          <Typography variant="body2" noWrap fontWeight={700}>
            {value || row.teamviewer_id || 'Unnamed device'}
          </Typography>
        </Button>
      ),
    },
    { field: 'teamviewer_id', headerName: 'TeamViewer ID', flex: 1, minWidth: 150 },
    {
      field: 'source',
      headerName: 'Type',
      flex: 0.7,
      minWidth: 120,
      renderCell: ({ value }) => (
        <Chip
          size="small"
          label={value === 'managed' ? 'Managed' : 'Classic'}
          color={value === 'managed' ? 'primary' : 'default'}
          variant="outlined"
        />
      ),
    },
    {
      field: 'online_state',
      headerName: 'Online State',
      flex: 0.8,
      minWidth: 130,
      renderCell: ({ value }) => (
        <Chip size="small" label={value || 'Unknown'} color={onlineStateColor(value)} variant="outlined" />
      ),
    },
    { field: 'last_seen', headerName: 'Last Seen', flex: 1, minWidth: 180 },
    { field: 'description', headerName: 'Description', flex: 1, minWidth: 180 },
  ];

  const stateOptions = useMemo(
    () => Array.from(new Set(devices.map((device) => device.online_state).filter(Boolean))).sort(),
    [devices]
  );
  const filteredDevices = useMemo(() => {
    const query = deviceSearch.trim().toLowerCase();
    return devices.filter((device) => {
      const matchesState = selectedState === 'all' || device.online_state === selectedState;
      const matchesSource = selectedSource === 'all' || device.source === selectedSource;
      const matchesSearch =
        !query ||
        [device.name, device.teamviewer_id, device.description, device.online_state]
          .filter(Boolean)
          .some((value) => String(value).toLowerCase().includes(query));

      return matchesState && matchesSource && matchesSearch;
    });
  }, [devices, selectedState, selectedSource, deviceSearch]);

  const hasActiveFilters = selectedState !== 'all' || selectedSource !== 'all' || deviceSearch.trim();
  const selectedDeviceRows = useMemo(() => buildRawRows(selectedDevice), [selectedDevice]);
  const resetFilters = () => {
    setSelectedState('all');
    setSelectedSource('all');
    setDeviceSearch('');
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      {message && (
        <Alert severity={message.severity} onClose={() => setMessage(null)} sx={{ mb: 2 }}>
          {message.text}
        </Alert>
      )}

      <Grid container spacing={3}>
        <Grid item xs={12} md={5}>
          <Card sx={{ borderRadius: 2, boxShadow: 2 }}>
            <CardContent sx={{ p: 3 }}>
              <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 2 }}>
                <KeyIcon color="primary" />
                <Typography variant="h6" fontWeight={700}>
                  TeamViewer
                </Typography>
              </Stack>

              <Stack spacing={2}>
                <TextField
                  label="Label"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  helperText="A name to identify this TeamViewer token, e.g. its account or purpose."
                  fullWidth
                />
                <TextField
                  label="TeamViewer API URL"
                  value={form.base_url}
                  onChange={(e) => setForm({ ...form, base_url: e.target.value })}
                  fullWidth
                />
                <TextField
                  label={connection?.has_api_token ? 'API Token (saved)' : 'API Token'}
                  type="password"
                  value={form.api_token}
                  onChange={(e) => setForm({ ...form, api_token: e.target.value })}
                  helperText={connection?.has_api_token ? 'Leave blank to keep the saved token, or paste a new one and save.' : 'Script or company API token generated in the TeamViewer Management Console.'}
                  fullWidth
                />

                {connection?.last_test_status && (
                  <Alert severity={connection.last_test_status === 'success' ? 'success' : 'warning'}>
                    {connection.last_test_message}
                  </Alert>
                )}

                <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
                  <Button
                    variant="contained"
                    startIcon={<SaveIcon />}
                    onClick={handleSave}
                    disabled={saving}
                  >
                    Save
                  </Button>
                  <Button
                    variant="outlined"
                    startIcon={<WifiTetheringIcon />}
                    onClick={handleTest}
                    disabled={testing || !connection || hasUnsavedSecret}
                  >
                    Test
                  </Button>
                </Stack>
              </Stack>
              {hasUnsavedSecret && (
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1.5 }}>
                  Save the updated API token before testing the connection.
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={7}>
          <Card sx={{ borderRadius: 2, boxShadow: 2 }}>
            <CardContent sx={{ p: 3 }}>
              <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 2 }}>
                <Typography variant="h6" fontWeight={700}>
                  TeamViewer Devices
                </Typography>
                <Button variant="outlined" size="small" startIcon={<RefreshIcon />} onClick={handleRefresh}>
                  Refresh
                </Button>
              </Stack>
              {managedGroupsWarning && (
                <Alert severity="warning" sx={{ mb: 2 }}>
                  {managedGroupsWarning}
                </Alert>
              )}
              <Grid container spacing={2} alignItems="center" sx={{ mb: 2 }}>
                <Grid item xs={12} sm={3}>
                  <TextField
                    select
                    label="Type"
                    size="small"
                    fullWidth
                    value={selectedSource}
                    onChange={(e) => setSelectedSource(e.target.value)}
                  >
                    <MenuItem value="all">All types</MenuItem>
                    <MenuItem value="classic">Classic</MenuItem>
                    <MenuItem value="managed">Managed</MenuItem>
                  </TextField>
                </Grid>
                <Grid item xs={12} sm={3}>
                  <TextField
                    select
                    label="Online State"
                    size="small"
                    fullWidth
                    value={selectedState}
                    onChange={(e) => setSelectedState(e.target.value)}
                  >
                    <MenuItem value="all">All states</MenuItem>
                    {stateOptions.map((state) => (
                      <MenuItem key={state} value={state}>
                        {state}
                      </MenuItem>
                    ))}
                  </TextField>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Stack direction="row" spacing={1}>
                    <TextField
                      label="Search devices"
                      size="small"
                      fullWidth
                      value={deviceSearch}
                      onChange={(e) => setDeviceSearch(e.target.value)}
                    />
                    <Button
                      variant="outlined"
                      startIcon={<ClearIcon />}
                      onClick={resetFilters}
                      disabled={!hasActiveFilters}
                    >
                      Clear
                    </Button>
                  </Stack>
                </Grid>
              </Grid>
              <Box sx={{ overflowX: 'auto', WebkitOverflowScrolling: 'touch' }}>
                <DataGrid
                  rows={filteredDevices}
                  columns={columns}
                  autoHeight
                  onRowClick={({ row }) => setSelectedDevice(row)}
                  pageSizeOptions={[10, 25]}
                  initialState={{ pagination: { paginationModel: { pageSize: 10 } } }}
                  sx={{
                    border: 'none',
                    minWidth: 500,
                    fontSize: 13.5,
                    '& .MuiDataGrid-row': { cursor: 'pointer' },
                    '& .MuiDataGrid-columnHeaders': { backgroundColor: '#F8FAFC', borderBottom: '1px solid #E2E8F0' },
                    '& .MuiDataGrid-columnHeaderTitle': { fontWeight: 700, fontSize: 12, color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.05em' },
                    '& .MuiDataGrid-row:hover': { backgroundColor: '#F8FAFC' },
                    '& .MuiDataGrid-cell': { borderBottom: '1px solid #F1F5F9', '&:focus': { outline: 'none' }, '&:focus-within': { outline: 'none' } },
                    '& .MuiDataGrid-footerContainer': { borderTop: '1px solid #E2E8F0', backgroundColor: '#F8FAFC' },
                    '& .MuiDataGrid-columnSeparator': {
                      color: '#E2E8F0',
                      '&:hover': { color: '#6366F1' },
                    },
                  }}
                />
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Dialog
        open={Boolean(selectedDevice)}
        onClose={() => setSelectedDevice(null)}
        maxWidth="lg"
        fullWidth
        fullScreen={fullScreen}
      >
        <DialogTitle>
          <Stack direction="row" alignItems="center" spacing={1.5}>
            <DevicesIcon color="primary" />
            <Box sx={{ minWidth: 0 }}>
              <Typography variant="h6" fontWeight={800} noWrap>
                {selectedDevice?.name || selectedDevice?.teamviewer_id || 'TeamViewer Device'}
              </Typography>
              <Typography variant="body2" color="text.secondary" noWrap>
                {selectedDevice?.online_state || 'Unknown status'}
              </Typography>
            </Box>
          </Stack>
        </DialogTitle>
        <DialogContent dividers>
          <Grid container spacing={2} sx={{ mb: 3 }}>
            {SUMMARY_FIELDS.map(([label, key]) => (
              <Grid item xs={12} sm={6} md={4} key={key}>
                <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 1, height: '100%' }}>
                  <Typography variant="caption" color="text.secondary" fontWeight={700}>
                    {label}
                  </Typography>
                  <Typography variant="body2" fontWeight={700} sx={{ mt: 0.5, wordBreak: 'break-word' }}>
                    {formatFieldValue(selectedDevice?.[key])}
                  </Typography>
                </Paper>
              </Grid>
            ))}
          </Grid>

          <Divider sx={{ mb: 2 }} />
          <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 1.5 }}>
            <Typography variant="subtitle1" fontWeight={800}>
              Full TeamViewer Payload
            </Typography>
            <Chip size="small" label={`${selectedDeviceRows.length} fields`} />
          </Stack>

          <Grid container spacing={1.25}>
            {selectedDeviceRows.map(({ label, value }, index) => (
              <Grid item xs={12} md={6} key={`${label}-${index}`}>
                <Box
                  sx={{
                    display: 'grid',
                    gridTemplateColumns: { xs: '1fr', sm: '190px 1fr' },
                    gap: 1,
                    p: 1.25,
                    border: '1px solid',
                    borderColor: 'divider',
                    borderRadius: 1,
                    bgcolor: index % 2 === 0 ? 'background.paper' : 'grey.50',
                  }}
                >
                  <Typography variant="caption" color="text.secondary" fontWeight={800} sx={{ wordBreak: 'break-word' }}>
                    {label}
                  </Typography>
                  <Typography variant="body2" sx={{ wordBreak: 'break-word', whiteSpace: 'pre-wrap' }}>
                    {formatFieldValue(value)}
                  </Typography>
                </Box>
              </Grid>
            ))}
          </Grid>
        </DialogContent>
      </Dialog>
    </Box>
  );
}

export default TeamViewerPanel;
