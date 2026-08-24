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
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  Grid,
  IconButton,
  LinearProgress,
  MenuItem,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import ClearIcon from '@mui/icons-material/Clear';
import KeyIcon from '@mui/icons-material/Key';
import SaveIcon from '@mui/icons-material/Save';
import WifiTetheringIcon from '@mui/icons-material/WifiTethering';
import MovieIcon from '@mui/icons-material/Movie';
import TollIcon from '@mui/icons-material/Toll';
import InsightsIcon from '@mui/icons-material/Insights';
import WorkspacePremiumIcon from '@mui/icons-material/WorkspacePremium';
import ReceiptLongIcon from '@mui/icons-material/ReceiptLong';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import PictureAsPdfIcon from '@mui/icons-material/PictureAsPdf';
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { DataGrid } from '@mui/x-data-grid';
import api from '../../api/axios';

const EMPTY_FORM = {
  name: '',
  base_url: 'https://api.synthesia.io/v2',
  api_key: '',
  is_active: true,
  plan_name: '',
  billing_period: 'annual',
  credit_allowance: '',
  billing_cycle_renews_on: '',
  credits_used_override: '',
};

const EMPTY_INVOICE_FORM = {
  payment_date: '',
  amount: '',
  currency: 'USD',
  invoice_number: '',
  file: null,
};

const CURRENCY_OPTIONS = ['USD', 'EUR', 'GBP', 'INR'];

