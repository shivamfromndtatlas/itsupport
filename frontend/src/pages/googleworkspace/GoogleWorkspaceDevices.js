import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Link,
  MenuItem,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import ClearIcon from '@mui/icons-material/Clear';
import DownloadIcon from '@mui/icons-material/Download';
import RefreshIcon from '@mui/icons-material/Refresh';
import { DataGrid } from '@mui/x-data-grid';
import api from '../../api/axios';
import { typeOf } from './UserDevicesPanel';
import { StatCard, formatDateTime, gridSx, userDashboardPath } from './shared';

const SOURCE_LABELS = { mobile: 'Mobile devices', cloud_identity: 'Computers and laptops' };

const csvCell = (value) => {
  const text = String(value ?? '');
  return /[",\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
};

const exportCsv = (rows) => {
  const header = ['Type', 'Make', 'Model', 'Serial number', 'Platform', 'OS', 'Ownership', 'Users', 'First seen', 'Last sync', 'Portal asset'];
  const lines = rows.map((row) => [
    row.type.label, row.make, row.model, row.serial, row.platform, row.os, row.ownership,
    row.users.join('; '), row.first_seen, row.last_sync, row.portal_asset?.asset_id || '',
  ]);
  const csv = [header, ...lines].map((line) => line.map(csvCell).join(',')).join('\r\n');
  const url = URL.createObjectURL(new Blob([`﻿${csv}`], { type: 'text/csv;charset=utf-8' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = 'google-workspace-devices.csv';
  link.click();
  URL.revokeObjectURL(url);
};

function GoogleWorkspaceDevices() {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');
  const [platformFilter, setPlatformFilter] = useState('all');
  const [portalFilter, setPortalFilter] = useState('all');

  const load = useCallback(async (refresh = false) => {
    setLoading(true);
    setError('');
    try {
      const res = await api.get('/integrations/google-workspace/devices/', { params: refresh ? { refresh: 1 } : {} });
      setData(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load devices.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const rows = useMemo(() => (data?.devices || []).map((device) => ({ ...device, type: typeOf(device) })), [data]);
  const platforms = useMemo(() => [...new Set(rows.map((row) => row.platform).filter(Boolean))].sort(), [rows]);
  const failedSources = Object.entries(data?.sources || {}).filter(([, source]) => !source.ok);

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase();
    return rows.filter((row) => {
      if (typeFilter === 'computer' ? row.type.key === 'mobile' || row.type.key === 'laptop' : typeFilter !== 'all' && row.type.key !== typeFilter) return false;
      if (platformFilter !== 'all' && row.platform !== platformFilter) return false;
      if (portalFilter === 'matched' && !row.portal_asset) return false;
      if (portalFilter === 'unmatched' && row.portal_asset) return false;
      if (!query) return true;
      return [row.make, row.model, row.serial, row.os, row.hostname, row.portal_asset?.asset_id, ...row.users].some(
        (value) => value && String(value).toLowerCase().includes(query)
      );
    });
  }, [rows, search, typeFilter, platformFilter, portalFilter]);

  const hasFilters = search.trim() || typeFilter !== 'all' || platformFilter !== 'all' || portalFilter !== 'all';
  const reset = () => {
    setSearch('');
    setTypeFilter('all');
    setPlatformFilter('all');
    setPortalFilter('all');
  };

  const columns = [
    {
      field: 'type',
      headerName: 'Type',
      width: 130,
      valueGetter: (value) => value.label,
      renderCell: ({ row }) => (
        <Tooltip title={row.type.note || ''}>
          <Chip size="small" variant="outlined" icon={row.type.icon} label={row.type.label} />
        </Tooltip>
      ),
    },
    { field: 'make', headerName: 'Make', flex: 0.8, minWidth: 110, valueGetter: (value) => value || '—' },
    { field: 'model', headerName: 'Model', flex: 1, minWidth: 140, valueGetter: (value) => value || '—' },
    {
      field: 'serial',
      headerName: 'Serial number',
      flex: 1,
      minWidth: 150,
      renderCell: ({ row }) =>
        row.serial ? (
          <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>{row.serial}</Typography>
        ) : (
          <Tooltip title="Google did not report a serial number. Personal Android and iOS devices usually withhold it.">
            <Typography variant="body2" color="text.secondary">Not reported</Typography>
          </Tooltip>
        ),
    },
    { field: 'os', headerName: 'OS', flex: 0.8, minWidth: 120, valueGetter: (value, row) => value || row.platform || '—' },
    {
      field: 'users',
      headerName: 'Signed-in users',
      flex: 1.6,
      minWidth: 240,
      valueGetter: (value) => (value || []).join(', '),
      renderCell: ({ row }) => {
        if (!row.users.length) return <Typography variant="body2" color="text.secondary">—</Typography>;
        return (
          <Stack direction="row" spacing={0.5} alignItems="center" sx={{ minWidth: 0 }}>
            <Link
              component="button"
              type="button"
              underline="hover"
              onClick={() => navigate(userDashboardPath(row.users[0]))}
              sx={{ fontSize: 13.5, fontWeight: 600, textAlign: 'left' }}
              noWrap
            >
              {row.users[0]}
            </Link>
            {row.users.length > 1 && (
              <Tooltip title={row.users.slice(1).join(', ')}>
                <Chip size="small" variant="outlined" label={`+${row.users.length - 1}`} />
              </Tooltip>
            )}
          </Stack>
        );
      },
    },
    {
      field: 'ownership',
      headerName: 'Ownership',
      width: 110,
      valueGetter: (value) => (value ? value.charAt(0).toUpperCase() + value.slice(1) : '—'),
    },
    {
      field: 'last_sync',
      headerName: 'Last sync',
      width: 150,
      valueGetter: (value) => (value ? new Date(value) : null),
      renderCell: ({ row }) => formatDateTime(row.last_sync),
    },
    {
      field: 'portal_asset',
      headerName: 'Portal asset',
      width: 125,
      valueGetter: (value) => value?.asset_id || '',
      renderCell: ({ row }) =>
        row.portal_asset ? (
          <Link
            component="button"
            type="button"
            underline="hover"
            onClick={() => navigate(`/inventory/assets/${row.portal_asset.id}`)}
            sx={{ fontSize: 13.5, fontWeight: 600 }}
          >
            {row.portal_asset.asset_id}
          </Link>
        ) : (
          <Typography variant="body2" color="text.secondary">—</Typography>
        ),
    },
  ];

  return (
    <Box>
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} alignItems={{ sm: 'center' }} justifyContent="space-between" sx={{ mb: 2 }}>
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/google-workspace')} sx={{ alignSelf: 'flex-start' }}>
          All users
        </Button>
        <Stack direction="row" spacing={1}>
          <Button variant="outlined" size="small" startIcon={<DownloadIcon />} onClick={() => exportCsv(filtered)} disabled={!filtered.length}>
            Export CSV
          </Button>
          <Button
            variant="contained"
            size="small"
            startIcon={loading ? <CircularProgress size={14} color="inherit" /> : <RefreshIcon />}
            onClick={() => load(true)}
            disabled={loading}
          >
            Refresh
          </Button>
        </Stack>
      </Stack>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {failedSources.map(([name, source]) => (
        <Alert key={name} severity="warning" sx={{ mb: 2 }}>
          {SOURCE_LABELS[name] || name} could not be read, so devices of that kind are missing from this list: {source.error}
        </Alert>
      ))}
      {loading && !data && (
        <Stack direction="row" spacing={1.5} alignItems="center" sx={{ py: 6, justifyContent: 'center' }}>
          <CircularProgress size={22} />
          <Typography variant="body2" color="text.secondary">
            Reading the device list from Google. This can take a few seconds on a large account.
          </Typography>
        </Stack>
      )}

      {data && (
        <>
          <Box sx={{ display: 'grid', gap: 1.5, gridTemplateColumns: { xs: 'repeat(2, 1fr)', md: 'repeat(5, 1fr)' }, mb: 2 }}>
            <StatCard label="Devices" value={data.summary.total} />
            <StatCard label="Laptops" value={data.summary.laptops} />
            <StatCard label="Other computers" value={data.summary.other_computers} />
            <StatCard label="Mobile" value={data.summary.mobile} />
            <StatCard label="In portal inventory" value={data.summary.in_portal} hint={`${data.summary.total - data.summary.in_portal} not matched`} />
          </Box>

          <Card sx={{ borderRadius: 2, boxShadow: 2 }}>
            <CardContent sx={{ p: { xs: 2, md: 3 } }}>
              <Box sx={{ display: 'grid', gap: 1.5, gridTemplateColumns: { xs: '1fr', md: '1.6fr 0.8fr 0.8fr 0.9fr auto' }, alignItems: 'center', mb: 2 }}>
                <TextField label="Search model, serial, user, asset…" size="small" value={search} onChange={(e) => setSearch(e.target.value)} />
                <TextField select label="Type" size="small" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
                  <MenuItem value="all">All types</MenuItem>
                  <MenuItem value="laptop">Laptops</MenuItem>
                  <MenuItem value="computer">Other computers</MenuItem>
                  <MenuItem value="mobile">Mobile</MenuItem>
                </TextField>
                <TextField select label="Platform" size="small" value={platformFilter} onChange={(e) => setPlatformFilter(e.target.value)}>
                  <MenuItem value="all">All platforms</MenuItem>
                  {platforms.map((platform) => (
                    <MenuItem key={platform} value={platform}>{platform}</MenuItem>
                  ))}
                </TextField>
                <TextField select label="Portal inventory" size="small" value={portalFilter} onChange={(e) => setPortalFilter(e.target.value)}>
                  <MenuItem value="all">Any</MenuItem>
                  <MenuItem value="matched">In inventory</MenuItem>
                  <MenuItem value="unmatched">Not in inventory</MenuItem>
                </TextField>
                <Button variant="outlined" startIcon={<ClearIcon />} onClick={reset} disabled={!hasFilters}>Clear</Button>
              </Box>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
                Showing {filtered.length} of {rows.length} devices
              </Typography>
              <Box sx={{ overflowX: 'auto' }}>
                <DataGrid
                  rows={filtered}
                  columns={columns}
                  autoHeight
                  disableRowSelectionOnClick
                  pageSizeOptions={[25, 50, 100]}
                  initialState={{ pagination: { paginationModel: { pageSize: 25 } } }}
                  sx={{ ...gridSx, minWidth: 1100, '& .MuiDataGrid-row': { cursor: 'default' } }}
                />
              </Box>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1.5 }}>
                Devices registered with Google that someone has signed in on with a company account: mobile management, Endpoint
                Verification and Windows management. A device with several users shows the first, with the rest on hover. Laptop
                comes from the portal asset with the same serial number, or from an unambiguous model name; hover the type to see
                which.
              </Typography>
            </CardContent>
          </Card>
        </>
      )}
    </Box>
  );
}

export default GoogleWorkspaceDevices;
