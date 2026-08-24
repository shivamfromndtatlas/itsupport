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
import SyncIcon from '@mui/icons-material/Sync';
import WifiTetheringIcon from '@mui/icons-material/WifiTethering';
import SecurityIcon from '@mui/icons-material/Security';
import { DataGrid } from '@mui/x-data-grid';
import api from '../../api/axios';

const EMPTY_FORM = {
  base_url: 'https://api.manage.trellix.com',
  auth_url: 'https://iam.cloud.trellix.com/iam/v1.0/token',
  tenant_name: '',
  tenant_id: '',
  client_id: '',
  client_secret: '',
  api_key: '',
  scope: 'epo.device.r',
  is_active: true,
};

const SUMMARY_FIELDS = [
  ['Device Name', 'name'],
  ['Serial Number', 'serial_number'],
  ['Trellix Device ID', 'trellix_device_id'],
  ['Platform', 'platform'],
  ['OS Version', 'os_version'],
  ['IP Address', 'ip_address'],
  ['Agent Version', 'agent_version'],
  ['Threat Status', 'threat_status'],
  ['Last Communication', 'last_communication'],
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

const threatSeverityColor = (severity) => {
  const value = String(severity || '').toLowerCase();
  if (value.includes('critical') || value.includes('high')) return 'error';
  if (value.includes('medium')) return 'warning';
  if (value.includes('low')) return 'info';
  return 'default';
};

function TrellixPanel() {
  const theme = useTheme();
  const fullScreen = useMediaQuery(theme.breakpoints.down('sm'));
  const [form, setForm] = useState(EMPTY_FORM);
  const [connection, setConnection] = useState(null);
  const [devices, setDevices] = useState([]);
  const [threats, setThreats] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [message, setMessage] = useState(null);
  const [selectedPlatform, setSelectedPlatform] = useState('all');
  const [deviceSearch, setDeviceSearch] = useState('');
  const [selectedDevice, setSelectedDevice] = useState(null);

  const showMessage = (severity, text) => setMessage({ severity, text });

  const loadConnection = async () => {
    setLoading(true);
    try {
      const res = await api.get('/integrations/trellix/connection/');
      if (res.data?.configured) {
        setConnection(res.data);
        setForm({
          base_url: res.data.base_url || EMPTY_FORM.base_url,
          auth_url: res.data.auth_url || EMPTY_FORM.auth_url,
          tenant_name: res.data.tenant_name || '',
          tenant_id: res.data.tenant_id || '',
          client_id: res.data.client_id || '',
          client_secret: '',
          api_key: '',
          scope: res.data.scope || EMPTY_FORM.scope,
          is_active: res.data.is_active ?? true,
        });
      }
    } catch (err) {
      showMessage('error', 'Failed to load Trellix connection.');
    } finally {
      setLoading(false);
    }
  };

  const loadDevices = async () => {
    try {
      const res = await api.get('/integrations/trellix/devices/?limit=500');
      setDevices((res.data?.results || []).map((device, index) => ({
        id: device.trellix_device_id || index,
        ...device,
      })));
    } catch (err) {
      setDevices([]);
    }
  };

  const loadThreats = async () => {
    try {
      const res = await api.get('/integrations/trellix/threats/?limit=200');
      setThreats((res.data?.results || []).map((event, index) => ({
        id: event.event_id || index,
        ...event,
      })));
    } catch (err) {
      setThreats([]);
    }
  };

  useEffect(() => {
    loadConnection();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (connection?.last_test_status === 'success') {
      loadDevices();
      loadThreats();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connection]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload = { ...form };
      const res = await api.post('/integrations/trellix/connection/', payload);
      setConnection(res.data);
      setForm({ ...form, client_secret: '', api_key: '', scope: res.data.scope || form.scope });
      showMessage('success', 'Trellix connection saved.');
    } catch (err) {
      showMessage('error', err.response?.data?.detail || 'Failed to save Trellix connection.');
    } finally {
      setSaving(false);
    }
  };

  const hasUnsavedSecret = Boolean(form.client_secret || form.api_key);

  const handleTest = async () => {
    setTesting(true);
    try {
      const res = await api.post('/integrations/trellix/test/');
      await loadConnection();
      showMessage('success', res.data?.message || 'Connected to Trellix successfully.');
    } catch (err) {
      await loadConnection();
      showMessage('error', err.response?.data?.message || err.response?.data?.detail || 'Trellix connection test failed.');
    } finally {
      setTesting(false);
    }
  };

  const handleSync = async () => {
    setSyncing(true);
    try {
      const res = await api.post('/integrations/trellix/sync-assets/');
      await loadConnection();
      await loadDevices();
      showMessage('success', `Synced ${res.data?.total || 0} Trellix endpoints into IT Assets.`);
    } catch (err) {
      showMessage('error', err.response?.data?.detail || 'Trellix asset sync failed.');
    } finally {
      setSyncing(false);
    }
  };

  const handleRefresh = async () => {
    await loadConnection();
    await loadDevices();
    await loadThreats();
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
            {value || row.serial_number || row.trellix_device_id || 'Unnamed device'}
          </Typography>
        </Button>
      ),
    },
    { field: 'serial_number', headerName: 'Serial Number', flex: 1, minWidth: 160 },
    { field: 'platform', headerName: 'Platform', flex: 1, minWidth: 130 },
    {
      field: 'threat_status',
      headerName: 'Threat Status',
      flex: 1,
      minWidth: 150,
      renderCell: ({ value }) => (
        <Chip
          size="small"
          label={value || 'Unknown'}
          color={String(value).toLowerCase().includes('protect') ? 'success' : 'default'}
          variant="outlined"
        />
      ),
    },
    { field: 'last_communication', headerName: 'Last Communication', flex: 1, minWidth: 180 },
  ];

  const threatColumns = [
    { field: 'device_name', headerName: 'Device', flex: 1, minWidth: 150 },
    { field: 'threat_name', headerName: 'Threat', flex: 1, minWidth: 170 },
    { field: 'threat_type', headerName: 'Type', flex: 0.8, minWidth: 120 },
    {
      field: 'severity',
      headerName: 'Severity',
      flex: 0.7,
      minWidth: 110,
      renderCell: ({ value }) => (
        <Chip size="small" label={value || 'Unknown'} color={threatSeverityColor(value)} variant="outlined" />
      ),
    },
    { field: 'action_taken', headerName: 'Action Taken', flex: 1, minWidth: 140 },
    { field: 'detected_at', headerName: 'Detected At', flex: 1, minWidth: 180 },
  ];

  const platformOptions = useMemo(
    () => Array.from(new Set(devices.map((device) => device.platform).filter(Boolean))).sort(),
    [devices]
  );
  const filteredDevices = useMemo(() => {
    const query = deviceSearch.trim().toLowerCase();
    return devices.filter((device) => {
      const matchesPlatform = selectedPlatform === 'all' || device.platform === selectedPlatform;
      const matchesSearch =
        !query ||
        [device.name, device.serial_number, device.platform, device.threat_status]
          .filter(Boolean)
          .some((value) => String(value).toLowerCase().includes(query));

      return matchesPlatform && matchesSearch;
    });
  }, [devices, selectedPlatform, deviceSearch]);

  const hasActiveFilters = selectedPlatform !== 'all' || deviceSearch.trim();
  const selectedDeviceRows = useMemo(() => buildRawRows(selectedDevice), [selectedDevice]);
  const resetFilters = () => {
    setSelectedPlatform('all');
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
                  Trellix
                </Typography>
              </Stack>

              <Stack spacing={2}>
                <TextField
                  label="Trellix API URL"
                  value={form.base_url}
                  onChange={(e) => setForm({ ...form, base_url: e.target.value })}
                  fullWidth
                />
                <TextField
                  label="Trellix Token URL"
                  value={form.auth_url}
                  onChange={(e) => setForm({ ...form, auth_url: e.target.value })}
                  helperText="OAuth2 client-credentials token endpoint from the Trellix Developer Portal."
                  fullWidth
                />
                <TextField
                  label="Tenant Name"
                  value={form.tenant_name}
                  onChange={(e) => setForm({ ...form, tenant_name: e.target.value })}
                  fullWidth
                />
                <TextField
                  label="Tenant ID"
                  value={form.tenant_id}
                  onChange={(e) => setForm({ ...form, tenant_id: e.target.value })}
                  fullWidth
                />
                <TextField
                  label="Client ID"
                  value={form.client_id}
                  onChange={(e) => setForm({ ...form, client_id: e.target.value })}
                  fullWidth
                />
                <TextField
                  label="OAuth Scope"
                  value={form.scope}
                  onChange={(e) => setForm({ ...form, scope: e.target.value })}
                  helperText="Space-separated scopes the token should carry, e.g. epo.device.r. Add more (epo.grps.r, epo.tags.r, ...) if you use related-resource routes."
                  fullWidth
                />
                <TextField
                  label={connection?.has_client_secret ? 'Client Secret (saved)' : 'Client Secret'}
                  type="password"
                  value={form.client_secret}
                  onChange={(e) => setForm({ ...form, client_secret: e.target.value })}
                  helperText={connection?.has_client_secret ? 'Leave blank to keep the saved secret, or type a new one and save.' : ''}
                  fullWidth
                />
                <TextField
                  label={connection?.has_api_key ? 'API Key (saved)' : 'API Key'}
                  type="password"
                  value={form.api_key}
                  onChange={(e) => setForm({ ...form, api_key: e.target.value })}
                  helperText={connection?.has_api_key ? 'Leave blank to keep the saved API key, or type a new one and save.' : ''}
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
                  <Button
                    variant="outlined"
                    startIcon={<SyncIcon />}
                    onClick={handleSync}
                    disabled={syncing || connection?.last_test_status !== 'success'}
                  >
                    Sync Assets
                  </Button>
                </Stack>
              </Stack>
              {hasUnsavedSecret && (
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1.5 }}>
                  Save the updated Client Secret or API key before testing the connection.
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
                  Trellix Endpoints
                </Typography>
                <Button variant="outlined" size="small" startIcon={<RefreshIcon />} onClick={handleRefresh}>
                  Refresh
                </Button>
              </Stack>
              <Grid container spacing={2} alignItems="center" sx={{ mb: 2 }}>
                <Grid item xs={12} sm={5}>
                  <TextField
                    select
                    label="Platform"
                    size="small"
                    fullWidth
                    value={selectedPlatform}
                    onChange={(e) => setSelectedPlatform(e.target.value)}
                  >
                    <MenuItem value="all">All platforms</MenuItem>
                    {platformOptions.map((platform) => (
                      <MenuItem key={platform} value={platform}>
                        {platform}
                      </MenuItem>
                    ))}
                  </TextField>
                </Grid>
                <Grid item xs={12} sm={7}>
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

        <Grid item xs={12}>
          <Card sx={{ borderRadius: 2, boxShadow: 2 }}>
            <CardContent sx={{ p: 3 }}>
              <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 2 }}>
                <SecurityIcon color="primary" />
                <Typography variant="h6" fontWeight={700}>
                  Threat Events
                </Typography>
              </Stack>
              <Box sx={{ overflowX: 'auto', WebkitOverflowScrolling: 'touch' }}>
                <DataGrid
                  rows={threats}
                  columns={threatColumns}
                  autoHeight
                  pageSizeOptions={[10, 25]}
                  initialState={{ pagination: { paginationModel: { pageSize: 10 } } }}
                  sx={{
                    border: 'none',
                    minWidth: 700,
                    fontSize: 13.5,
                    '& .MuiDataGrid-columnHeaders': { backgroundColor: '#F8FAFC', borderBottom: '1px solid #E2E8F0' },
                    '& .MuiDataGrid-row': { cursor: 'default' },
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
                {selectedDevice?.name || selectedDevice?.serial_number || 'Trellix Endpoint'}
              </Typography>
              <Typography variant="body2" color="text.secondary" noWrap>
                {selectedDevice?.platform || 'Platform unavailable'} - {selectedDevice?.threat_status || 'Unknown status'}
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
              Full Trellix Payload
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

export default TrellixPanel;
