import React, { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import {
  Alert,
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
  MenuItem,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableRow,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import ClearIcon from '@mui/icons-material/Clear';
import RefreshIcon from '@mui/icons-material/Refresh';
import { DataGrid } from '@mui/x-data-grid';
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip as ChartTooltip, XAxis, YAxis } from 'recharts';
import api from '../../api/axios';
import UserDevicesPanel from './UserDevicesPanel';
import { StatCard, adminLabel, formatDateTime, gridSx, initialsOf, statusOf, useUserPhotos } from './shared';

const BASE = '/integrations/google-workspace';
const RANGES = [7, 30, 90];

const DIRECTION = {
  sent: { label: 'Sent', color: 'primary' },
  received: { label: 'Received', color: 'default' },
  forwarded: { label: 'Forwarded', color: 'info' },
  auto_forwarded: { label: 'Auto-forwarded', color: 'info' },
};

const ACTIVITY_FILTERS = [
  ['all', 'All'],
  ['download', 'Downloads'],
  ['share', 'Sharing'],
  ['external', 'Shared externally'],
  ['signin', 'Sign-ins'],
];

// Each panel loads from its own endpoint, so one report being unavailable (edition,
// missing scope) shows an error in that panel only.
function useReport(path, email, days, nonce) {
  const [state, setState] = useState({ data: null, loading: true, error: '' });

  useEffect(() => {
    let cancelled = false;
    setState({ data: null, loading: true, error: '' });
    api
      .get(`${BASE}/${path}/`, { params: { email, days, ...(nonce ? { refresh: 1 } : {}) } })
      .then((res) => !cancelled && setState({ data: res.data, loading: false, error: '' }))
      .catch((err) => {
        if (cancelled) return;
        setState({ data: null, loading: false, error: err.response?.data?.detail || 'Failed to load this report.' });
      });
    return () => {
      cancelled = true;
    };
  }, [path, email, days, nonce]);

  return state;
}

const describeDriveEvent = (event) => {
  if (event.category === 'download') return 'Downloaded';
  if (event.action === 'removed') return event.event === 'change_user_access' ? 'Removed access' : 'Link sharing turned off';
  if (event.event === 'change_user_access') return event.access_change ? `Shared (${event.access_change.replace(/^ → /, '')})` : 'Changed access';
  if (event.event === 'change_document_visibility') {
    return `Link sharing: ${event.old_visibility || '?'} → ${event.visibility || '?'}`;
  }
  return 'Changed access scope';
};

const scopeChip = (scope) => {
  if (scope === 'external') return <Chip size="small" color="warning" label="External" />;
  if (scope === 'internal') return <Chip size="small" variant="outlined" label="Internal" />;
  return <Typography variant="body2" color="text.secondary">—</Typography>;
};

function Panel({ title, children, action }) {
  return (
    <Card sx={{ borderRadius: 2, boxShadow: 2, mb: 2.5 }}>
      <CardContent sx={{ p: { xs: 2, md: 3 } }}>
        <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 1.5 }}>
          <Typography variant="h6" fontWeight={800}>
            {title}
          </Typography>
          {action}
        </Stack>
        {children}
      </CardContent>
    </Card>
  );
}

function Loading({ label }) {
  return (
    <Stack direction="row" spacing={1.5} alignItems="center" sx={{ py: 3 }}>
      <CircularProgress size={20} />
      <Typography variant="body2" color="text.secondary">
        {label}
      </Typography>
    </Stack>
  );
}

const formatFieldValue = (value) => (Array.isArray(value) ? value.join(', ') : String(value));

