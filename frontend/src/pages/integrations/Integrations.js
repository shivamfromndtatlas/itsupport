import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Grid,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import ClearIcon from '@mui/icons-material/Clear';
import CloudSyncIcon from '@mui/icons-material/CloudSync';
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

function Integrations() {
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

  const columns = [
    { field: 'name', headerName: 'Device', flex: 1, minWidth: 180 },
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
      <Stack direction="row" alignItems="center" spacing={1.5} sx={{ mb: 3 }}>
        <CloudSyncIcon color="primary" />
        <Typography variant="h5" fontWeight={700}>
          Sure MDM
        </Typography>
      </Stack>

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
              <Typography variant="h6" fontWeight={700} sx={{ mb: 2 }}>
                SureMDM Devices
              </Typography>
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
              <DataGrid
                rows={filteredDevices}
                columns={columns}
                autoHeight
                disableRowSelectionOnClick
                pageSizeOptions={[10, 25]}
                initialState={{ pagination: { paginationModel: { pageSize: 10 } } }}
                sx={{ border: 0 }}
              />
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}

export default Integrations;
