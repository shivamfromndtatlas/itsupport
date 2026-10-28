import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  MenuItem,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import RocketLaunchIcon from '@mui/icons-material/RocketLaunch';
import RefreshIcon from '@mui/icons-material/Refresh';
import { DataGrid } from '@mui/x-data-grid';
import api from '../../api/axios';

const JOB_PLATFORMS = [
  ['windows', 'Windows'],
  ['android', 'Android'],
  ['macos', 'macOS'],
  ['linux', 'Linux'],
  ['ios', 'iOS'],
  ['any', 'Any OS'],
];

const EMPTY_SELECTION = { type: 'include', ids: new Set() };

const STATUS_COLORS = {
  DEPLOYED: 'success',
  PENDING: 'warning',
  SCHEDULED: 'info',
  NOT_QUEUED: 'default',
  UNKNOWN: 'default',
};

const STATUS_LABELS = {
  DEPLOYED: 'Deployed',
  PENDING: 'Pending',
  SCHEDULED: 'Scheduled',
  NOT_QUEUED: 'Not queued',
  UNKNOWN: 'Unknown',
};

const gridSx = {
  border: 'none',
  minWidth: 500,
  fontSize: 13.5,
  '& .MuiDataGrid-columnHeaders': { backgroundColor: '#F8FAFC', borderBottom: '1px solid #E2E8F0' },
  '& .MuiDataGrid-columnHeaderTitle': { fontWeight: 700, fontSize: 12, color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.05em' },
  '& .MuiDataGrid-cell': { borderBottom: '1px solid #F1F5F9', '&:focus': { outline: 'none' }, '&:focus-within': { outline: 'none' } },
  '& .MuiDataGrid-footerContainer': { borderTop: '1px solid #E2E8F0', backgroundColor: '#F8FAFC' },
};

const errorText = (err, fallback) => err.response?.data?.detail || fallback;

function selectedIdsFrom(model, rows) {
  // DataGrid can report "everything except these" after a header select-all.
  if (model.type === 'exclude') {
    return rows.map((row) => row.id).filter((id) => !model.ids.has(id));
  }
  return Array.from(model.ids);
}

function SureMDMDeployPanel({ devices }) {
  const [platform, setPlatform] = useState('windows');
  const [jobs, setJobs] = useState([]);
  const [jobsLoading, setJobsLoading] = useState(false);
  const [jobId, setJobId] = useState('');
  const [category, setCategory] = useState('all');
  const [search, setSearch] = useState('');
  const [selection, setSelection] = useState(EMPTY_SELECTION);
  const [deploying, setDeploying] = useState(false);
  const [message, setMessage] = useState(null);
  const [statusByDevice, setStatusByDevice] = useState({});
  const [statusLoading, setStatusLoading] = useState(false);

  const loadJobs = useCallback(async () => {
    setJobsLoading(true);
    setJobId('');
    try {
      const res = await api.get(`/integrations/suremdm/jobs/?platform=${platform}`);
      setJobs(res.data?.results || []);
    } catch (err) {
      setJobs([]);
      setMessage({ severity: 'error', text: errorText(err, 'Failed to load SureMDM jobs.') });
    } finally {
      setJobsLoading(false);
    }
  }, [platform]);

  useEffect(() => {
    loadJobs();
  }, [loadJobs]);

  const categories = useMemo(
    () => Array.from(new Set(devices.map((device) => device.category).filter(Boolean))).sort(),
    [devices]
  );

  const filteredDevices = useMemo(() => {
    const query = search.trim().toLowerCase();
    return devices.filter((device) => {
      if (category !== 'all' && device.category !== category) return false;
      if (!query) return true;
      return [device.name, device.serial_number, device.system_tag, device.model]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(query));
    });
  }, [devices, category, search]);

  const selectedIds = useMemo(
    () => selectedIdsFrom(selection, filteredDevices),
    [selection, filteredDevices]
  );
  const selectedJob = jobs.find((job) => job.job_id === jobId);

  const loadStatus = useCallback(async (deviceIds, forJobId) => {
    if (!deviceIds.length || !forJobId) return;
    setStatusLoading(true);
    try {
      const params = new URLSearchParams({ device_ids: deviceIds.join(','), job_id: forJobId });
      const res = await api.get(`/integrations/suremdm/job-status/?${params.toString()}`);
      const next = {};
      (res.data?.results || []).forEach((row) => {
        next[row.suremdm_device_id] = row;
      });
      setStatusByDevice((current) => ({ ...current, ...next }));
    } catch (err) {
      setMessage({ severity: 'error', text: errorText(err, 'Failed to load deployment status.') });
    } finally {
      setStatusLoading(false);
    }
  }, []);

  // Status is per job, so clear it whenever a different job is picked.
  useEffect(() => {
    setStatusByDevice({});
  }, [jobId]);

  const handleDeploy = async () => {
    if (!selectedJob || !selectedIds.length) return;
    const confirmed = window.confirm(
      `Deploy "${selectedJob.name}" to ${selectedIds.length} device(s)? `
      + 'SureMDM will start installing it on each device.'
    );
    if (!confirmed) return;

    setDeploying(true);
    setMessage(null);
    try {
      const res = await api.post('/integrations/suremdm/deploy/', {
        job_id: selectedJob.job_id,
        device_ids: selectedIds,
      });
      setMessage({ severity: 'success', text: res.data?.message || 'Job queued.' });
      await loadStatus(selectedIds.slice(0, 50), selectedJob.job_id);
    } catch (err) {
      setMessage({ severity: 'error', text: errorText(err, 'Failed to deploy the job.') });
    } finally {
      setDeploying(false);
    }
  };

  const columns = [
    { field: 'name', headerName: 'Device', flex: 1, minWidth: 180 },
    { field: 'category', headerName: 'Category', width: 150 },
    { field: 'platform', headerName: 'Platform', width: 130 },
    { field: 'serial_number', headerName: 'Serial', width: 150 },
    {
      field: 'deploy_status',
      headerName: 'Deployment',
      width: 150,
      sortable: false,
      renderCell: ({ row }) => {
        const entry = statusByDevice[row.suremdm_device_id];
        if (!entry) return <Typography variant="body2" color="text.secondary">—</Typography>;
        const label = STATUS_LABELS[entry.status] || entry.status;
        return (
          <Tooltip title={entry.error || entry.comments || ''}>
            <Chip size="small" label={label} color={STATUS_COLORS[entry.status] || 'default'} />
          </Tooltip>
        );
      },
    },
  ];

  return (
    <Card sx={{ borderRadius: 2, boxShadow: 2 }}>
      <CardContent sx={{ p: 3 }}>
        <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1 }}>
          <RocketLaunchIcon color="primary" />
          <Typography variant="h6" fontWeight={700}>
            Deploy Software
          </Typography>
        </Stack>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Push a job built in the SureMDM console (for example a Trellix or TeamViewer install) to managed
          devices. Only devices already running the SureMDM agent can receive jobs.
        </Typography>

        {message && (
          <Alert severity={message.severity} onClose={() => setMessage(null)} sx={{ mb: 2 }}>
            {message.text}
          </Alert>
        )}

        <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} sx={{ mb: 2 }}>
          <TextField
            select
            label="Job platform"
            size="small"
            value={platform}
            onChange={(e) => setPlatform(e.target.value)}
            sx={{ minWidth: 160 }}
          >
            {JOB_PLATFORMS.map(([value, label]) => (
              <MenuItem key={value} value={value}>{label}</MenuItem>
            ))}
          </TextField>
          <TextField
            select
            label={jobsLoading ? 'Loading jobs…' : 'Job to deploy'}
            size="small"
            fullWidth
            value={jobId}
            onChange={(e) => setJobId(e.target.value)}
            disabled={jobsLoading || !jobs.length}
            helperText={!jobsLoading && !jobs.length ? 'No jobs for this platform. Create one in the SureMDM console under Jobs.' : ' '}
          >
            {jobs.map((job) => (
              <MenuItem key={job.job_id} value={job.job_id}>
                {job.name}{job.type ? ` — ${job.type}` : ''}
              </MenuItem>
            ))}
          </TextField>
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={loadJobs}
            disabled={jobsLoading}
            sx={{ alignSelf: 'flex-start', whiteSpace: 'nowrap' }}
          >
            Reload jobs
          </Button>
        </Stack>

        <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} sx={{ mb: 2 }}>
          <TextField
            select
            label="Category"
            size="small"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            sx={{ minWidth: 200 }}
          >
            <MenuItem value="all">All categories</MenuItem>
            {categories.map((name) => (
              <MenuItem key={name} value={name}>{name}</MenuItem>
            ))}
          </TextField>
          <TextField
            label="Search devices"
            size="small"
            fullWidth
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </Stack>

        <Box sx={{ overflowX: 'auto', WebkitOverflowScrolling: 'touch' }}>
          <DataGrid
            rows={filteredDevices}
            columns={columns}
            autoHeight
            checkboxSelection
            disableRowSelectionOnClick
            rowSelectionModel={selection}
            onRowSelectionModelChange={setSelection}
            pageSizeOptions={[10, 25, 50]}
            initialState={{ pagination: { paginationModel: { pageSize: 10 } } }}
            sx={gridSx}
          />
        </Box>

        <Stack
          direction={{ xs: 'column', sm: 'row' }}
          spacing={2}
          alignItems={{ xs: 'stretch', sm: 'center' }}
          justifyContent="space-between"
          sx={{ mt: 2 }}
        >
          <Typography variant="body2" color="text.secondary">
            {selectedIds.length} device(s) selected
          </Typography>
          <Stack direction="row" spacing={1}>
            <Button
              variant="outlined"
              onClick={() => loadStatus(selectedIds.slice(0, 50), jobId)}
              disabled={!jobId || !selectedIds.length || statusLoading}
              startIcon={statusLoading ? <CircularProgress size={16} /> : <RefreshIcon />}
            >
              Check status
            </Button>
            <Button
              variant="contained"
              onClick={handleDeploy}
              disabled={!selectedJob || !selectedIds.length || deploying}
              startIcon={deploying ? <CircularProgress size={16} color="inherit" /> : <RocketLaunchIcon />}
            >
              Deploy to {selectedIds.length || ''} device{selectedIds.length === 1 ? '' : 's'}
            </Button>
          </Stack>
        </Stack>
      </CardContent>
    </Card>
  );
}

export default SureMDMDeployPanel;