const formatBytes = (bytes) => {
  if (bytes === null || bytes === undefined) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

// Everything Google returned for one message, so the columns can always be checked
// against the source and any field the table doesn't show is still reachable.
function MailDialog({ mail, onClose }) {
  const entries = Object.entries(mail?.fields || {}).sort(([a], [b]) => a.localeCompare(b));
  return (
    <Dialog open={Boolean(mail)} onClose={onClose} maxWidth="md" fullWidth>
      {mail && (
        <>
          <DialogTitle sx={{ fontWeight: 800, wordBreak: 'break-word' }}>{mail.subject || '(no subject)'}</DialogTitle>
          <DialogContent dividers>
            <Table size="small" sx={{ mb: 3 }}>
              <TableBody>
                {[
                  ['Time', formatDateTime(mail.time)],
                  ['Direction', DIRECTION[mail.direction]?.label || mail.direction],
                  ['From', mail.sender || '—'],
                  ['To', mail.recipients?.length ? mail.recipients.join(', ') : '—'],
                  ['Attachments', mail.attachments ?? '—'],
                  ['Size', formatBytes(mail.size)],
                  ['Outside recipients', mail.external_recipients?.length ? mail.external_recipients.join(', ') : 'None'],
                  ['Flag', mail.external_with_attachments ? 'Attachments sent to outside recipients' : '—'],
                ].map(([label, value]) => (
                  <TableRow key={label}>
                    <TableCell sx={{ fontWeight: 700, width: 120 }}>{label}</TableCell>
                    <TableCell sx={{ wordBreak: 'break-word' }}>{value}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <Typography variant="subtitle2" fontWeight={800} sx={{ mb: 1 }}>
              All fields Google returned ({entries.length})
            </Typography>
            {entries.length ? (
              <Table size="small">
                <TableBody>
                  {entries.map(([key, value]) => (
                    <TableRow key={key}>
                      <TableCell sx={{ fontFamily: 'monospace', fontSize: 12, width: '38%', verticalAlign: 'top', wordBreak: 'break-all' }}>
                        {key}
                      </TableCell>
                      <TableCell sx={{ wordBreak: 'break-word' }}>{formatFieldValue(value)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <Typography variant="body2" color="text.secondary">
                Google returned no fields for this event.
              </Typography>
            )}
          </DialogContent>
        </>
      )}
    </Dialog>
  );
}

function GoogleWorkspaceUser() {
  const { email } = useParams();
  const location = useLocation();
  const navigate = useNavigate();

  const [days, setDays] = useState(30);
  const [nonce, setNonce] = useState(0);
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [selectedMail, setSelectedMail] = useState(null);
  const [flaggedOnly, setFlaggedOnly] = useState(false);
  const [fetched, setFetched] = useState({ email: '', user: null });

  // The list page hands over the row it already has; a direct visit or reload looks it up.
  const stateUser = location.state?.user?.primary_email?.toLowerCase() === email.toLowerCase() ? location.state.user : null;
  useEffect(() => {
    if (stateUser) return undefined;
    let cancelled = false;
    api
      .get(`${BASE}/directory/`)
      .then((res) => {
        const found = (res.data?.users || []).find((user) => user.primary_email.toLowerCase() === email.toLowerCase());
        if (!cancelled) setFetched({ email, user: found || null });
      })
      .catch(() => !cancelled && setFetched({ email, user: null }));
    return () => {
      cancelled = true;
    };
  }, [email, stateUser]);
  const profile = stateUser || (fetched.email === email ? fetched.user : null);
  const profileLoading = !stateUser && fetched.email !== email;
  const profileList = useMemo(() => (profile ? [profile] : []), [profile]);
  const photoOf = useUserPhotos(profileList);

  // Not period-based, so the fixed 30 keeps it from refetching when the Period picker changes.
  const devices = useReport('user-devices', email, 30, nonce);
  const drive = useReport('user-drive', email, days, nonce);
  const signins = useReport('user-signins', email, days, nonce);
  const usage = useReport('user-email-usage', email, days, nonce);
  const mail = useReport('user-email-events', email, days, nonce);

  const stat = (report, pick) => (report.loading ? '…' : report.error ? '—' : pick(report.data));

  // A missing delegation scope fails several reports with the same message: show each
  // repeated message once at the top, and keep one-off errors in their own panel.
  const errors = [drive.error, signins.error, usage.error, mail.error].filter(Boolean);
  const sharedErrors = [...new Set(errors)].filter((message) => errors.filter((e) => e === message).length > 1);
  const isShared = (message) => sharedErrors.includes(message);

  const activityRows = useMemo(() => {
    const driveRows = (drive.data?.events || []).map((event, index) => ({
      id: `drive-${index}`,
      time: event.time,
      kind: event.category === 'download' ? 'Download' : 'Share',
      filterKey: event.category,
      activity: describeDriveEvent(event),
      item: event.title || '(untitled)',
      docType: event.doc_type,
      owner: event.owner,
      target: event.target_user || event.target_domain || '',
      scope: event.scope,
      external: event.category === 'share' && event.scope === 'external' && event.action !== 'removed',
      ip: event.ip,
    }));
    const signinRows = (signins.data?.events || []).map((event, index) => ({
      id: `signin-${index}`,
      time: event.time,
      kind: 'Sign-in',
      filterKey: 'signin',
      activity: event.label,
      item: event.login_type ? event.login_type.replace(/_/g, ' ') : '',
      docType: '',
      owner: '',
      target: '',
      scope: '',
      risk: event.risk,
      ip: event.ip,
    }));
    return [...driveRows, ...signinRows].sort((a, b) => new Date(b.time) - new Date(a.time));
  }, [drive.data, signins.data]);

  const visibleRows = useMemo(() => {
    const query = search.trim().toLowerCase();
    return activityRows.filter((row) => {
      if (filter === 'external' ? !row.external : filter !== 'all' && row.filterKey !== filter) return false;
      if (!query) return true;
      return [row.activity, row.item, row.target, row.owner, row.ip, row.kind].some((value) => value && String(value).toLowerCase().includes(query));
    });
  }, [activityRows, filter, search]);

  const activityColumns = [
    {
      field: 'time',
      headerName: 'Time',
      type: 'dateTime',
      width: 150,
      valueGetter: (value) => (value ? new Date(value) : null),
      renderCell: ({ row }) => formatDateTime(row.time),
    },
    {
      field: 'kind',
      headerName: 'Type',
      width: 110,
      renderCell: ({ row }) => (
        <Chip
          size="small"
          variant="outlined"
          color={row.kind === 'Download' ? 'primary' : row.kind === 'Share' ? 'secondary' : row.risk ? 'error' : 'default'}
          label={row.kind}
        />
      ),
    },
    { field: 'activity', headerName: 'Activity', flex: 1.2, minWidth: 190 },
    {
      field: 'item',
      headerName: 'Item / detail',
      flex: 1.5,
      minWidth: 220,
      renderCell: ({ row }) => (
        <Tooltip title={row.owner ? `Owner: ${row.owner}` : row.item}>
          <Typography variant="body2" noWrap>
            {row.item}
            {row.docType ? ` · ${row.docType}` : ''}
          </Typography>
        </Tooltip>
      ),
    },
    { field: 'target', headerName: 'Shared with', flex: 1, minWidth: 180 },
    { field: 'scope', headerName: 'Scope', width: 110, renderCell: ({ row }) => scopeChip(row.scope) },
    { field: 'ip', headerName: 'IP address', width: 140 },
  ];

  const mailColumns = [
    {
      field: 'time',
      headerName: 'Time',
      width: 150,
      valueGetter: (value) => (value ? new Date(value) : null),
      renderCell: ({ row }) => formatDateTime(row.time),
    },
    {
      field: 'direction',
      headerName: 'Direction',
      width: 130,
      renderCell: ({ value }) => (
        <Chip size="small" variant="outlined" color={DIRECTION[value]?.color || 'default'} label={DIRECTION[value]?.label || value} />
      ),
    },
    { field: 'subject', headerName: 'Subject', flex: 1.5, minWidth: 200, valueGetter: (value) => value || '—' },
    { field: 'sender', headerName: 'From', flex: 1, minWidth: 180, valueGetter: (value) => value || '—' },
    { field: 'recipients', headerName: 'To', flex: 1, minWidth: 180, valueGetter: (value) => (value?.length ? value.join(', ') : '—') },
    {
      field: 'attachments',
      headerName: 'Attachments',
      type: 'number',
      width: 130,
      headerAlign: 'left',
      align: 'left',
      // Bold when a message carried files, so those stand out when scanning.
      renderCell: ({ value }) => (
        <Typography variant="body2" fontWeight={value > 0 ? 800 : 400} color={value > 0 ? 'text.primary' : 'text.secondary'}>
          {value ?? '—'}
        </Typography>
      ),
    },
    {
      field: 'size',
      headerName: 'Size',
      type: 'number',
      width: 110,
      headerAlign: 'left',
      align: 'left',
      valueFormatter: (value) => formatBytes(value),
    },
    {
      field: 'external_with_attachments',
      headerName: 'Outside',
      width: 160,
      // Sorts flagged first, then messages to outside recipients without files.
      valueGetter: (value, row) => (row.external_with_attachments ? 2 : row.external_recipients?.length ? 1 : 0),
      renderCell: ({ row }) => {
        if (!row.external_recipients?.length) return <Typography variant="body2" color="text.secondary">—</Typography>;
        return (
          <Tooltip title={`Outside recipients: ${row.external_recipients.join(', ')}`}>
            {row.external_with_attachments ? (
              <Chip size="small" color="warning" label="Files to outside" />
            ) : (
              <Chip size="small" variant="outlined" label="External" />
            )}
          </Tooltip>
        );
      },
    },
  ];

  const mailEvents = useMemo(() => (mail.data?.events || []).map((event, index) => ({ id: index, ...event })), [mail.data]);
  const mailHasDetails = mailEvents.some((event) => event.subject || event.sender || event.recipients.length);
  const shownMailEvents = flaggedOnly ? mailEvents.filter((event) => event.external_with_attachments) : mailEvents;
  const mailHasSenders = mailEvents.some((event) => event.sender);
  const mailHasRecipients = mailEvents.some((event) => event.recipients.length);
  const mailHasAddresses = mailHasSenders || mailHasRecipients;
  // Google's Gmail log gives the sender only on some accounts; an always-empty column is just noise.
  const visibleMailColumns = mailColumns.filter((column) => column.field !== 'sender' || mailHasSenders);
  const chartData = (usage.data?.daily || []).map((day) => ({ ...day, label: day.date.slice(5) }));
  const status = profile ? statusOf(profile) : null;

  return (
    <Box>
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} alignItems={{ sm: 'center' }} justifyContent="space-between" sx={{ mb: 2 }}>
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/google-workspace')} sx={{ alignSelf: 'flex-start' }}>
          All users
        </Button>
        <Stack direction="row" spacing={1}>
          <TextField select size="small" label="Period" value={days} onChange={(e) => setDays(Number(e.target.value))} sx={{ minWidth: 140 }}>
            {RANGES.map((range) => (
              <MenuItem key={range} value={range}>
                Last {range} days
              </MenuItem>
            ))}
          </TextField>
          <Button variant="contained" size="small" startIcon={<RefreshIcon />} onClick={() => setNonce((n) => n + 1)}>
            Refresh
          </Button>
        </Stack>
      </Stack>

      <Card sx={{ borderRadius: 2, boxShadow: 2, mb: 2.5 }}>
        <CardContent sx={{ p: { xs: 2, md: 3 } }}>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} alignItems={{ sm: 'center' }}>
            <Avatar src={photoOf(email)} alt={profile?.full_name} sx={{ width: 56, height: 56, bgcolor: 'primary.main', fontSize: 20 }}>
              {initialsOf(profile || { primary_email: email })}
            </Avatar>
            <Box sx={{ minWidth: 0, flex: 1 }}>
              <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                <Typography variant="h5" fontWeight={800}>
                  {profile?.full_name || email}
                </Typography>
                {status && <Chip size="small" variant="outlined" color={status.color} label={status.label} />}
                {profile && (profile.is_admin || profile.is_delegated_admin) && <Chip size="small" color="primary" label={adminLabel(profile)} />}
                {profile && !profile.is_enrolled_in_2sv && <Chip size="small" color="warning" variant="outlined" label="No 2-Step" />}
              </Stack>
              <Typography color="text.secondary" sx={{ wordBreak: 'break-all' }}>
                {email}
              </Typography>
              {profile && (
                <Typography variant="body2" color="text.secondary">
                  {[profile.title, profile.department, profile.org_unit].filter(Boolean).join(' · ') || 'No title or department set'}
                  {' · Last sign-in '}
                  {profile.last_login_at ? formatDateTime(profile.last_login_at) : 'never'}
                </Typography>
              )}
              {profileLoading && <Typography variant="body2" color="text.secondary">Loading profile…</Typography>}
              {!profileLoading && !profile && (
                <Typography variant="body2" color="text.secondary">
                  This user isn&apos;t in the loaded directory, but their activity can still be shown.
                </Typography>
              )}
            </Box>
          </Stack>
          {profile?.groups?.length > 0 && (
            <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap sx={{ mt: 2 }}>
              <Typography variant="caption" color="text.secondary" fontWeight={700} sx={{ alignSelf: 'center', mr: 0.5 }}>
                GROUPS
              </Typography>
              {profile.groups.map((group) => (
                <Tooltip key={group.id} title={`${group.email} · ${group.role.toLowerCase()}`}>
                  <Chip size="small" label={group.name} />
                </Tooltip>
              ))}
            </Stack>
          )}
        </CardContent>
      </Card>

      {sharedErrors.map((message) => (
        <Alert key={message} severity="warning" sx={{ mb: 2.5 }}>
          {message}
        </Alert>
      ))}

      <Box sx={{ display: 'grid', gap: 1.5, gridTemplateColumns: { xs: 'repeat(2, 1fr)', md: 'repeat(3, 1fr)', lg: 'repeat(6, 1fr)' }, mb: 2.5 }}>
        <StatCard label="Emails sent" value={stat(usage, (d) => d.totals.sent)} hint={usage.data?.data_through ? `through ${usage.data.data_through}` : undefined} />
        <StatCard label="Emails received" value={stat(usage, (d) => d.totals.received)} hint={usage.data?.data_through ? `through ${usage.data.data_through}` : undefined} />
        <StatCard label="Downloads" value={stat(drive, (d) => d.summary.downloads)} hint={drive.data?.truncated ? 'most recent only' : undefined} />
        <StatCard
          label="Shared externally"
          value={stat(drive, (d) => d.summary.shared_external)}
          color={drive.data?.summary.shared_external ? 'warning.main' : undefined}
        />
        <StatCard label="Shared internally" value={stat(drive, (d) => d.summary.shared_internal)} />
        <StatCard
          label="Sign-in problems"
          value={stat(signins, (d) => d.summary.failures + d.summary.suspicious)}
          color={signins.data && signins.data.summary.failures + signins.data.summary.suspicious ? 'error.main' : undefined}
          hint={signins.data ? `${signins.data.summary.signins} successful` : undefined}
        />
      </Box>

      <Panel title="Devices">
        <UserDevicesPanel report={devices} />
      </Panel>

      <Panel title="Email">
        {usage.loading && <Loading label="Reading daily email counts from Google…" />}
        {usage.error && !isShared(usage.error) && <Alert severity="warning" sx={{ mb: 2 }}>{usage.error}</Alert>}
        {usage.data && (
          <>
            {chartData.length ? (
              <Box sx={{ height: 240 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" vertical={false} />
                    <XAxis dataKey="label" tick={{ fontSize: 11, fill: '#94A3B8' }} axisLine={false} tickLine={false} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: '#94A3B8' }} axisLine={false} tickLine={false} />
                    <ChartTooltip cursor={{ fill: 'rgba(79,70,229,0.04)' }} />
                    <Legend />
                    <Bar dataKey="sent" name="Sent" fill="#4F46E5" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="received" name="Received" fill="#94A3B8" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </Box>
            ) : (
              <Typography variant="body2" color="text.secondary">
                Google returned no email counts for this period.
              </Typography>
            )}
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
              Daily totals only. Google publishes these with a delay of a few days, so the newest days are not included
              {usage.data.data_through ? ` (latest: ${usage.data.data_through}).` : '.'}
            </Typography>
          </>
        )}

        <Typography variant="subtitle1" fontWeight={800} sx={{ mt: 3, mb: 1 }}>
          Individual messages (last {mail.data?.days || Math.min(days, 30)} days)
        </Typography>
        {mail.loading && <Loading label="Reading the Gmail log…" />}
        {mail.error && !isShared(mail.error) && <Alert severity="warning">{mail.error}</Alert>}
        {mail.data && (
          <>
            <Stack direction="row" spacing={1} sx={{ mb: 1.5 }} flexWrap="wrap" useFlexGap>
              {Object.entries(DIRECTION).map(([key, { label, color }]) => (
                <Chip key={key} size="small" variant="outlined" color={color} label={`${label}: ${mail.data.counts[key] || 0}`} />
              ))}
              {/* Clicking narrows the table to just the flagged messages. */}
              <Chip
                size="small"
                color={mail.data.flagged ? 'warning' : 'default'}
                variant={flaggedOnly ? 'filled' : 'outlined'}
                clickable={mail.data.flagged > 0}
                onClick={mail.data.flagged > 0 ? () => setFlaggedOnly((value) => !value) : undefined}
                label={`Files to outside recipients: ${mail.data.flagged || 0}`}
              />
            </Stack>
            {mail.data.truncated && (
              <Alert severity="info" sx={{ mb: 1.5 }}>
                This user has more mail events than can be shown here. Only the most recent are listed.
              </Alert>
            )}
            {mailEvents.length === 0 && (
              <Alert severity="info">
                Google&apos;s Gmail log returned no sent or received events for this user. If they do use email, message-level
                logs are likely not included in your Workspace edition (Google documents them for Enterprise, Frontline and
                Education plans). The daily totals above still work.
              </Alert>
            )}
            {mailEvents.length > 0 && !mailHasDetails && (
              <Alert severity="info" sx={{ mb: 1.5 }}>
                Your Workspace edition reports that mail was sent or received, but not the subject, sender or recipients.
              </Alert>
            )}
            {mailHasDetails && !mailHasAddresses && (
              <Alert severity="info" sx={{ mb: 1.5 }}>
                Google returned subjects but no sender or recipient addresses under any field this page recognises. Click a
                message to see every field Google sent.
                {mail.data.field_names?.length > 0 && ` Fields seen: ${mail.data.field_names.join(', ')}.`}
              </Alert>
            )}
            {mailHasRecipients && !mailHasSenders && (
              <Alert severity="info" sx={{ mb: 1.5 }}>
                Google&apos;s Gmail log includes the recipient address but not the sender, so there is no From column. For
                received mail, To is the mailbox owner. Click a message to see everything Google returned.
              </Alert>
            )}
            {mailEvents.length > 0 && (
              <Box sx={{ overflowX: 'auto' }}>
                <DataGrid
                  rows={shownMailEvents}
                  columns={visibleMailColumns}
                  autoHeight
                  disableRowSelectionOnClick
                  onRowClick={({ row }) => setSelectedMail(row)}
                  getRowClassName={({ row }) => (row.external_with_attachments ? 'flagged-row' : '')}
                  pageSizeOptions={[10, 25, 50]}
                  initialState={{ pagination: { paginationModel: { pageSize: 10 } } }}
                  sx={{
                    ...gridSx,
                    minWidth: 1100,
                    '& .flagged-row': { backgroundColor: 'rgba(237, 108, 2, 0.08)' },
                    '& .flagged-row:hover': { backgroundColor: 'rgba(237, 108, 2, 0.14)' },
                  }}
                />
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
                  &quot;Files to outside&quot; marks a sent or forwarded message with at least one attachment and at least one
                  recipient outside your connected domains. It is based on the attachment count and recipient list in Google&apos;s
                  Gmail log; file names and contents are not available.
                </Typography>
              </Box>
            )}
          </>
        )}
      </Panel>

      <Panel title="File and sign-in activity">
        {drive.error && !isShared(drive.error) && <Alert severity="warning" sx={{ mb: 2 }}>Drive activity: {drive.error}</Alert>}
        {signins.error && !isShared(signins.error) && <Alert severity="warning" sx={{ mb: 2 }}>Sign-ins: {signins.error}</Alert>}
        {(drive.data?.truncated || signins.data?.truncated) && (
          <Alert severity="info" sx={{ mb: 2 }}>
            This user has more events in this period than can be listed, so only the most recent are shown. Pick a shorter period
            to see everything.
          </Alert>
        )}
        {(drive.loading || signins.loading) && <Loading label="Reading the audit logs from Google…" />}

        <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5} alignItems={{ md: 'center' }} sx={{ mb: 2 }}>
          <ToggleButtonGroup size="small" exclusive value={filter} onChange={(e, value) => value && setFilter(value)} sx={{ flexWrap: 'wrap' }}>
            {ACTIVITY_FILTERS.map(([value, label]) => (
              <ToggleButton key={value} value={value} sx={{ textTransform: 'none', px: 1.5 }}>
                {label}
              </ToggleButton>
            ))}
          </ToggleButtonGroup>
          <TextField size="small" label="Search activity" value={search} onChange={(e) => setSearch(e.target.value)} sx={{ flex: 1, maxWidth: { md: 320 } }} />
          <Button startIcon={<ClearIcon />} onClick={() => { setFilter('all'); setSearch(''); }} disabled={filter === 'all' && !search}>
            Clear
          </Button>
        </Stack>

        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
          Showing {visibleRows.length} of {activityRows.length} events
        </Typography>
        <Box sx={{ overflowX: 'auto' }}>
          <DataGrid
            rows={visibleRows}
            columns={activityColumns}
            autoHeight
            disableRowSelectionOnClick
            pageSizeOptions={[10, 25, 50, 100]}
            initialState={{
              pagination: { paginationModel: { pageSize: 25 } },
              sorting: { sortModel: [{ field: 'time', sort: 'desc' }] },
            }}
            sx={{ ...gridSx, minWidth: 900, '& .MuiDataGrid-row': { cursor: 'default' } }}
          />
        </Box>
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1.5 }}>
          Downloads and sharing come from Google&apos;s Drive log; only actions this user performed are listed. Sharing counts as
          &quot;external&quot; when Google marks it external, or the recipient is outside your connected domains. Google keeps this
          data for about 6 months.
        </Typography>
      </Panel>

      <Typography variant="caption" color="text.secondary">
        Opening this dashboard is recorded in the portal&apos;s Activity Log.
      </Typography>

      <MailDialog mail={selectedMail} onClose={() => setSelectedMail(null)} />
    </Box>
  );
}

export default GoogleWorkspaceUser;
