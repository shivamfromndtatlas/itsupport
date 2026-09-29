import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Autocomplete,
  Avatar,
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
  IconButton,
  Link,
  MenuItem,
  Paper,
  Stack,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Tabs,
  TextField,
  Tooltip,
  Typography,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import ClearIcon from '@mui/icons-material/Clear';
import CloseIcon from '@mui/icons-material/Close';
import DownloadIcon from '@mui/icons-material/Download';
import GoogleIcon from '@mui/icons-material/Google';
import InsightsIcon from '@mui/icons-material/Insights';
import RefreshIcon from '@mui/icons-material/Refresh';
import SettingsIcon from '@mui/icons-material/Settings';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import { DataGrid } from '@mui/x-data-grid';
import { useNavigate } from 'react-router-dom';
import api from '../../api/axios';
import GoogleWorkspaceConnections from './GoogleWorkspaceConnections';
import {
  StatCard,
  adminLabel,
  formatDateTime,
  gridSx,
  initialsOf,
  statusOf,
  userDashboardPath,
} from './shared';

const DIRECTORY_URL = '/integrations/google-workspace/directory/';

const roleColor = (role) => {
  if (role === 'OWNER') return 'primary';
  if (role === 'MANAGER') return 'info';
  return 'default';
};

const titleCase = (value) => (value ? value.charAt(0) + value.slice(1).toLowerCase() : '');

