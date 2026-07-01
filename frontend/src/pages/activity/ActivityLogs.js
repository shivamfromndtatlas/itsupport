import React, { useCallback, useEffect, useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  Chip,
  Snackbar,
  Alert,
  TextField,
  MenuItem,
} from '@mui/material';
import DataTable from '../../components/common/DataTable';
import api from '../../api/axios';

function ActivityLogs() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [users, setUsers] = useState([]);
  const [selectedUserId, setSelectedUserId] = useState('');
  const [selectedAction, setSelectedAction] = useState('');
  const [snack, setSnack] = useState({ open: false, msg: '', severity: 'success' });

  const showSnack = (msg, severity = 'success') => setSnack({ open: true, msg, severity });

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (selectedUserId) params.set('user_id', selectedUserId);
      if (selectedAction) params.set('action', selectedAction);
      const res = await api.get(`/activity-log/activity-logs/${params.toString() ? `?${params.toString()}` : ''}`);
      setRows(Array.isArray(res.data) ? res.data : res.data.results || []);
    } catch {
      showSnack('Failed to load activity logs.', 'error');
    } finally {
      setLoading(false);
    }
  }, [selectedAction, selectedUserId]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  useEffect(() => {
    (async () => {
      try {
        const res = await api.get('/users/');
        setUsers(Array.isArray(res.data) ? res.data : res.data.results || []);
      } catch {
        showSnack('Failed to load users.', 'error');
      }
    })();
  }, []);

  const columns = [
    { field: 'created_at', headerName: 'Time', width: 190 },
    { field: 'user_name', headerName: 'User', width: 180 },
    {
      field: 'user_role',
      headerName: 'Role',
      width: 120,
      renderCell: ({ value }) => <Chip size="small" label={String(value || '').replace('_', ' ')} variant="outlined" />,
    },
    { field: 'action', headerName: 'Action', flex: 1, minWidth: 220 },
    { field: 'method', headerName: 'Method', width: 95 },
    { field: 'path', headerName: 'Path', flex: 1.2, minWidth: 260 },
    {
      field: 'status_code',
      headerName: 'Status',
      width: 100,
      renderCell: ({ value }) => (
        <Chip
          size="small"
          label={value}
          color={value >= 400 ? 'error' : 'success'}
          variant="outlined"
        />
      ),
    },
  ];

  return (
    <Box>
      <Typography variant="h6" fontWeight={600} sx={{ mb: 2 }}>
        Activity Log
      </Typography>
      <Paper sx={{ borderRadius: 2, p: 2 }}>
        <Box sx={{ display: 'flex', gap: 2, mb: 2, flexWrap: 'wrap' }}>
          <TextField
            select
            size="small"
            label="User"
            value={selectedUserId}
            onChange={(e) => setSelectedUserId(e.target.value)}
            sx={{ minWidth: 240 }}
          >
            <MenuItem value="">All users</MenuItem>
            {users.map((user) => (
              <MenuItem key={user.id} value={String(user.id)}>
                {user.full_name} ({user.email})
              </MenuItem>
            ))}
          </TextField>
          <TextField
            size="small"
            label="Action contains"
            value={selectedAction}
            onChange={(e) => setSelectedAction(e.target.value)}
            sx={{ minWidth: 240 }}
          />
        </Box>
        <DataTable
          rows={rows}
          columns={columns}
          loading={loading}
          onRefresh={fetchLogs}
          refreshLabel="Refresh"
          searchable
        />
      </Paper>
      <Snackbar open={snack.open} autoHideDuration={4000} onClose={() => setSnack({ ...snack, open: false })}>
        <Alert severity={snack.severity} onClose={() => setSnack({ ...snack, open: false })}>
          {snack.msg}
        </Alert>
      </Snackbar>
    </Box>
  );
}

export default ActivityLogs;
