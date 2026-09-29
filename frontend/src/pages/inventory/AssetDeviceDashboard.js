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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import AppsIcon from '@mui/icons-material/Apps';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import ComputerIcon from '@mui/icons-material/Computer';
import MemoryIcon from '@mui/icons-material/Memory';
import StorageIcon from '@mui/icons-material/Storage';
import RefreshIcon from '@mui/icons-material/Refresh';
import VerifiedUserIcon from '@mui/icons-material/VerifiedUser';
import FactCheckIcon from '@mui/icons-material/FactCheck';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import DataTable from '../../components/common/DataTable';
import api from '../../api/axios';

const STATUS_COLORS = {
  available: 'success',
  assigned: 'primary',
  maintenance: 'warning',
  retired: 'default',
};

const ATTRIBUTE_LABELS = {
  2: 'Brand',
  3: 'RAM',
  4: 'Device ID',
  5: 'Product ID',
  6: 'Screen Size',
  7: 'Model',
  8: 'Processor',
  9: 'Condition',
  10: 'Availability Status',
  brand: 'Brand',
  ram: 'RAM',
  device_id: 'Device ID',
  product_id: 'Product ID',
  screen_size: 'Screen Size',
  model: 'Model',
  processor: 'Processor',
  condition: 'Condition',
  availability_status: 'Availability Status',
  'availability status': 'Availability Status',
};

const SYSTEM_ATTRIBUTE_KEYS = new Set([
  'asset id',
  'asset type',
  'status',
  'condition',
  'availability status',
  'availability_status',
]);

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

const formatDateOnly = (value) => {
  if (!value) return '--';
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(value));
  if (!match) return String(value);
  const [, year, month, day] = match;
  return `${day}-${month}-${year}`;
};

