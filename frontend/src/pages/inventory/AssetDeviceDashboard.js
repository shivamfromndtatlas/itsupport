import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Grid,
  Paper,
  Stack,
  Typography,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import AppsIcon from '@mui/icons-material/Apps';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import ComputerIcon from '@mui/icons-material/Computer';
import MemoryIcon from '@mui/icons-material/Memory';
import StorageIcon from '@mui/icons-material/Storage';
import DataTable from '../../components/common/DataTable';
import api from '../../api/axios';

const STATUS_COLORS = {
  available: 'success',
  assigned: 'primary',
  maintenance: 'warning',
  retired: 'default',
};

function DetailTile({ icon, label, value }) {
  return (
    <Paper variant="outlined" sx={{ p: 2, height: '100%', borderRadius: 2 }}>
      <Stack direction="row" spacing={1.5} alignItems="center">
        <Box sx={{ color: 'primary.main', display: 'flex' }}>{icon}</Box>
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 700, textTransform: 'uppercase' }}>
            {label}
          </Typography>
          <Typography variant="body1" fontWeight={600} noWrap>
            {value || '--'}
          </Typography>
        </Box>
      </Stack>
    </Paper>
  );
}

const formatLastSeen = (dateString) => {
  if (!dateString) return '--';
  try {
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return dateString;
    return date.toLocaleString('en-IN', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: true,
    });
  } catch (e) {
    return dateString;
  }
};

