import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  Paper,
  Stack,
  TextField,
  Tooltip,
  Typography,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import DeleteOutlinedIcon from '@mui/icons-material/DeleteOutlined';
import EditIcon from '@mui/icons-material/Edit';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import WifiTetheringIcon from '@mui/icons-material/WifiTethering';
import api from '../../api/axios';
import ConfirmDialog from '../../components/common/ConfirmDialog';

const CONNECTIONS_URL = '/integrations/google-workspace-connections/';

export const REQUIRED_SCOPES = [
  'https://www.googleapis.com/auth/admin.directory.user.readonly',
  'https://www.googleapis.com/auth/admin.directory.group.readonly',
].join(',');

// Only the per-user activity dashboard needs these; the user list works without them.
export const ACTIVITY_SCOPES = [
  'https://www.googleapis.com/auth/admin.reports.audit.readonly',
  'https://www.googleapis.com/auth/admin.reports.usage.readonly',
].join(',');

// Only the per-user Devices section needs these.
export const DEVICE_SCOPES = [
  'https://www.googleapis.com/auth/admin.directory.device.mobile.readonly',
  'https://www.googleapis.com/auth/cloud-identity.devices.readonly',
].join(',');

const EMPTY_FORM = { domain: '', label: '', admin_email: '', service_account_json: '' };