const WARRANTY_STATUS_COLORS = { active: 'success', expired: 'error', unknown: 'default' };

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
  const [refreshingSupport, setRefreshingSupport] = useState(false);
  const [supportMessage, setSupportMessage] = useState('');

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

  const allocationHistoryRows = useMemo(
    () => (report?.allocation_history || []).map((allocation, index) => ({
      id: allocation.id || `${allocation.asset || assetId}-${index}`,
      ...allocation,
    })),
    [report, assetId]
  );

  const attributeRows = useMemo(() => {
    const attrs = report?.asset?.attribute_values_with_names || report?.asset?.attribute_values || {};
    const rows = [];
    const seenFields = new Set();

    Object.entries(attrs).forEach(([key, value]) => {
      if (value === '' || value === null || value === undefined || typeof value === 'object') return;
      if (SYSTEM_ATTRIBUTE_KEYS.has(String(key).trim().toLowerCase())) return;

      const field = ATTRIBUTE_LABELS[key] || ATTRIBUTE_LABELS[String(key).trim().toLowerCase()] || key;
      const normalizedField = String(field).trim().toLowerCase();
      if (seenFields.has(normalizedField)) return;

      seenFields.add(normalizedField);
      rows.push({ id: normalizedField, field, value });
    });

    return rows;
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
  const supportInfo = report?.support_info || null;
  const warranty = supportInfo?.warranty || {};
  const productSpecs = supportInfo?.product_specifications || [];

  const handleRefreshSupportInfo = async () => {
    setRefreshingSupport(true);
    setSupportMessage('');
    try {
      await api.post(`/inventory/assets/${assetId}/refresh-support-info/`);
      setSupportMessage('Vendor support data refreshed.');
      await fetchReport();
    } catch (err) {
      const data = err.response?.data;
      setSupportMessage(data?.fetch_error || data?.detail || 'Failed to fetch vendor support data.');
      await fetchReport();
    } finally {
      setRefreshingSupport(false);
    }
  };

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

      {supportInfo?.supported && (
        <Paper sx={{ p: 2, borderRadius: 2 }}>
          <Stack
            direction={{ xs: 'column', sm: 'row' }}
            spacing={1.5}
            alignItems={{ xs: 'stretch', sm: 'center' }}
            sx={{ mb: 2 }}
          >
            <Stack direction="row" spacing={1} alignItems="center" sx={{ flex: 1 }}>
              <VerifiedUserIcon color="primary" />
              <Typography variant="subtitle1" fontWeight={700}>
                Product Support (Warranty)
              </Typography>
              {supportInfo.manufacturer && (
                <Chip label={supportInfo.manufacturer.toUpperCase()} size="small" variant="outlined" />
              )}
              {warranty.status && (
                <Chip
                  label={warranty.status}
                  size="small"
                  color={WARRANTY_STATUS_COLORS[warranty.status] || 'default'}
                  sx={{ textTransform: 'capitalize' }}
                />
              )}
            </Stack>
            <Typography variant="caption" color="text.secondary">
              {supportInfo.fetched_at
                ? `Fetched ${formatLastSeen(supportInfo.fetched_at)}`
                : 'Not fetched yet'}
            </Typography>
            <Button
              variant="outlined"
              size="small"
              startIcon={<RefreshIcon />}
              onClick={handleRefreshSupportInfo}
              disabled={refreshingSupport}
              sx={{ alignSelf: { xs: 'flex-start', sm: 'center' } }}
            >
              {refreshingSupport ? 'Fetching...' : 'Refresh from vendor'}
            </Button>
          </Stack>

          {supportMessage && (
            <Alert
              severity={supportInfo.fetch_status === 'success' ? 'success' : 'warning'}
              sx={{ mb: 2 }}
              onClose={() => setSupportMessage('')}
            >
              {supportMessage}
            </Alert>
          )}
          {!supportMessage && supportInfo.fetch_status === 'error' && supportInfo.fetch_error && (
            <Alert severity="warning" sx={{ mb: 2 }}>{supportInfo.fetch_error}</Alert>
          )}
          {supportInfo.fetch_status === 'pending' && (
            <Alert severity="info" sx={{ mb: 2 }}>
              Warranty and configuration data has not been fetched yet. Click "Refresh from vendor".
            </Alert>
          )}

          <Grid container spacing={2}>
            <Grid item xs={12} sm={6} md={3}>
              <Typography variant="caption" color="text.secondary" fontWeight={700}>Service Tag / Serial</Typography>
              <Typography variant="body2">{supportInfo.service_tag || '--'}</Typography>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Typography variant="caption" color="text.secondary" fontWeight={700}>Plan Taken</Typography>
              <Typography variant="body2">{warranty.plan || '--'}</Typography>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Typography variant="caption" color="text.secondary" fontWeight={700}>Start Date</Typography>
              <Typography variant="body2">{formatDateOnly(warranty.start_date)}</Typography>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Typography variant="caption" color="text.secondary" fontWeight={700}>Valid Until</Typography>
              <Typography variant="body2">{formatDateOnly(warranty.end_date)}</Typography>
            </Grid>
            {supportInfo.product_name && (
              <Grid item xs={12} sm={6} md={3}>
                <Typography variant="caption" color="text.secondary" fontWeight={700}>Product</Typography>
                <Typography variant="body2">{supportInfo.product_name}</Typography>
              </Grid>
            )}
            {supportInfo.ship_date && (
              <Grid item xs={12} sm={6} md={3}>
                <Typography variant="caption" color="text.secondary" fontWeight={700}>Ship Date</Typography>
                <Typography variant="body2">{formatDateOnly(supportInfo.ship_date)}</Typography>
              </Grid>
            )}
          </Grid>

          {(warranty.entitlements || []).length > 0 && (
            <Box sx={{ width: '100%', overflowX: 'auto', mt: 2 }}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Plan</TableCell>
                    <TableCell>Start</TableCell>
                    <TableCell>End</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {warranty.entitlements.map((row, index) => (
                    <TableRow key={`${row.plan}-${index}`} hover>
                      <TableCell>{row.plan || '--'}</TableCell>
                      <TableCell>{formatDateOnly(row.start_date)}</TableCell>
                      <TableCell>{formatDateOnly(row.end_date)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Box>
          )}
        </Paper>
      )}

      {supportInfo?.supported && (
        <Paper sx={{ p: 2, borderRadius: 2 }}>
          <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}>
            <FactCheckIcon color="primary" />
            <Typography variant="subtitle1" fontWeight={700}>
              Review Product Specifications
            </Typography>
            <Chip label={productSpecs.length} size="small" />
            {supportInfo.source_url && (
              <Button
                size="small"
                endIcon={<OpenInNewIcon />}
                component="a"
                href={supportInfo.source_url}
                target="_blank"
                rel="noopener noreferrer"
              >
                Vendor page
              </Button>
            )}
          </Stack>
          {productSpecs.length === 0 ? (
            <Alert severity="info">
              {supportInfo.fetch_status === 'success'
                ? 'The vendor page did not list an original configuration for this device.'
                : 'Original configuration has not been fetched yet. Use "Refresh from vendor" above.'}
            </Alert>
          ) : (
            <>
              {supportInfo.service_tag && (
                <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
                  Original configuration for {supportInfo.manufacturer === 'dell' ? 'Service Tag' : 'Serial'}{' '}
                  {supportInfo.service_tag} — the system specifications it shipped with.
                </Typography>
              )}
              <Box sx={{ width: '100%', overflowX: 'auto' }}>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell sx={{ width: 140 }}>Code</TableCell>
                      <TableCell>Description</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {productSpecs.map((spec, index) => (
                      <TableRow key={`${spec.code || 'item'}-${index}`} hover>
                        <TableCell sx={{ whiteSpace: 'nowrap', fontFamily: 'monospace' }}>{spec.code || '--'}</TableCell>
                        <TableCell>{spec.description || '--'}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Box>
            </>
          )}
        </Paper>
      )}

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
            {report?.installed_apps_source === 'suremdm_sync' && (
              <Chip
                label={`Synced from SureMDM${report?.installed_apps_synced_at ? ` • ${formatLastSeen(report.installed_apps_synced_at)}` : ''}`}
                size="small"
                color="success"
                variant="outlined"
              />
            )}
            {report?.installed_apps_source === 'uploaded_report' && <Chip label="Uploaded report" size="small" color="primary" variant="outlined" />}
          </Stack>
          <Button
            component="label"
            variant="outlined"
            size="small"
            startIcon={<CloudUploadIcon />}
            disabled={uploading}
            sx={{ alignSelf: { xs: 'flex-start', sm: 'center' } }}
            title="Installed apps now sync automatically from SureMDM. Only use this to manually override a device's data."
          >
            {uploading ? 'Uploading...' : 'Upload Report'}
            <input hidden type="file" accept=".xlsx" onChange={handleReportUpload} />
          </Button>
        </Stack>
        {uploadError && <Alert severity="error" sx={{ mb: 2 }}>{uploadError}</Alert>}
        <DataTable rows={appRows} columns={appColumns} searchable pageSize={25} onRefresh={fetchReport} refreshLabel="Refresh" />
      </Paper>

      <Paper sx={{ p: 2, borderRadius: 2 }}>
        <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 2 }}>
          Device Attributes
        </Typography>
        <DataTable rows={attributeRows} columns={attributeColumns} pageSize={10} onRefresh={fetchReport} refreshLabel="Refresh" />
      </Paper>

      <Paper sx={{ p: 2, borderRadius: 2 }}>
        <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 2 }}>
          Asset Allocation History
        </Typography>
        {allocationHistoryRows.length === 0 ? (
          <Alert severity="info">No allocation history found for this asset.</Alert>
        ) : (
          <Box sx={{ width: '100%', overflowX: 'auto' }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Assigned To</TableCell>
                  <TableCell>Assigned By</TableCell>
                  <TableCell>Assigned Date</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Recovered By</TableCell>
                  <TableCell>Recovered Date</TableCell>
                  <TableCell>Notes</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {allocationHistoryRows.map((row) => (
                  <TableRow key={row.id} hover>
                    <TableCell>{row.employee_detail?.full_name || row.employee_detail?.employee_id || '--'}</TableCell>
                    <TableCell>{row.assigned_by_name || '--'}</TableCell>
                    <TableCell>{row.assigned_date || '--'}</TableCell>
                    <TableCell>
                      <Chip
                        label={(row.status || '').replace(/_/g, ' ') || '--'}
                        color={row.status === 'active' ? 'primary' : 'default'}
                        size="small"
                        sx={{ textTransform: 'capitalize' }}
                      />
                    </TableCell>
                    <TableCell>{row.recovered_by_name || '--'}</TableCell>
                    <TableCell>{row.recovered_date || '--'}</TableCell>
                    <TableCell>{row.notes || '--'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Box>
        )}
      </Paper>
    </Stack>
  );
}

export default AssetDeviceDashboard;