function AssetDeviceDashboard() {
  const { assetId } = useParams();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [report, setReport] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');

  const fetchReport = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await api.get(`/inventory/assets/${assetId}/device-dashboard/`);
      setReport(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load device dashboard.');
    } finally {
      setLoading(false);
    }
  }, [assetId]);

  useEffect(() => {
    fetchReport();
  }, [fetchReport]);

  const appRows = useMemo(
    () => (report?.installed_apps || []).map((app, index) => ({ id: `${app.name || 'app'}-${index}`, ...app })),
    [report]
  );

  const attributeRows = useMemo(() => {
    const attrs = report?.asset?.attribute_values_with_names || report?.asset?.attribute_values || {};
    return Object.entries(attrs)
      .filter(([key, value]) => value !== '' && value !== null && value !== undefined && typeof value !== 'object')
      .map(([key, value]) => ({ id: key, field: key, value }));
  }, [report]);

  const appColumns = [
    { field: 'name', headerName: 'Application', flex: 1, minWidth: 220, renderCell: ({ value }) => value || '--' },
    { field: 'application_package', headerName: 'Package', flex: 1, minWidth: 220, renderCell: ({ value }) => value || '--' },
    { field: 'application_type', headerName: 'Type', width: 130, renderCell: ({ value }) => value || '--' },
    { field: 'user_name', headerName: 'User', width: 150, renderCell: ({ value }) => value || '--' },
    { field: 'version', headerName: 'Version', width: 160, renderCell: ({ value }) => value || '--' },
  ];

  const attributeColumns = [
    { field: 'field', headerName: 'Field', flex: 1, minWidth: 180 },
    { field: 'value', headerName: 'Value', flex: 1.5, minWidth: 220 },
  ];

  if (loading) {
    return (
      <Box sx={{ minHeight: 360, display: 'grid', placeItems: 'center' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Stack spacing={2}>
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/inventory/assets')} sx={{ alignSelf: 'flex-start' }}>
          Back to assets
        </Button>
        <Alert severity="error">{error}</Alert>
      </Stack>
    );
  }

  const asset = report?.asset || {};
  const device = report?.device || {};

  const handleReportUpload = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;

    setUploading(true);
    setUploadError('');
    try {
      const payload = new FormData();
      payload.append('file', file);
      await api.post('/inventory/assets/installed-app-report/upload/', payload, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      await fetchReport();
    } catch (err) {
      setUploadError(err.response?.data?.detail || 'Failed to upload installed app report.');
    } finally {
      setUploading(false);
    }
  };

  return (
    <Stack spacing={2.5}>
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} alignItems={{ xs: 'stretch', sm: 'center' }}>
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/inventory/assets')} sx={{ alignSelf: { xs: 'flex-start', sm: 'center' } }}>
          Back
        </Button>
        <Box sx={{ flex: 1 }}>
          <Typography variant="h6" fontWeight={700}>
            {asset.asset_id || 'Device'} Dashboard
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {device.name || asset.notes || device.serial_number || 'Hardware asset'}
          </Typography>
        </Box>
        <Chip
          label={asset.status || 'unknown'}
          color={STATUS_COLORS[asset.status] || 'default'}
          sx={{ textTransform: 'capitalize', alignSelf: { xs: 'flex-start', sm: 'center' } }}
        />
      </Stack>

      <Grid container spacing={2}>
        <Grid item xs={12} sm={6} md={3}>
          <DetailTile icon={<ComputerIcon />} label="Model" value={device.model || asset.asset_type_name} />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <DetailTile icon={<MemoryIcon />} label="Processor" value={device.processor} />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <DetailTile icon={<MemoryIcon />} label="RAM" value={device.ram} />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <DetailTile icon={<StorageIcon />} label="Storage" value={device.storage} />
        </Grid>
      </Grid>

      <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
        <Grid container spacing={2}>
          <Grid item xs={12} sm={6} md={3}>
            <Typography variant="caption" color="text.secondary" fontWeight={700}>Serial Number</Typography>
            <Typography variant="body2">{device.serial_number || '--'}</Typography>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Typography variant="caption" color="text.secondary" fontWeight={700}>System Tag</Typography>
            <Typography variant="body2">{device.system_tag || '--'}</Typography>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Typography variant="caption" color="text.secondary" fontWeight={700}>Platform</Typography>
            <Typography variant="body2">{device.platform || '--'}</Typography>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Typography variant="caption" color="text.secondary" fontWeight={700}>MDM Device ID</Typography>
            <Typography variant="body2">{device.device_id || '--'}</Typography>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Typography variant="caption" color="text.secondary" fontWeight={700}>MDM Category</Typography>
            <Typography variant="body2">{device.category || '--'}</Typography>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Typography variant="caption" color="text.secondary" fontWeight={700}>Manufacturer</Typography>
            <Typography variant="body2">{device.manufacturer || '--'}</Typography>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Typography variant="caption" color="text.secondary" fontWeight={700}>Assigned User</Typography>
            <Typography variant="body2">{device.assigned_user_name || '--'}</Typography>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Typography variant="caption" color="text.secondary" fontWeight={700}>Last Seen</Typography>
            <Typography variant="body2">{formatLastSeen(device.last_seen)}</Typography>
          </Grid>
        </Grid>
      </Paper>

      {report?.installed_apps_error && (
        <Alert severity="warning">{report.installed_apps_error}</Alert>
      )}

      <Paper sx={{ p: 2, borderRadius: 2 }}>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} alignItems={{ xs: 'stretch', sm: 'center' }} sx={{ mb: 2 }}>
          <Stack direction="row" spacing={1} alignItems="center" sx={{ flex: 1 }}>
            <AppsIcon color="primary" />
            <Typography variant="subtitle1" fontWeight={700}>
              Installed Applications
            </Typography>
            <Chip label={appRows.length} size="small" />
            {report?.installed_apps_source === 'uploaded_report' && <Chip label="Uploaded report" size="small" color="primary" variant="outlined" />}
          </Stack>
          <Button
            component="label"
            variant="outlined"
            size="small"
            startIcon={<CloudUploadIcon />}
            disabled={uploading}
            sx={{ alignSelf: { xs: 'flex-start', sm: 'center' } }}
          >
            {uploading ? 'Uploading...' : 'Upload Report'}
            <input hidden type="file" accept=".xlsx" onChange={handleReportUpload} />
          </Button>
        </Stack>
        {uploadError && <Alert severity="error" sx={{ mb: 2 }}>{uploadError}</Alert>}
        <DataTable rows={appRows} columns={appColumns} searchable pageSize={25} />
      </Paper>

      <Paper sx={{ p: 2, borderRadius: 2 }}>
        <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 2 }}>
          Device Attributes
        </Typography>
        <DataTable rows={attributeRows} columns={attributeColumns} pageSize={10} />
      </Paper>
    </Stack>
  );
}

export default AssetDeviceDashboard;