const SUMMARY_FIELDS = [
  ['Title', 'title'],
  ['Status', 'status'],
  ['Visibility', 'visibility'],
  ['Duration', 'duration_display'],
  ['Credits Used', 'credits_used'],
  ['Created At', 'created_at'],
  ['Last Updated', 'last_updated_at'],
  ['Test Video', 'is_test'],
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

const DATE_FIELD_KEYS = new Set(['created_at', 'last_updated_at']);

const formatDateTime = (value) => {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  const pad = (n) => String(n).padStart(2, '0');
  return `${pad(date.getDate())}-${pad(date.getMonth() + 1)}-${date.getFullYear()} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
};

const formatDateOnly = (value) => {
  if (!value) return '—';
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (!match) return String(value);
  const [, year, month, day] = match;
  return `${day}-${month}-${year}`;
};

const MONTH_LABEL_FORMATTER = new Intl.DateTimeFormat('en-US', { month: 'short', year: 'numeric' });

const formatMonthLabel = (year, month) => MONTH_LABEL_FORMATTER.format(new Date(year, month, 1));

const formatMinutes = (seconds) => (Math.round((seconds / 60) * 10) / 10).toFixed(1);

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

const buildRawRows = (video) => {
  const normalized = Object.entries(video || {})
    .filter(([key]) => !['id', 'raw'].includes(key))
    .map(([key, value]) => ({ label: formatFieldLabel(key), value }));
  const raw = flattenObject(video?.raw || {}).map(({ label, value }) => ({
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

const statusColor = (statusValue) => {
  const value = String(statusValue || '').toLowerCase();
  if (value === 'complete' || value === 'approved') return 'success';
  if (value === 'error' || value === 'rejected') return 'error';
  if (value === 'in_progress') return 'warning';
  return 'default';
};

function SynthesiaPanel() {
  const theme = useTheme();
  const fullScreen = useMediaQuery(theme.breakpoints.down('sm'));
  const [form, setForm] = useState(EMPTY_FORM);
  const [connection, setConnection] = useState(null);
  const [videos, setVideos] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [message, setMessage] = useState(null);
  const [selectedStatus, setSelectedStatus] = useState('all');
  const [videoSearch, setVideoSearch] = useState('');
  const [selectedVideo, setSelectedVideo] = useState(null);
  const [usageYear, setUsageYear] = useState('all');
  const [usageMetric, setUsageMetric] = useState('credits');
  const [invoices, setInvoices] = useState([]);
  const [invoiceDialogOpen, setInvoiceDialogOpen] = useState(false);
  const [invoiceForm, setInvoiceForm] = useState(EMPTY_INVOICE_FORM);
  const [savingInvoice, setSavingInvoice] = useState(false);
  const [deleteInvoiceTarget, setDeleteInvoiceTarget] = useState(null);
  const [deletingInvoice, setDeletingInvoice] = useState(false);

  const showMessage = (severity, text) => setMessage({ severity, text });

  const loadConnection = async () => {
    setLoading(true);
    try {
      const res = await api.get('/integrations/synthesia/connection/');
      if (res.data?.configured) {
        setConnection(res.data);
        setForm({
          name: res.data.name || '',
          base_url: res.data.base_url || EMPTY_FORM.base_url,
          api_key: '',
          is_active: res.data.is_active ?? true,
          plan_name: res.data.plan_name || '',
          billing_period: res.data.billing_period || EMPTY_FORM.billing_period,
          credit_allowance: res.data.credit_allowance ?? '',
          billing_cycle_renews_on: res.data.billing_cycle_renews_on || '',
          credits_used_override: res.data.credits_used_override ?? '',
        });
      }
    } catch (err) {
      showMessage('error', 'Failed to load Synthesia connection.');
    } finally {
      setLoading(false);
    }
  };

  const loadVideos = async () => {
    try {
      const res = await api.get('/integrations/synthesia/videos/?limit=500');
      setVideos((res.data?.results || []).map((video, index) => ({
        id: video.video_id || index,
        ...video,
      })));
    } catch (err) {
      setVideos([]);
    }
  };

  const loadSummary = async () => {
    try {
      const res = await api.get('/integrations/synthesia/summary/?limit=500');
      setSummary(res.data || null);
    } catch (err) {
      setSummary(null);
    }
  };

  const loadInvoices = async () => {
    try {
      const res = await api.get('/integrations/synthesia-invoices/');
      setInvoices(res.data || []);
    } catch (err) {
      setInvoices([]);
    }
  };

  useEffect(() => {
    loadConnection();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (connection) {
      loadInvoices();
    }
    if (connection?.last_test_status === 'success') {
      loadVideos();
      loadSummary();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connection]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload = {
        ...form,
        credit_allowance: form.credit_allowance === '' ? null : Number(form.credit_allowance),
        billing_cycle_renews_on: form.billing_cycle_renews_on || null,
        credits_used_override: form.credits_used_override === '' ? null : Number(form.credits_used_override),
      };
      const res = await api.post('/integrations/synthesia/connection/', payload);
      setConnection(res.data);
      setForm({
        ...form,
        api_key: '',
        plan_name: res.data.plan_name || '',
        billing_period: res.data.billing_period || EMPTY_FORM.billing_period,
        credit_allowance: res.data.credit_allowance ?? '',
        billing_cycle_renews_on: res.data.billing_cycle_renews_on || '',
        credits_used_override: res.data.credits_used_override ?? '',
      });
      showMessage('success', 'Synthesia connection saved.');
    } catch (err) {
      showMessage('error', err.response?.data?.detail || 'Failed to save Synthesia connection.');
    } finally {
      setSaving(false);
    }
  };

  const handleOpenInvoiceDialog = () => {
    setInvoiceForm(EMPTY_INVOICE_FORM);
    setInvoiceDialogOpen(true);
  };

  const handleCloseInvoiceDialog = () => {
    setInvoiceDialogOpen(false);
  };

  const handleSaveInvoice = async () => {
    if (!invoiceForm.payment_date || !invoiceForm.amount || !invoiceForm.file) {
      showMessage('error', 'Payment date, amount, and the invoice PDF are all required.');
      return;
    }
    setSavingInvoice(true);
    try {
      const payload = new FormData();
      payload.append('payment_date', invoiceForm.payment_date);
      payload.append('amount', invoiceForm.amount);
      payload.append('currency', invoiceForm.currency || 'USD');
      if (invoiceForm.invoice_number) payload.append('invoice_number', invoiceForm.invoice_number);
      payload.append('invoice_file', invoiceForm.file);
      await api.post('/integrations/synthesia-invoices/', payload, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setInvoiceDialogOpen(false);
      setInvoiceForm(EMPTY_INVOICE_FORM);
      await loadInvoices();
      showMessage('success', 'Invoice logged.');
    } catch (err) {
      showMessage('error', err.response?.data?.invoice_file?.[0] || err.response?.data?.detail || 'Failed to save invoice.');
    } finally {
      setSavingInvoice(false);
    }
  };

  const handleConfirmDeleteInvoice = async () => {
    if (!deleteInvoiceTarget) return;
    setDeletingInvoice(true);
    try {
      await api.delete(`/integrations/synthesia-invoices/${deleteInvoiceTarget.id}/`);
      setInvoices((prev) => prev.filter((invoice) => invoice.id !== deleteInvoiceTarget.id));
      setDeleteInvoiceTarget(null);
    } catch (err) {
      showMessage('error', 'Failed to delete invoice.');
    } finally {
      setDeletingInvoice(false);
    }
  };

  const hasUnsavedSecret = Boolean(form.api_key);

  const handleTest = async () => {
    setTesting(true);
    try {
      const res = await api.post('/integrations/synthesia/test/');
      await loadConnection();
      showMessage('success', res.data?.message || 'Connected to Synthesia successfully.');
    } catch (err) {
      await loadConnection();
      showMessage('error', err.response?.data?.message || err.response?.data?.detail || 'Synthesia connection test failed.');
    } finally {
      setTesting(false);
    }
  };

  const handleRefresh = async () => {
    await loadConnection();
    await loadVideos();
    await loadSummary();
  };

  const columns = [
    {
      field: 'title',
      headerName: 'Title',
      flex: 1.2,
      minWidth: 200,
      renderCell: ({ row, value }) => (
        <Button
          variant="text"
          size="small"
          onClick={() => setSelectedVideo(row)}
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
            {value || 'Untitled video'}
          </Typography>
        </Button>
      ),
    },
    {
      field: 'status',
      headerName: 'Status',
      flex: 0.8,
      minWidth: 130,
      renderCell: ({ value }) => (
        <Chip size="small" label={value || 'Unknown'} color={statusColor(value)} variant="outlined" />
      ),
    },
    { field: 'duration_display', headerName: 'Duration', flex: 0.7, minWidth: 110 },
    { field: 'credits_used', headerName: 'Credits Used', flex: 0.7, minWidth: 120 },
    { field: 'visibility', headerName: 'Visibility', flex: 0.7, minWidth: 110 },
    {
      field: 'created_at',
      headerName: 'Created At',
      flex: 1,
      minWidth: 170,
      renderCell: ({ value }) => <Typography variant="body2">{formatDateTime(value)}</Typography>,
    },
    {
      field: 'last_updated_at',
      headerName: 'Edited At',
      flex: 1,
      minWidth: 170,
      renderCell: ({ value }) => <Typography variant="body2">{formatDateTime(value)}</Typography>,
    },
  ];

  const statusOptions = useMemo(
    () => Array.from(new Set(videos.map((video) => video.status).filter(Boolean))).sort(),
    [videos]
  );
  const filteredVideos = useMemo(() => {
    const query = videoSearch.trim().toLowerCase();
    return videos.filter((video) => {
      const matchesStatus = selectedStatus === 'all' || video.status === selectedStatus;
      const matchesSearch =
        !query ||
        [video.title, video.status, video.visibility]
          .filter(Boolean)
          .some((value) => String(value).toLowerCase().includes(query));

      return matchesStatus && matchesSearch;
    });
  }, [videos, selectedStatus, videoSearch]);

  const hasActiveFilters = selectedStatus !== 'all' || videoSearch.trim();
  const selectedVideoRows = useMemo(() => buildRawRows(selectedVideo), [selectedVideo]);
  const resetFilters = () => {
    setSelectedStatus('all');
    setVideoSearch('');
  };

  const monthlyUsage = useMemo(() => {
    const buckets = new Map();
    const now = new Date();

    const ensureBucket = (year, month) => {
      const key = `${year}-${String(month).padStart(2, '0')}`;
      if (!buckets.has(key)) {
        buckets.set(key, { key, year, month, credits: 0, editCredits: 0, videos: 0, durationSeconds: 0 });
      }
      return buckets.get(key);
    };
    ensureBucket(now.getFullYear(), now.getMonth());

    videos.forEach((video) => {
      const createdDate = video.created_at ? new Date(video.created_at) : null;
      const createdValid = createdDate && !Number.isNaN(createdDate.getTime());
      if (createdValid) {
        const bucket = ensureBucket(createdDate.getFullYear(), createdDate.getMonth());
        bucket.credits += video.credits_used || 0;
        bucket.videos += 1;
        bucket.durationSeconds += video.duration_seconds || 0;
      }

      // Editing/re-rendering an existing video consumes credits again
      // without changing its creation month, so it's attributed as a
      // separate "edit credits" figure in whichever month it was last
      // touched - a full-duration estimate, since the API doesn't say
      // whether an edit re-rendered the whole video or just a scene.
      const updatedDate = video.last_updated_at ? new Date(video.last_updated_at) : null;
      const updatedValid = updatedDate && !Number.isNaN(updatedDate.getTime());
      if (
        updatedValid &&
        createdValid &&
        (updatedDate.getFullYear() !== createdDate.getFullYear() || updatedDate.getMonth() !== createdDate.getMonth())
      ) {
        const bucket = ensureBucket(updatedDate.getFullYear(), updatedDate.getMonth());
        bucket.editCredits += video.credits_used || 0;
      }
    });

    return Array.from(buckets.values())
      .sort((a, b) => a.key.localeCompare(b.key))
      .map((bucket) => ({
        ...bucket,
        totalCredits: bucket.credits + bucket.editCredits,
        label: formatMonthLabel(bucket.year, bucket.month),
        durationMinutes: Number(formatMinutes(bucket.durationSeconds)),
      }));
  }, [videos]);

  const billingSince = monthlyUsage.length ? formatMonthLabel(monthlyUsage[0].year, monthlyUsage[0].month) : '—';

  const usageYearOptions = useMemo(
    () => Array.from(new Set(monthlyUsage.map((bucket) => bucket.year))).sort((a, b) => b - a),
    [monthlyUsage]
  );

  const monthlyUsageWithActual = useMemo(() => {
    const hasRealFigure = summary && summary.credits_used_this_cycle != null && !summary.credits_used_is_estimate;
    if (!hasRealFigure || !summary.billing_cycle_started_on) {
      return monthlyUsage;
    }
    const cycleStart = new Date(summary.billing_cycle_started_on);
    const cycleKey = `${cycleStart.getFullYear()}-${String(cycleStart.getMonth()).padStart(2, '0')}`;
    return monthlyUsage.map((bucket) =>
      bucket.key === cycleKey ? { ...bucket, actualCredits: summary.credits_used_this_cycle } : bucket
    );
  }, [monthlyUsage, summary]);

  const filteredMonthlyUsage = useMemo(
    () =>
      usageYear === 'all'
        ? monthlyUsageWithActual
        : monthlyUsageWithActual.filter((bucket) => String(bucket.year) === String(usageYear)),
    [monthlyUsageWithActual, usageYear]
  );

  const usageMetricConfig = {
    credits: { dataKey: 'totalCredits', name: 'Credits Used', color: '#6366F1', formatter: (value) => value },
    videos: { dataKey: 'videos', name: 'Videos Published', color: '#10B981', formatter: (value) => value },
    duration: { dataKey: 'durationMinutes', name: 'Duration (minutes)', color: '#F59E0B', formatter: (value) => `${value}m` },
  }[usageMetric];

  const invoiceTotals = useMemo(() => {
    const totals = new Map();
    invoices.forEach((invoice) => {
      const amount = Number(invoice.amount) || 0;
      totals.set(invoice.currency, (totals.get(invoice.currency) || 0) + amount);
    });
    return Array.from(totals.entries());
  }, [invoices]);

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
                  Synthesia
                </Typography>
              </Stack>

              <Stack spacing={2}>
                <TextField
                  label="Workspace Name"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  helperText="A label to identify this Synthesia workspace, e.g. ATLAS."
                  fullWidth
                />
                <TextField
                  label="Synthesia API URL"
                  value={form.base_url}
                  onChange={(e) => setForm({ ...form, base_url: e.target.value })}
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

                <Divider />
                <Stack direction="row" alignItems="center" spacing={1}>
                  <WorkspacePremiumIcon color="primary" fontSize="small" />
                  <Typography variant="subtitle2" fontWeight={700}>
                    Current Plan
                  </Typography>
                </Stack>
                <TextField
                  label="Plan Name"
                  value={form.plan_name}
                  onChange={(e) => setForm({ ...form, plan_name: e.target.value })}
                  helperText="Entered manually — Synthesia's API doesn't expose plan/subscription details."
                  fullWidth
                />
                <TextField
                  select
                  label="Billing Period"
                  value={form.billing_period}
                  onChange={(e) => setForm({ ...form, billing_period: e.target.value })}
                  fullWidth
                >
                  <MenuItem value="monthly">Monthly</MenuItem>
                  <MenuItem value="annual">Annual</MenuItem>
                </TextField>
                <TextField
                  label="Credit Allowance"
                  type="number"
                  value={form.credit_allowance}
                  onChange={(e) => setForm({ ...form, credit_allowance: e.target.value })}
                  helperText="Credits included per billing period, per synthesia.io/pricing for this plan."
                  fullWidth
                />
                <TextField
                  label="Renewal Date"
                  type="date"
                  value={form.billing_cycle_renews_on}
                  onChange={(e) => setForm({ ...form, billing_cycle_renews_on: e.target.value })}
                  InputLabelProps={{ shrink: true }}
                  fullWidth
                />
                <TextField
                  label="Credits Used (from Synthesia dashboard)"
                  type="number"
                  value={form.credits_used_override}
                  onChange={(e) => setForm({ ...form, credits_used_override: e.target.value })}
                  helperText={
                    connection?.credits_used_override_at
                      ? `As of ${formatDateTime(connection.credits_used_override_at)}. Real-time credit consumption requires Synthesia's Enterprise-only audit logs, so copy this from the "Usage" panel on your Synthesia dashboard.`
                      : 'Real-time credit consumption requires Synthesia\'s Enterprise-only audit logs. Copy this number from the "Usage" panel on your Synthesia dashboard.'
                  }
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
                </Stack>
              </Stack>
              {hasUnsavedSecret && (
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1.5 }}>
                  Save the updated API key before testing the connection.
                </Typography>
              )}
            </CardContent>
          </Card>

          {summary && (
            <Grid container spacing={2} sx={{ mt: 0.5 }}>
              <Grid item xs={6}>
                <Paper variant="outlined" sx={{ p: 2 }}>
                  <Stack direction="row" alignItems="center" spacing={1}>
                    <MovieIcon color="primary" fontSize="small" />
                    <Typography variant="caption" color="text.secondary">Videos Published</Typography>
                  </Stack>
                  <Typography variant="h5" fontWeight={800}>
                    {summary.published_videos} / {summary.total_videos}
                  </Typography>
                </Paper>
              </Grid>
              <Grid item xs={6}>
                <Paper variant="outlined" sx={{ p: 2 }}>
                  <Stack direction="row" alignItems="center" spacing={1}>
                    <TollIcon color="primary" fontSize="small" />
                    <Typography variant="caption" color="text.secondary">Total Credits Used</Typography>
                  </Stack>
                  <Typography variant="h5" fontWeight={800}>{summary.total_credits_used}</Typography>
                </Paper>
              </Grid>
              <Grid item xs={12}>
                <Paper variant="outlined" sx={{ p: 2 }}>
                  <Typography variant="caption" color="text.secondary">Total Video Duration</Typography>
                  <Typography variant="h6" fontWeight={800}>{summary.total_duration_display}</Typography>
                </Paper>
              </Grid>
              {summary.credit_allowance != null && (
                <Grid item xs={12}>
                  <Paper variant="outlined" sx={{ p: 2 }}>
                    <Stack direction="row" alignItems="center" spacing={1}>
                      <Typography variant="caption" color="text.secondary">
                        {summary.plan_name || 'Plan'} Credits
                      </Typography>
                      {summary.credits_used_this_cycle != null && (
                        <Chip
                          size="small"
                          label={summary.credits_used_is_estimate ? 'Estimated from videos' : 'From Synthesia dashboard'}
                          color={summary.credits_used_is_estimate ? 'warning' : 'success'}
                          variant="outlined"
                        />
                      )}
                    </Stack>
                    {summary.credits_used_this_cycle != null ? (
                      <>
                        <Stack direction="row" alignItems="baseline" justifyContent="space-between" sx={{ mt: 0.5 }}>
                          <Typography variant="h6" fontWeight={800}>
                            {summary.credits_remaining} remaining
                          </Typography>
                          <Typography variant="body2" color="text.secondary">
                            {summary.credits_used_this_cycle} / {summary.credit_allowance} used
                          </Typography>
                        </Stack>
                        <LinearProgress
                          variant="determinate"
                          value={Math.min(100, (summary.credits_used_this_cycle / summary.credit_allowance) * 100)}
                          color={summary.credits_remaining < 0 ? 'error' : 'primary'}
                          sx={{ mt: 1, height: 8, borderRadius: 4 }}
                        />
                        <Stack direction="row" justifyContent="space-between" sx={{ mt: 0.75 }}>
                          {summary.billing_cycle_started_on && summary.billing_cycle_renews_on && (
                            <Typography variant="caption" color="text.secondary">
                              Cycle: {formatDateOnly(summary.billing_cycle_started_on)} → {formatDateOnly(summary.billing_cycle_renews_on)}
                            </Typography>
                          )}
                          {summary.credits_used_override_at && (
                            <Typography variant="caption" color="text.secondary">
                              Updated {formatDateOnly(summary.credits_used_override_at)}
                            </Typography>
                          )}
                        </Stack>
                        {summary.videos_edited_this_cycle?.length > 0 && (
                          <Box sx={{ mt: 1.5, pt: 1.5, borderTop: '1px dashed', borderColor: 'divider' }}>
                            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                              {summary.videos_edited_this_cycle.length} existing video
                              {summary.videos_edited_this_cycle.length === 1 ? '' : 's'} edited since this cycle
                              started — re-renders can consume credits this estimate doesn't capture:
                            </Typography>
                            <Stack spacing={0.5}>
                              {summary.videos_edited_this_cycle.map((video) => (
                                <Stack
                                  key={video.video_id}
                                  direction="row"
                                  justifyContent="space-between"
                                  spacing={1}
                                >
                                  <Typography variant="caption" noWrap sx={{ maxWidth: '65%' }}>
                                    {video.title}
                                  </Typography>
                                  <Typography variant="caption" color="text.secondary">
                                    {formatDateTime(video.last_updated_at)}
                                  </Typography>
                                </Stack>
                              ))}
                            </Stack>
                          </Box>
                        )}
                      </>
                    ) : (
                      <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                        Enter "Credits Used" from your Synthesia dashboard to track usage against this plan.
                      </Typography>
                    )}
                  </Paper>
                </Grid>
              )}
            </Grid>
          )}
        </Grid>

        <Grid item xs={12} md={7}>
          <Card sx={{ borderRadius: 2, boxShadow: 2 }}>
            <CardContent sx={{ p: 3 }}>
              <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 2 }}>
                <Typography variant="h6" fontWeight={700}>
                  Synthesia Videos
                </Typography>
                <Button variant="outlined" size="small" startIcon={<RefreshIcon />} onClick={handleRefresh}>
                  Refresh
                </Button>
              </Stack>
              <Grid container spacing={2} alignItems="center" sx={{ mb: 2 }}>
                <Grid item xs={12} sm={5}>
                  <TextField
                    select
                    label="Status"
                    size="small"
                    fullWidth
                    value={selectedStatus}
                    onChange={(e) => setSelectedStatus(e.target.value)}
                  >
                    <MenuItem value="all">All statuses</MenuItem>
                    {statusOptions.map((statusValue) => (
                      <MenuItem key={statusValue} value={statusValue}>
                        {statusValue}
                      </MenuItem>
                    ))}
                  </TextField>
                </Grid>
                <Grid item xs={12} sm={7}>
                  <Stack direction="row" spacing={1}>
                    <TextField
                      label="Search videos"
                      size="small"
                      fullWidth
                      value={videoSearch}
                      onChange={(e) => setVideoSearch(e.target.value)}
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
                  rows={filteredVideos}
                  columns={columns}
                  autoHeight
                  disableVirtualization
                  onRowClick={({ row }) => setSelectedVideo(row)}
                  pageSizeOptions={[10, 25]}
                  initialState={{ pagination: { paginationModel: { pageSize: 10 } } }}
                  sx={{
                    border: 'none',
                    minWidth: 600,
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
              <Stack direction="row" alignItems="center" justifyContent="space-between" flexWrap="wrap" rowGap={1} sx={{ mb: 2 }}>
                <Stack direction="row" alignItems="center" spacing={1}>
                  <InsightsIcon color="primary" />
                  <Typography variant="h6" fontWeight={700}>
                    Monthly Usage
                  </Typography>
                </Stack>
                <Typography variant="body2" color="text.secondary">
                  Billing since {billingSince}
                </Typography>
              </Stack>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 2 }}>
                "Credits (Edits)" attributes a video's full duration-based credit estimate to the month it was last
                edited, since re-rendering an existing video consumes credits again without changing its creation
                date. This is an upper bound, not a certainty — the API doesn't say whether an edit re-rendered the
                whole video or just one scene, so a partial re-render would cost less than shown here. "Actual
                (Dashboard)" shows the real, manually-entered figure from Synthesia's Usage panel, but only appears
                for the month the current billing cycle started in — there's no API or logged history to attribute
                a real number to past months.
              </Typography>

              <Grid container spacing={2} alignItems="center" sx={{ mb: 2 }}>
                <Grid item xs={12} sm={4} md={3}>
                  <TextField
                    select
                    label="Year"
                    size="small"
                    fullWidth
                    value={usageYear}
                    onChange={(e) => setUsageYear(e.target.value)}
                  >
                    <MenuItem value="all">All years</MenuItem>
                    {usageYearOptions.map((year) => (
                      <MenuItem key={year} value={year}>
                        {year}
                      </MenuItem>
                    ))}
                  </TextField>
                </Grid>
                <Grid item xs={12} sm={4} md={3}>
                  <TextField
                    select
                    label="Metric"
                    size="small"
                    fullWidth
                    value={usageMetric}
                    onChange={(e) => setUsageMetric(e.target.value)}
                  >
                    <MenuItem value="credits">Credits Used</MenuItem>
                    <MenuItem value="videos">Videos Published</MenuItem>
                    <MenuItem value="duration">Duration (minutes)</MenuItem>
                  </TextField>
                </Grid>
              </Grid>

              {filteredMonthlyUsage.length === 0 ? (
                <Paper variant="outlined" sx={{ p: 3, bgcolor: 'grey.50', textAlign: 'center' }}>
                  <Typography variant="body2" color="text.secondary">
                    No usage data for the selected year yet.
                  </Typography>
                </Paper>
              ) : (
                <>
                  <Box sx={{ width: '100%', height: 320, overflowX: 'auto' }}>
                    <ResponsiveContainer width="100%" minWidth={480} height="100%">
                      <ComposedChart data={filteredMonthlyUsage} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                        <XAxis dataKey="label" tick={{ fontSize: 12 }} />
                        <YAxis tick={{ fontSize: 12 }} allowDecimals={usageMetric === 'duration'} />
                        <RechartsTooltip formatter={(value) => [usageMetricConfig.formatter(value), usageMetricConfig.name]} />
                        <Legend />
                        <Bar dataKey={usageMetricConfig.dataKey} name={usageMetricConfig.name} fill={usageMetricConfig.color} radius={[4, 4, 0, 0]} />
                        <Line type="monotone" dataKey={usageMetricConfig.dataKey} name={`${usageMetricConfig.name} trend`} stroke="#1E293B" strokeWidth={2} dot={false} />
                      </ComposedChart>
                    </ResponsiveContainer>
                  </Box>

                  <TableContainer sx={{ mt: 2 }}>
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell sx={{ fontWeight: 700 }}>Month</TableCell>
                          <TableCell sx={{ fontWeight: 700 }} align="right">Videos Published</TableCell>
                          <TableCell sx={{ fontWeight: 700 }} align="right">Credits (New Videos)</TableCell>
                          <TableCell sx={{ fontWeight: 700 }} align="right">Credits (Edits)</TableCell>
                          <TableCell sx={{ fontWeight: 700 }} align="right">Estimated Total</TableCell>
                          <TableCell sx={{ fontWeight: 700 }} align="right">Actual (Dashboard)</TableCell>
                          <TableCell sx={{ fontWeight: 700 }} align="right">Duration (minutes)</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {[...filteredMonthlyUsage].reverse().map((bucket) => (
                          <TableRow key={bucket.key} hover selected={bucket.actualCredits != null}>
                            <TableCell>{bucket.label}</TableCell>
                            <TableCell align="right">{bucket.videos}</TableCell>
                            <TableCell align="right">{bucket.credits}</TableCell>
                            <TableCell align="right">{bucket.editCredits || '—'}</TableCell>
                            <TableCell align="right">
                              <Typography component="span" fontWeight={bucket.editCredits ? 700 : 400}>
                                {bucket.totalCredits}
                              </Typography>
                            </TableCell>
                            <TableCell align="right">
                              {bucket.actualCredits != null ? (
                                <Chip
                                  size="small"
                                  color="success"
                                  variant="outlined"
                                  label={`${bucket.actualCredits} (cycle to date)`}
                                />
                              ) : (
                                '—'
                              )}
                            </TableCell>
                            <TableCell align="right">{bucket.durationMinutes}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </>
              )}
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12}>
          <Card sx={{ borderRadius: 2, boxShadow: 2 }}>
            <CardContent sx={{ p: 3 }}>
              <Stack direction="row" alignItems="center" justifyContent="space-between" flexWrap="wrap" rowGap={1} sx={{ mb: 2 }}>
                <Stack direction="row" alignItems="center" spacing={1}>
                  <ReceiptLongIcon color="primary" />
                  <Typography variant="h6" fontWeight={700}>
                    Invoice History
                  </Typography>
                </Stack>
                <Button variant="contained" size="small" startIcon={<AddIcon />} onClick={handleOpenInvoiceDialog}>
                  Add Invoice
                </Button>
              </Stack>

              {invoiceTotals.length > 0 && (
                <Stack direction="row" spacing={1} flexWrap="wrap" rowGap={1} sx={{ mb: 2 }}>
                  {invoiceTotals.map(([currency, total]) => (
                    <Chip key={currency} label={`Total Paid (${currency}): ${total.toFixed(2)}`} color="primary" variant="outlined" />
                  ))}
                </Stack>
              )}

              {invoices.length === 0 ? (
                <Paper variant="outlined" sx={{ p: 3, bgcolor: 'grey.50', textAlign: 'center' }}>
                  <Typography variant="body2" color="text.secondary">
                    No invoices logged yet. Add one after you pay a Synthesia invoice.
                  </Typography>
                </Paper>
              ) : (
                <TableContainer sx={{ overflowX: 'auto' }}>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell sx={{ fontWeight: 700 }}>Payment Date</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Invoice #</TableCell>
                        <TableCell sx={{ fontWeight: 700 }} align="right">Amount</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Attachment</TableCell>
                        <TableCell sx={{ fontWeight: 700 }} align="right">Actions</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {invoices.map((invoice) => (
                        <TableRow key={invoice.id} hover>
                          <TableCell>{formatDateOnly(invoice.payment_date)}</TableCell>
                          <TableCell>{invoice.invoice_number || '—'}</TableCell>
                          <TableCell align="right">{Number(invoice.amount).toFixed(2)} {invoice.currency}</TableCell>
                          <TableCell>
                            {invoice.invoice_file ? (
                              <Button
                                size="small"
                                startIcon={<PictureAsPdfIcon />}
                                component="a"
                                href={invoice.invoice_file}
                                target="_blank"
                                rel="noopener noreferrer"
                              >
                                Download
                              </Button>
                            ) : (
                              '—'
                            )}
                          </TableCell>
                          <TableCell align="right">
                            <IconButton size="small" color="error" onClick={() => setDeleteInvoiceTarget(invoice)}>
                              <DeleteIcon fontSize="small" />
                            </IconButton>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Dialog open={invoiceDialogOpen} onClose={handleCloseInvoiceDialog} maxWidth="xs" fullWidth>
        <DialogTitle>Log Synthesia Invoice</DialogTitle>
        <DialogContent dividers>
          <Stack spacing={2} sx={{ mt: 0.5 }}>
            <TextField
              label="Payment Date"
              type="date"
              value={invoiceForm.payment_date}
              onChange={(e) => setInvoiceForm({ ...invoiceForm, payment_date: e.target.value })}
              InputLabelProps={{ shrink: true }}
              fullWidth
              required
            />
            <TextField
              label="Amount"
              type="number"
              value={invoiceForm.amount}
              onChange={(e) => setInvoiceForm({ ...invoiceForm, amount: e.target.value })}
              fullWidth
              required
            />
            <TextField
              select
              label="Currency"
              value={invoiceForm.currency}
              onChange={(e) => setInvoiceForm({ ...invoiceForm, currency: e.target.value })}
              fullWidth
            >
              {CURRENCY_OPTIONS.map((code) => (
                <MenuItem key={code} value={code}>
                  {code}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              label="Invoice Number (optional)"
              value={invoiceForm.invoice_number}
              onChange={(e) => setInvoiceForm({ ...invoiceForm, invoice_number: e.target.value })}
              fullWidth
            />
            <Button variant="outlined" component="label" startIcon={<UploadFileIcon />}>
              {invoiceForm.file ? invoiceForm.file.name : 'Upload Invoice PDF'}
              <input
                type="file"
                accept="application/pdf"
                hidden
                onChange={(e) => setInvoiceForm({ ...invoiceForm, file: e.target.files?.[0] || null })}
              />
            </Button>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseInvoiceDialog}>Cancel</Button>
          <Button variant="contained" onClick={handleSaveInvoice} disabled={savingInvoice}>
            Save Invoice
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={Boolean(deleteInvoiceTarget)} onClose={() => setDeleteInvoiceTarget(null)} maxWidth="xs" fullWidth>
        <DialogTitle>Delete Invoice?</DialogTitle>
        <DialogContent dividers>
          <Typography variant="body2">
            This will permanently remove the invoice dated {formatDateOnly(deleteInvoiceTarget?.payment_date)} and its attached PDF.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteInvoiceTarget(null)}>Cancel</Button>
          <Button variant="contained" color="error" onClick={handleConfirmDeleteInvoice} disabled={deletingInvoice}>
            Delete
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={Boolean(selectedVideo)}
        onClose={() => setSelectedVideo(null)}
        maxWidth="lg"
        fullWidth
        fullScreen={fullScreen}
      >
        <DialogTitle>
          <Stack direction="row" alignItems="center" spacing={1.5}>
            <MovieIcon color="primary" />
            <Box sx={{ minWidth: 0 }}>
              <Typography variant="h6" fontWeight={800} noWrap>
                {selectedVideo?.title || 'Synthesia Video'}
              </Typography>
              <Typography variant="body2" color="text.secondary" noWrap>
                {selectedVideo?.status || 'Unknown status'} - {selectedVideo?.duration_display || 'Duration unavailable'}
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
                    {DATE_FIELD_KEYS.has(key) ? formatDateTime(selectedVideo?.[key]) : formatFieldValue(selectedVideo?.[key])}
                  </Typography>
                </Paper>
              </Grid>
            ))}
          </Grid>

          <Divider sx={{ mb: 2 }} />
          <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 1.5 }}>
            <Typography variant="subtitle1" fontWeight={800}>
              Full Synthesia Payload
            </Typography>
            <Chip size="small" label={`${selectedVideoRows.length} fields`} />
          </Stack>

          <Grid container spacing={1.25}>
            {selectedVideoRows.map(({ label, value }, index) => (
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

export default SynthesiaPanel;