const csvCell = (value) => {
  const text = String(value ?? '');
  return /[",\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
};

const exportCsv = (users) => {
  const header = [
    'Full name', 'Primary email', 'Aliases', 'Domain', 'Org unit', 'Title', 'Department', 'Employee ID',
    'Manager', 'Status', 'Admin', '2-Step enrolled', 'Created', 'Last sign-in', 'Groups',
  ];
  const rows = users.map((user) => [
    user.full_name, user.primary_email, user.aliases.join('; '), user.domain, user.org_unit, user.title,
    user.department, user.employee_id, user.manager, statusOf(user).label, adminLabel(user),
    user.is_enrolled_in_2sv ? 'Yes' : 'No', user.created_at, user.last_login_at || 'Never',
    user.groups.map((group) => group.email).join('; '),
  ]);
  const csv = [header, ...rows].map((row) => row.map(csvCell).join(',')).join('\r\n');
  const url = URL.createObjectURL(new Blob([`﻿${csv}`], { type: 'text/csv;charset=utf-8' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = 'google-workspace-users.csv';
  link.click();
  URL.revokeObjectURL(url);
};

function DetailField({ label, children }) {
  // Lists (aliases, phones) arrive as arrays, and an empty array is truthy.
  const hasContent = React.Children.toArray(children).some((child) => child !== '');
  return (
    <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 1, height: '100%' }}>
      <Typography variant="caption" color="text.secondary" fontWeight={700}>
        {label}
      </Typography>
      <Typography variant="body2" fontWeight={700} component="div" sx={{ mt: 0.5, wordBreak: 'break-word' }}>
        {hasContent ? children : '—'}
      </Typography>
    </Paper>
  );
}

function UserDialog({ user, onClose, onOpenDashboard }) {
  const theme = useTheme();
  const fullScreen = useMediaQuery(theme.breakpoints.down('sm'));
  const status = user ? statusOf(user) : null;

  return (
    <Dialog open={Boolean(user)} onClose={onClose} maxWidth="md" fullWidth fullScreen={fullScreen}>
      {user && (
        <>
          <DialogTitle>
            <Stack direction="row" alignItems="center" spacing={1.5}>
              <Avatar sx={{ bgcolor: 'primary.main' }}>{initialsOf(user)}</Avatar>
              <Box sx={{ minWidth: 0, flex: 1 }}>
                <Typography variant="h6" fontWeight={800} noWrap>
                  {user.full_name || user.primary_email}
                </Typography>
                <Typography variant="body2" color="text.secondary" noWrap>
                  {user.primary_email}
                </Typography>
              </Box>
              <Chip size="small" color={status.color} variant="outlined" label={status.label} />
              <Button size="small" variant="contained" startIcon={<InsightsIcon />} onClick={() => onOpenDashboard(user)} sx={{ display: { xs: 'none', sm: 'inline-flex' } }}>
                Activity
              </Button>
              <IconButton onClick={onClose} aria-label="Close">
                <CloseIcon />
              </IconButton>
            </Stack>
          </DialogTitle>
          <DialogContent dividers>
            <Box sx={{ display: 'grid', gap: 1.5, gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', md: 'repeat(3, 1fr)' }, mb: 3 }}>
              <DetailField label="First name">{user.given_name}</DetailField>
              <DetailField label="Last name">{user.family_name}</DetailField>
              <DetailField label="Domain">{user.domain}</DetailField>
              <DetailField label="Aliases">
                {user.aliases.map((alias) => (
                  <div key={alias}>{alias}</div>
                ))}
              </DetailField>
              <DetailField label="Org unit">{user.org_unit}</DetailField>
              <DetailField label="Job title">{user.title}</DetailField>
              <DetailField label="Department">{user.department}</DetailField>
              <DetailField label="Cost center">{user.cost_center}</DetailField>
              <DetailField label="Employee ID">{user.employee_id}</DetailField>
              <DetailField label="Manager">{user.manager}</DetailField>
              <DetailField label="Phones">
                {user.phones.map((phone) => (
                  <div key={`${phone.type}-${phone.value}`}>
                    {phone.value}
                    {phone.type ? ` (${phone.type})` : ''}
                  </div>
                ))}
              </DetailField>
              <DetailField label="Admin">{adminLabel(user)}</DetailField>
              <DetailField label="2-Step verification">
                {user.is_enrolled_in_2sv ? 'Enrolled' : 'Not enrolled'}
                {user.is_enforced_in_2sv ? ' · enforced' : ''}
              </DetailField>
              <DetailField label="Password change required">{user.change_password_at_next_login ? 'Yes' : 'No'}</DetailField>
              <DetailField label="Account created">{formatDateTime(user.created_at)}</DetailField>
              <DetailField label="Last sign-in">{user.last_login_at ? formatDateTime(user.last_login_at) : 'Never'}</DetailField>
              {user.suspended && <DetailField label="Suspension reason">{user.suspension_reason}</DetailField>}
            </Box>

            <Divider sx={{ mb: 2 }} />
            <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 1 }}>
              <Typography variant="subtitle1" fontWeight={800}>
                Google Groups
              </Typography>
              <Chip size="small" label={`${user.groups.length} group${user.groups.length === 1 ? '' : 's'}`} />
            </Stack>
            {user.groups.length ? (
              <Box sx={{ overflowX: 'auto' }}>
                <Table size="small" sx={{ minWidth: 420 }}>
                  <TableHead>
                    <TableRow>
                      <TableCell sx={{ fontWeight: 700 }}>Group</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Email</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Role</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {user.groups.map((group) => (
                      <TableRow key={group.id}>
                        <TableCell>{group.name}</TableCell>
                        <TableCell sx={{ wordBreak: 'break-all' }}>{group.email}</TableCell>
                        <TableCell>
                          <Chip size="small" variant="outlined" color={roleColor(group.role)} label={titleCase(group.role)} />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Box>
            ) : (
              <Typography variant="body2" color="text.secondary">
                Not a direct member of any group.
              </Typography>
            )}
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1.5 }}>
              Direct memberships only. Access a user gets through a group nested inside another group isn&apos;t listed.
            </Typography>
          </DialogContent>
        </>
      )}
    </Dialog>
  );
}

function GoogleWorkspace() {
  const navigate = useNavigate();
  // Passing the row along lets the dashboard show the profile without refetching the directory.
  const openDashboard = (user) => navigate(userDashboardPath(user.primary_email), { state: { user } });
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [connectionsOpen, setConnectionsOpen] = useState(false);
  const [domainTab, setDomainTab] = useState('all');
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [securityFilter, setSecurityFilter] = useState('all');
  const [groupFilter, setGroupFilter] = useState(null);
  const [selectedUser, setSelectedUser] = useState(null);

  const load = useCallback(async (refresh = false) => {
    setLoading(true);
    setError('');
    try {
      const res = await api.get(DIRECTORY_URL, { params: refresh ? { refresh: 1 } : {} });
      setData(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load the Google Workspace directory.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const domains = useMemo(() => data?.domains || [], [data]);
  const allUsers = useMemo(() => data?.users || [], [data]);
  const groups = useMemo(() => data?.groups || [], [data]);
  const failedDomains = domains.filter((domain) => !domain.ok);
  const unreadableGroups = domains.reduce((sum, domain) => sum + (domain.groups_unreadable || 0), 0);

  // If the selected domain disappears (removed in the connections dialog), go back to All.
  useEffect(() => {
    if (domainTab !== 'all' && !domains.some((domain) => domain.domain === domainTab)) setDomainTab('all');
  }, [domains, domainTab]);

  const domainUsers = useMemo(
    () => (domainTab === 'all' ? allUsers : allUsers.filter((user) => user.domain === domainTab)),
    [allUsers, domainTab]
  );

  const filteredUsers = useMemo(() => {
    const query = search.trim().toLowerCase();
    return domainUsers.filter((user) => {
      const status = statusOf(user).key;
      if (statusFilter !== 'all' && status !== statusFilter) return false;
      if (securityFilter === 'admins' && !(user.is_admin || user.is_delegated_admin)) return false;
      if (securityFilter === 'no2sv' && user.is_enrolled_in_2sv) return false;
      if (groupFilter && !user.groups.some((group) => group.email.toLowerCase() === groupFilter.email.toLowerCase())) return false;
      if (!query) return true;
      return [
        user.full_name, user.primary_email, ...user.aliases, user.title, user.department,
        user.employee_id, user.org_unit, ...user.groups.flatMap((group) => [group.name, group.email]),
      ].some((value) => value && String(value).toLowerCase().includes(query));
    });
  }, [domainUsers, search, statusFilter, securityFilter, groupFilter]);

  const stats = useMemo(() => ({
    total: domainUsers.length,
    active: domainUsers.filter((user) => statusOf(user).key === 'active').length,
    suspended: domainUsers.filter((user) => user.suspended).length,
    admins: domainUsers.filter((user) => user.is_admin || user.is_delegated_admin).length,
    no2sv: domainUsers.filter((user) => !user.is_enrolled_in_2sv && statusOf(user).key === 'active').length,
  }), [domainUsers]);

  const hasActiveFilters = search.trim() || statusFilter !== 'all' || securityFilter !== 'all' || groupFilter;
  const resetFilters = () => {
    setSearch('');
    setStatusFilter('all');
    setSecurityFilter('all');
    setGroupFilter(null);
  };

  const loadedAt = useMemo(
    () => domains.map((domain) => domain.fetched_at).filter(Boolean).sort()[0] || '',
    [domains]
  );

  const columns = [
    {
      field: 'full_name',
      headerName: 'Name',
      flex: 1.2,
      minWidth: 190,
      renderCell: ({ row }) => (
        <Stack direction="row" alignItems="center" spacing={1.25} sx={{ minWidth: 0 }}>
          <Avatar sx={{ width: 28, height: 28, fontSize: 12, bgcolor: 'primary.main' }}>{initialsOf(row)}</Avatar>
          <Typography variant="body2" fontWeight={700} noWrap>
            {row.full_name || '—'}
          </Typography>
        </Stack>
      ),
    },
    {
      field: 'primary_email',
      headerName: 'Email',
      flex: 1.5,
      minWidth: 250,
      renderCell: ({ row, value }) => (
        <Link
          component="button"
          type="button"
          underline="hover"
          onClick={(event) => {
            // The row itself opens the detail dialog; the email opens the activity dashboard.
            event.stopPropagation();
            openDashboard(row);
          }}
          sx={{ textAlign: 'left', fontSize: 13.5, fontWeight: 600 }}
        >
          {value}
        </Link>
      ),
    },
    { field: 'domain', headerName: 'Domain', flex: 0.9, minWidth: 130 },
    { field: 'department', headerName: 'Department', flex: 0.9, minWidth: 130 },
    {
      field: 'status',
      headerName: 'Status',
      flex: 0.7,
      minWidth: 110,
      valueGetter: (value, row) => statusOf(row).label,
      renderCell: ({ row }) => {
        const status = statusOf(row);
        return <Chip size="small" variant="outlined" color={status.color} label={status.label} />;
      },
    },
    {
      field: 'is_enrolled_in_2sv',
      headerName: '2-Step',
      flex: 0.6,
      minWidth: 100,
      renderCell: ({ value }) => (
        <Chip size="small" variant="outlined" color={value ? 'success' : 'warning'} label={value ? 'On' : 'Off'} />
      ),
    },
    {
      field: 'last_login_at',
      headerName: 'Last sign-in',
      flex: 0.9,
      minWidth: 150,
      valueGetter: (value) => (value ? formatDateTime(value) : 'Never'),
    },
    {
      field: 'groups',
      headerName: 'Groups',
      flex: 2,
      minWidth: 300,
      valueGetter: (value, row) => row.groups.length,
      renderCell: ({ row }) => {
        if (!row.groups.length) return <Typography variant="body2" color="text.secondary">None</Typography>;
        const shown = row.groups.slice(0, 2);
        const hidden = row.groups.slice(2);
        return (
          <Stack direction="row" spacing={0.5} alignItems="center" sx={{ minWidth: 0 }}>
            {shown.map((group) => (
              <Chip key={group.id} size="small" label={group.name} sx={{ maxWidth: 150 }} />
            ))}
            {hidden.length > 0 && (
              <Tooltip title={hidden.map((group) => group.name).join(', ')}>
                <Chip size="small" variant="outlined" label={`+${hidden.length}`} />
              </Tooltip>
            )}
          </Stack>
        );
      },
    },
  ];

  const noDomains = data && domains.length === 0;

  return (
    <Box>
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} alignItems={{ sm: 'center' }} justifyContent="space-between" sx={{ mb: 2 }}>
        <Box>
          <Typography variant="body2" color="text.secondary">
            Users and Google Groups memberships across your Workspace domains.
            {loadedAt && ` Loaded ${formatDateTime(loadedAt)}.`}
          </Typography>
        </Box>
        <Stack direction="row" spacing={1}>
          <Button variant="outlined" size="small" startIcon={<SettingsIcon />} onClick={() => setConnectionsOpen(true)}>
            Domains
          </Button>
          <Button
            variant="outlined"
            size="small"
            startIcon={<DownloadIcon />}
            onClick={() => exportCsv(filteredUsers)}
            disabled={!filteredUsers.length}
          >
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

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {failedDomains.map((domain) => (
        <Alert
          key={domain.domain}
          severity="warning"
          sx={{ mb: 2 }}
          action={
            <Button color="inherit" size="small" onClick={() => setConnectionsOpen(true)}>
              Fix
            </Button>
          }
        >
          <b>{domain.domain}</b> couldn&apos;t be loaded: {domain.error}
        </Alert>
      ))}

      {unreadableGroups > 0 && (
        <Alert severity="info" sx={{ mb: 2 }}>
          {unreadableGroups} group{unreadableGroups === 1 ? '' : 's'} couldn&apos;t be read, so some users may be missing a membership.
        </Alert>
      )}

      {loading && !data && (
        <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', py: 8, gap: 2 }}>
          <CircularProgress />
          <Typography variant="body2" color="text.secondary">
            Reading the directory from Google. Large directories can take a few seconds.
          </Typography>
        </Box>
      )}

      {noDomains && (
        <Card sx={{ borderRadius: 2, boxShadow: 2 }}>
          <CardContent sx={{ textAlign: 'center', py: 6 }}>
            <GoogleIcon color="primary" sx={{ fontSize: 40, mb: 1 }} />
            <Typography variant="h6" fontWeight={800}>
              Connect a Google Workspace domain
            </Typography>
            <Typography color="text.secondary" sx={{ mb: 2.5, maxWidth: 480, mx: 'auto' }}>
              Add each domain (for example ndtatlas.com and aeis.com) with a service account key to list its users and the
              groups they belong to.
            </Typography>
            <Button variant="contained" onClick={() => setConnectionsOpen(true)}>
              Add a domain
            </Button>
          </CardContent>
        </Card>
      )}

      {data && !noDomains && (
        <>
          <Tabs
            value={domainTab}
            onChange={(e, value) => setDomainTab(value)}
            variant="scrollable"
            scrollButtons="auto"
            sx={{ mb: 2, borderBottom: 1, borderColor: 'divider' }}
          >
            <Tab value="all" label={`All domains (${allUsers.length})`} />
            {domains.map((domain) => (
              <Tab
                key={domain.domain}
                value={domain.domain}
                icon={domain.ok ? undefined : <WarningAmberIcon fontSize="small" color="warning" />}
                iconPosition="end"
                label={`${domain.domain} (${domain.user_count})`}
              />
            ))}
          </Tabs>

          <Box sx={{ display: 'grid', gap: 1.5, gridTemplateColumns: { xs: 'repeat(2, 1fr)', md: 'repeat(5, 1fr)' }, mb: 2 }}>
            <StatCard label="Users" value={stats.total} />
            <StatCard label="Active" value={stats.active} color="success.main" />
            <StatCard label="Suspended" value={stats.suspended} color={stats.suspended ? 'error.main' : undefined} />
            <StatCard label="Admins" value={stats.admins} />
            <StatCard label="Active w/o 2-Step" value={stats.no2sv} color={stats.no2sv ? 'warning.main' : undefined} />
          </Box>

          <Card sx={{ borderRadius: 2, boxShadow: 2 }}>
            <CardContent sx={{ p: { xs: 2, md: 3 } }}>
              <Box sx={{ display: 'grid', gap: 1.5, gridTemplateColumns: { xs: '1fr', md: '1.4fr 1.2fr 0.8fr 0.9fr auto' }, alignItems: 'center', mb: 2 }}>
                <TextField
                  label="Search name, email, title, group…"
                  size="small"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
                <Autocomplete
                  size="small"
                  options={groups}
                  value={groupFilter}
                  onChange={(e, value) => setGroupFilter(value)}
                  getOptionLabel={(group) => `${group.name} (${group.email})`}
                  isOptionEqualToValue={(a, b) => a.email === b.email}
                  renderInput={(params) => <TextField {...params} label="Member of group" />}
                />
                <TextField select label="Status" size="small" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
                  <MenuItem value="all">All statuses</MenuItem>
                  <MenuItem value="active">Active</MenuItem>
                  <MenuItem value="suspended">Suspended</MenuItem>
                  <MenuItem value="archived">Archived</MenuItem>
                </TextField>
                <TextField select label="Security" size="small" value={securityFilter} onChange={(e) => setSecurityFilter(e.target.value)}>
                  <MenuItem value="all">Everyone</MenuItem>
                  <MenuItem value="admins">Admins</MenuItem>
                  <MenuItem value="no2sv">No 2-Step</MenuItem>
                </TextField>
                <Button variant="outlined" startIcon={<ClearIcon />} onClick={resetFilters} disabled={!hasActiveFilters}>
                  Clear
                </Button>
              </Box>

              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
                Showing {filteredUsers.length} of {domainUsers.length} users
              </Typography>

              <Box sx={{ overflowX: 'auto', WebkitOverflowScrolling: 'touch' }}>
                <DataGrid
                  rows={filteredUsers}
                  columns={columns}
                  getRowId={(row) => row.primary_email}
                  autoHeight
                  rowHeight={52}
                  onRowClick={({ row }) => setSelectedUser(row)}
                  pageSizeOptions={[25, 50, 100]}
                  initialState={{ pagination: { paginationModel: { pageSize: 25 } } }}
                  disableRowSelectionOnClick
                  sx={{ ...gridSx, minWidth: 900 }}
                />
              </Box>
            </CardContent>
          </Card>
        </>
      )}

      <UserDialog user={selectedUser} onClose={() => setSelectedUser(null)} onOpenDashboard={openDashboard} />
      <GoogleWorkspaceConnections
        open={connectionsOpen}
        onClose={() => setConnectionsOpen(false)}
        onChanged={() => load(true)}
      />
    </Box>
  );
}

export default GoogleWorkspace;
