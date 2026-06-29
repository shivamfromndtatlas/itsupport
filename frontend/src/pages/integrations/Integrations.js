import React, { useCallback, useEffect, useMemo, useState } from 'react';
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
import { DataGrid } from '@mui/x-data-grid';
import api from '../../api/axios';

const EMPTY_FORM = {
  base_url: 'https://suremdm.42gears.com/api',
  username: '',
  password: '',
  api_key: '',
  is_active: true,
};

const SUMMARY_FIELDS = [
  ['Device Name', 'name'],
  ['Serial Number', 'serial_number'],
  ['System Tag', 'system_tag'],
  ['MDM Device ID', 'suremdm_device_id'],
  ['Category', 'category'],
  ['Platform', 'platform'],
  ['Model', 'model'],
  ['Manufacturer', 'manufacturer'],
  ['Processor', 'processor'],
  ['RAM', 'ram'],
  ['Storage', 'storage'],
  ['Last Seen', 'last_seen'],
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
    .filter(([key]) => !['id', 'raw', 'platform_model'].includes(key))
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

function Integrations() {
  const theme = useTheme();
  const fullScreen = useMediaQuery(theme.breakpoints.down('sm'));
  const [form, setForm] = useState(EMPTY_FORM);
  const [connection, setConnection] = useState(null);
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [message, setMessage] = useState(null);
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [selectedPlatform, setSelectedPlatform] = useState('all');
  const [deviceSearch, setDeviceSearch] = useState('');
  const [selectedDevice, setSelectedDevice] = useState(null);

  const showMessage = (severity, text) => setMessage({ severity, text });

  const loadConnection = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/integrations/suremdm/connection/');
      if (res.data?.configured) {
        setConnection(res.data);
        setForm({
          base_url: res.data.base_url || EMPTY_FORM.base_url,
          username: res.data.username || '',
          password: '',
          api_key: '',
          is_active: res.data.is_active ?? true,
        });
      }
    } catch (err) {
      showMessage('error', 'Failed to load SureMDM connection.');
    } finally {
      setLoading(false);
    }
  }, []);

  const loadDevices = async () => {
    try {
      const res = await api.get('/integrations/suremdm/devices/?limit=500');
      setDevices((res.data?.results || []).map((device, index) => ({
        id: device.suremdm_device_id || index,
        ...device,
        platform_model: [device.platform, device.model].filter(Boolean).join(' / '),
      })));
    } catch (err) {
      setDevices([]);
    }
  };

  useEffect(() => {
    loadConnection();
  }, [loadConnection]);

  useEffect(() => {
    if (connection?.last_test_status === 'success') {
      loadDevices();
    }
  }, [connection]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload = { ...form };
      const res = await api.post('/integrations/suremdm/connection/', payload);
      setConnection(res.data);
      setForm({ ...form, password: '', api_key: '' });
      showMessage('success', 'SureMDM connection saved.');
    } catch (err) {
      showMessage('error', err.response?.data?.detail || 'Failed to save SureMDM connection.');
    } finally {
      setSaving(false);
    }
  };

  const hasUnsavedSecret = Boolean(form.password || form.api_key);

  const handleTest = async () => {
    setTesting(true);
    try {
      const res = await api.post('/integrations/suremdm/test/');
      await loadConnection();
      showMessage('success', res.data?.message || 'Connected to SureMDM successfully.');
    } catch (err) {
      await loadConnection();
      showMessage('error', err.response?.data?.message || err.response?.data?.detail || 'SureMDM connection test failed.');
    } finally {
      setTesting(false);
    }
  };

  const handleSync = async () => {
    setSyncing(true);
    try {
      const res = await api.post('/integrations/suremdm/sync-assets/');
      await loadConnection();
      await loadDevices();
      showMessage('success', `Synced ${res.data?.total || 0} SureMDM devices into IT Assets.`);
    } catch (err) {
      showMessage('error', err.response?.data?.detail || 'SureMDM asset sync failed.');
    } finally {
      setSyncing(false);
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
            {value || row.serial_number || row.suremdm_device_id || 'Unnamed device'}
          </Typography>
        </Button>
      ),
    },
    { field: 'serial_number', headerName: 'Serial Number', flex: 1, minWidth: 160 },
    { field: 'category', headerName: 'MDM Category', flex: 1, minWidth: 150 },
    { field: 'platform_model', headerName: 'Platform / Model', flex: 1, minWidth: 180 },
    { field: 'last_seen', headerName: 'Last Seen', flex: 1, minWidth: 180 },
  ];

  const categoryCounts = devices.reduce((counts, device) => {
    const category = device.category || 'Uncategorized';
    counts[category] = (counts[category] || 0) + 1;
    return counts;
  }, {});
  const categories = Object.entries(categoryCounts).sort(([a], [b]) => a.localeCompare(b));
  const platformOptions = useMemo(
    () => Array.from(new Set(devices.map((device) => device.platform).filter(Boolean))).sort(),
    [devices]
  );
  const filteredDevices = useMemo(() => {
    const query = deviceSearch.trim().toLowerCase();
    return devices.filter((device) => {
      const category = device.category || 'Uncategorized';
      const matchesCategory = selectedCategory === 'all' || category === selectedCategory;
      const matchesPlatform = selectedPlatform === 'all' || device.platform === selectedPlatform;
      const matchesSearch =
        !query ||
        [
          device.name,
          device.serial_number,
          device.category,
          device.platform_model,
          device.last_seen,
        ]
          .filter(Boolean)
          .some((value) => String(value).toLowerCase().includes(query));

      return matchesCategory && matchesPlatform && matchesSearch;
    });
  }, [devices, selectedCategory, selectedPlatform, deviceSearch]);

  const hasActiveFilters = selectedCategory !== 'all' || selectedPlatform !== 'all' || deviceSearch.trim();
  const selectedDeviceRows = useMemo(() => buildRawRows(selectedDevice), [selectedDevice]);
  const resetFilters = () => {
    setSelectedCategory('all');
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
                  SureMDM
                </Typography>
              </Stack>

              <Stack spacing={2}>
                <TextField
                  label="SureMDM URL"
                  value={form.base_url}
                  onChange={(e) => setForm({ ...form, base_url: e.target.value })}
                  helperText="You can paste your console URL; the portal will use the matching /api endpoint."
                  fullWidth
                />
                <TextField
                  label="Username"
                  value={form.username}
                  onChange={(e) => setForm({ ...form, username: e.target.value })}
                  fullWidth
                />
                <TextField
                  label={connection?.has_password ? 'Password (saved)' : 'Password'}
                  type="password"
                  value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                  helperText={connection?.has_password ? 'Leave blank to keep the saved password, or type a new one and save.' : ''}
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
                  Save the updated password or API key before testing the connection.
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
                  SureMDM Devices
                </Typography>
                <Button variant="outlined" size="small" startIcon={<RefreshIcon />} onClick={handleRefresh}>
                  Refresh
                </Button>
              </Stack>
              {categories.length > 0 && (
                <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap" sx={{ mb: 2 }}>
                  <Chip
                    label={`All: ${devices.length}`}
                    size="small"
                    color="primary"
                    variant={selectedCategory === 'all' ? 'filled' : 'outlined'}
                    onClick={() => setSelectedCategory('all')}
                  />
                  {categories.map(([category, count]) => (
                    <Chip
                      key={category}
                      label={`${category}: ${count}`}
                      size="small"
                      color="primary"
                      variant={selectedCategory === category ? 'filled' : 'outlined'}
                      onClick={() => setSelectedCategory(category)}
                    />
                  ))}
                </Stack>
              )}
              <Grid container spacing={2} alignItems="center" sx={{ mb: 2 }}>
                <Grid item xs={12} sm={4}>
                  <TextField
                    select
                    label="MDM Category"
                    size="small"
                    fullWidth
                    value={selectedCategory}
                    onChange={(e) => setSelectedCategory(e.target.value)}
                  >
                    <MenuItem value="all">All categories</MenuItem>
                    {categories.map(([category]) => (
                      <MenuItem key={category} value={category}>
                        {category}
                      </MenuItem>
                    ))}
                  </TextField>
                </Grid>
                <Grid item xs={12} sm={4}>
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
                <Grid item xs={12} sm={4}>
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
                    '& .MuiDataGrid-columnSeparator': { display: 'none' },
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
                {selectedDevice?.name || selectedDevice?.serial_number || 'MDM Device'}
              </Typography>
              <Typography variant="body2" color="text.secondary" noWrap>
                {selectedDevice?.category || 'Uncategorized'} - {[selectedDevice?.platform, selectedDevice?.model].filter(Boolean).join(' / ') || 'Platform unavailable'}
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
              Full MDM Payload
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

export default Integrations;