const formatDateTime = (value) => {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  const pad = (n) => String(n).padStart(2, '0');
  return `${pad(date.getDate())}-${pad(date.getMonth() + 1)}-${date.getFullYear()} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
};

// DRF field errors come back as {field: ['msg']}; show the first one.
const errorText = (err, fallback) => {
  const data = err.response?.data;
  if (!data) return fallback;
  if (typeof data === 'string') return fallback;
  if (data.detail || data.message) return data.detail || data.message;
  const first = Object.entries(data)[0];
  if (!first) return fallback;
  const [field, messages] = first;
  const text = Array.isArray(messages) ? messages[0] : String(messages);
  return field === 'non_field_errors' ? text : `${field.replace(/_/g, ' ')}: ${text}`;
};

function CopyValue({ label, value }) {
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
    } catch (err) {
      // Clipboard can be blocked on plain-http origins; the value is still selectable.
    }
  };
  return (
    <Box sx={{ mb: 1.5 }}>
      <Typography variant="caption" color="text.secondary" fontWeight={700}>
        {label}
      </Typography>
      <Stack direction="row" alignItems="center" spacing={0.5}>
        <Typography variant="body2" sx={{ fontFamily: 'monospace', wordBreak: 'break-all', userSelect: 'all' }}>
          {value}
        </Typography>
        <Tooltip title="Copy">
          <IconButton size="small" onClick={copy} aria-label={`Copy ${label}`}>
            <ContentCopyIcon fontSize="inherit" />
          </IconButton>
        </Tooltip>
      </Stack>
    </Box>
  );
}

function SetupGuide() {
  return (
    <Accordion variant="outlined" disableGutters sx={{ mb: 2, '&:before': { display: 'none' }, borderRadius: 1 }}>
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        <Typography fontWeight={700}>How to connect a domain</Typography>
      </AccordionSummary>
      <AccordionDetails>
        <Typography variant="body2" component="div" sx={{ '& li': { mb: 0.75 } }}>
          Do this once for each Google Workspace account. If both domains are in the same account, one service
          account works for both; add the domain twice with the same key file.
          <ol style={{ paddingLeft: 20 }}>
            <li>
              In the <b>Google Cloud console</b>, create (or pick) a project and enable the <b>Admin SDK API</b>.
            </li>
            <li>
              Create a <b>service account</b> in that project, then add a <b>JSON key</b> to it and download the file.
            </li>
            <li>
              In the <b>Google Admin console</b> go to Security &rarr; Access and data control &rarr; API controls
              &rarr; <b>Manage domain-wide delegation</b> &rarr; Add new. Paste the service account&apos;s Client ID
              (shown here once a key is saved) and these scopes:
              <CopyValue label="OAuth scopes (read-only)" value={REQUIRED_SCOPES} />
            </li>
            <li>
              <b>Optional, for a user&apos;s activity dashboard</b> (downloads, sharing, sign-ins, email counts): edit that
              same delegation entry and add these two scopes after the ones above. The user list keeps working without them.
              <CopyValue label="Activity report scopes (read-only)" value={ACTIVITY_SCOPES} />
              The Admin SDK API you enabled already covers the reports. Drive and Gmail logs also depend on your Workspace edition.
            </li>
            <li>
              <b>Optional, for a user&apos;s Devices section</b> (make, model, serial number, laptop or mobile): add these two
              scopes to the same entry, and in the Google Cloud project also enable the <b>Cloud Identity API</b> (the
              computers and laptops list comes from it).
              <CopyValue label="Device scopes (read-only)" value={DEVICE_SCOPES} />
              Edit the existing entry and keep every scope already on it, because saving replaces the whole list.
            </li>
            <li>
              Add the domain below with a <b>super admin</b> email for the service account to act as, and upload the
              JSON key. Then press <b>Test</b>.
            </li>
          </ol>
          The portal only ever reads the directory. The key is stored on the server and is never sent back to the browser.
        </Typography>
      </AccordionDetails>
    </Accordion>
  );
}

function ConnectionForm({ initial, editing, onCancel, onSaved }) {
  const [form, setForm] = useState(initial);
  const [fileName, setFileName] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const fileInput = useRef(null);

  const handleFile = (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      setForm((prev) => ({ ...prev, service_account_json: String(reader.result || '') }));
      setFileName(file.name);
    };
    reader.readAsText(file);
    // Allow re-selecting the same file after an error.
    event.target.value = '';
  };

  const handleSave = async () => {
    setSaving(true);
    setError('');
    try {
      const payload = { ...form };
      // Blank means "keep the saved key" on edit; never send an empty key.
      if (!payload.service_account_json) delete payload.service_account_json;
      const res = editing
        ? await api.patch(`${CONNECTIONS_URL}${editing.id}/`, payload)
        : await api.post(CONNECTIONS_URL, payload);
      onSaved(res.data);
    } catch (err) {
      setError(errorText(err, 'Failed to save this domain.'));
    } finally {
      setSaving(false);
    }
  };

  const canSave = form.domain.trim() && form.admin_email.trim() && (editing || form.service_account_json);

  return (
    <Paper variant="outlined" sx={{ p: 2, mb: 2, borderRadius: 1 }}>
      <Typography variant="subtitle1" fontWeight={800} sx={{ mb: 1.5 }}>
        {editing ? `Edit ${editing.domain}` : 'Add a domain'}
      </Typography>
      <Stack spacing={2}>
        {error && <Alert severity="error">{error}</Alert>}
        <TextField
          label="Domain"
          placeholder="example.com"
          value={form.domain}
          onChange={(e) => setForm({ ...form, domain: e.target.value })}
          size="small"
          fullWidth
        />
        <TextField
          label="Label (optional)"
          value={form.label}
          onChange={(e) => setForm({ ...form, label: e.target.value })}
          size="small"
          fullWidth
        />
        <TextField
          label="Super admin email to act as"
          type="email"
          value={form.admin_email}
          onChange={(e) => setForm({ ...form, admin_email: e.target.value })}
          helperText="An active super admin in this Workspace account. The service account impersonates them read-only."
          size="small"
          fullWidth
        />
        <Box>
          <input ref={fileInput} type="file" accept=".json,application/json" hidden onChange={handleFile} />
          <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap" useFlexGap>
            <Button variant="outlined" startIcon={<UploadFileIcon />} onClick={() => fileInput.current?.click()}>
              {editing?.has_service_account_key ? 'Replace JSON key' : 'Upload JSON key'}
            </Button>
            <Typography variant="body2" color="text.secondary">
              {fileName || (editing?.has_service_account_key ? 'Key saved. Upload a file only to replace it.' : 'No file chosen')}
            </Typography>
          </Stack>
        </Box>
        <Stack direction="row" spacing={1} justifyContent="flex-end">
          <Button onClick={onCancel} disabled={saving}>
            Cancel
          </Button>
          <Button variant="contained" onClick={handleSave} disabled={saving || !canSave}>
            {saving ? 'Saving…' : 'Save'}
          </Button>
        </Stack>
      </Stack>
    </Paper>
  );
}

const statusChip = (connection) => {
  if (!connection.last_test_status) return <Chip size="small" label="Not tested" />;
  return connection.last_test_status === 'success' ? (
    <Chip size="small" color="success" variant="outlined" label="Connected" />
  ) : (
    <Chip size="small" color="error" variant="outlined" label="Failed" />
  );
};

function GoogleWorkspaceConnections({ open, onClose, onChanged }) {
  const theme = useTheme();
  const fullScreen = useMediaQuery(theme.breakpoints.down('sm'));
  const [connections, setConnections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState(null);
  const [formState, setFormState] = useState(null); // null | {editing: connection|null}
  const [testingId, setTestingId] = useState(null);
  const [pendingDelete, setPendingDelete] = useState(null);
  const changed = useRef(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get(CONNECTIONS_URL);
      setConnections(res.data || []);
    } catch (err) {
      setMessage({ severity: 'error', text: errorText(err, 'Failed to load Google Workspace connections.') });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) {
      changed.current = false;
      setMessage(null);
      setFormState(null);
      load();
    }
  }, [open, load]);

  const close = () => {
    onClose();
    // The directory only needs reloading if a domain was added, edited or removed.
    if (changed.current) onChanged();
  };

  const handleSaved = async () => {
    changed.current = true;
    setFormState(null);
    setMessage({ severity: 'success', text: 'Saved. Press Test to check the connection.' });
    await load();
  };

  const handleTest = async (connection) => {
    setTestingId(connection.id);
    try {
      const res = await api.post(`${CONNECTIONS_URL}${connection.id}/test/`);
      setMessage({ severity: 'success', text: res.data?.message || 'Connected.' });
    } catch (err) {
      setMessage({ severity: 'error', text: errorText(err, 'Connection test failed.') });
    } finally {
      // A failing test can flip a domain's state, so let the page reload its data too.
      changed.current = true;
      setTestingId(null);
      await load();
    }
  };

  const handleDelete = async () => {
    const target = pendingDelete;
    setPendingDelete(null);
    try {
      await api.delete(`${CONNECTIONS_URL}${target.id}/`);
      changed.current = true;
      setMessage({ severity: 'success', text: `Removed ${target.domain}.` });
      await load();
    } catch (err) {
      setMessage({ severity: 'error', text: errorText(err, 'Failed to remove this domain.') });
    }
  };

  return (
    <>
      <Dialog open={open} onClose={close} maxWidth="md" fullWidth fullScreen={fullScreen}>
        <DialogTitle sx={{ fontWeight: 800 }}>Google Workspace domains</DialogTitle>
        <DialogContent dividers>
          {message && (
            <Alert severity={message.severity} onClose={() => setMessage(null)} sx={{ mb: 2 }}>
              {message.text}
            </Alert>
          )}

          <SetupGuide />

          {formState && (
            <ConnectionForm
              key={formState.editing?.id || 'new'}
              editing={formState.editing}
              initial={
                formState.editing
                  ? {
                      domain: formState.editing.domain,
                      label: formState.editing.label || '',
                      admin_email: formState.editing.admin_email,
                      service_account_json: '',
                    }
                  : EMPTY_FORM
              }
              onCancel={() => setFormState(null)}
              onSaved={handleSaved}
            />
          )}

          {loading && !connections.length ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
              <CircularProgress size={28} />
            </Box>
          ) : (
            <Stack spacing={1.5}>
              {connections.map((connection) => (
                <Paper key={connection.id} variant="outlined" sx={{ p: 2, borderRadius: 1 }}>
                  <Stack direction="row" alignItems="flex-start" justifyContent="space-between" spacing={1}>
                    <Box sx={{ minWidth: 0 }}>
                      <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                        <Typography fontWeight={800}>{connection.domain}</Typography>
                        {statusChip(connection)}
                        {!connection.is_active && <Chip size="small" label="Disabled" />}
                      </Stack>
                      {connection.label && (
                        <Typography variant="body2" color="text.secondary">
                          {connection.label}
                        </Typography>
                      )}
                      <Typography variant="body2" sx={{ mt: 0.5 }}>
                        Acting as <b>{connection.admin_email}</b>
                      </Typography>
                      <Typography variant="caption" color="text.secondary" display="block">
                        Last tested {formatDateTime(connection.last_tested_at)} · Last loaded {formatDateTime(connection.last_synced_at)}
                      </Typography>
                    </Box>
                    <Stack direction="row" spacing={0.5} sx={{ flexShrink: 0 }}>
                      <Button
                        size="small"
                        variant="outlined"
                        startIcon={testingId === connection.id ? <CircularProgress size={14} /> : <WifiTetheringIcon />}
                        disabled={testingId === connection.id}
                        onClick={() => handleTest(connection)}
                      >
                        Test
                      </Button>
                      <Tooltip title="Edit">
                        <IconButton size="small" aria-label={`Edit ${connection.domain}`} onClick={() => setFormState({ editing: connection })}>
                          <EditIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Remove">
                        <IconButton size="small" color="error" aria-label={`Remove ${connection.domain}`} onClick={() => setPendingDelete(connection)}>
                          <DeleteOutlinedIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </Stack>
                  </Stack>

                  {connection.last_test_message && (
                    <Alert severity={connection.last_test_status === 'success' ? 'success' : 'warning'} sx={{ mt: 1.5 }}>
                      {connection.last_test_message}
                    </Alert>
                  )}

                  {connection.service_account_client_id ? (
                    <Box sx={{ mt: 1.5 }}>
                      <CopyValue label="Client ID to authorise in the Admin console" value={connection.service_account_client_id} />
                      <Typography variant="caption" color="text.secondary" sx={{ fontFamily: 'monospace' }}>
                        {connection.service_account_email}
                      </Typography>
                    </Box>
                  ) : (
                    connection.service_account_email && (
                      <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1.5 }}>
                        Service account {connection.service_account_email} (the key file has no client_id; find the numeric
                        Client ID on its Cloud console page).
                      </Typography>
                    )
                  )}
                </Paper>
              ))}
              {!connections.length && !formState && (
                <Typography color="text.secondary" sx={{ py: 2, textAlign: 'center' }}>
                  No domains connected yet.
                </Typography>
              )}
            </Stack>
          )}
        </DialogContent>
        <DialogActions sx={{ px: 3, py: 1.5, justifyContent: 'space-between' }}>
          <Button startIcon={<AddIcon />} onClick={() => setFormState({ editing: null })} disabled={Boolean(formState)}>
            Add domain
          </Button>
          <Button onClick={close}>Done</Button>
        </DialogActions>
      </Dialog>

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        title={`Remove ${pendingDelete?.domain}?`}
        message="This deletes the saved key and settings for this domain from the portal. Nothing changes in Google Workspace."
        confirmLabel="Remove"
        onConfirm={handleDelete}
        onCancel={() => setPendingDelete(null)}
      />
    </>
  );
}

export default GoogleWorkspaceConnections;
