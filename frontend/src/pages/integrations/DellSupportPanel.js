import React, { useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  Divider,
  Link,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import KeyIcon from '@mui/icons-material/Key';
import SaveIcon from '@mui/icons-material/Save';
import WifiTetheringIcon from '@mui/icons-material/WifiTethering';
import api from '../../api/axios';

const EMPTY_FORM = {
  base_url: 'https://apigtwb2c.us.dell.com',
  client_id: '',
  client_secret: '',
  is_active: true,
};

const formatDateTime = (value) => {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  const pad = (n) => String(n).padStart(2, '0');
  return `${pad(date.getDate())}-${pad(date.getMonth() + 1)}-${date.getFullYear()} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
};

function DellSupportPanel() {
  const [form, setForm] = useState(EMPTY_FORM);
  const [connection, setConnection] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [message, setMessage] = useState(null);

  const showMessage = (severity, text) => setMessage({ severity, text });

  const loadConnection = async () => {
    setLoading(true);
    try {
      const res = await api.get('/integrations/dell-support/connection/');
      if (res.data?.configured) {
        setConnection(res.data);
        setForm({
          base_url: res.data.base_url || EMPTY_FORM.base_url,
          client_id: res.data.client_id || '',
          client_secret: '',
          is_active: res.data.is_active ?? true,
        });
      }
    } catch (err) {
      showMessage('error', 'Failed to load the Dell TechDirect connection.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadConnection();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      const res = await api.post('/integrations/dell-support/connection/', form);
      setConnection(res.data);
      setForm((prev) => ({ ...prev, client_secret: '' }));
      showMessage('success', 'Dell TechDirect connection saved.');
    } catch (err) {
      showMessage('error', err.response?.data?.detail || 'Failed to save the Dell TechDirect connection.');
    } finally {
      setSaving(false);
    }
  };

  const hasUnsavedSecret = Boolean(form.client_secret);

  const handleTest = async () => {
    setTesting(true);
    try {
      const res = await api.post('/integrations/dell-support/test/');
      await loadConnection();
      showMessage('success', res.data?.message || 'Authenticated with Dell successfully.');
    } catch (err) {
      await loadConnection();
      showMessage('error', err.response?.data?.message || err.response?.data?.detail || 'Dell authentication failed.');
    } finally {
      setTesting(false);
    }
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
      {message && (
        <Alert severity={message.severity} onClose={() => setMessage(null)} sx={{ mb: 2 }}>
          {message.text}
        </Alert>
      )}

      <Card sx={{ borderRadius: 2, boxShadow: 2, maxWidth: 640 }}>
        <CardContent sx={{ p: 3 }}>
          <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1 }}>
            <KeyIcon color="primary" />
            <Typography variant="h6" fontWeight={700}>
              Dell Warranty (TechDirect API)
            </Typography>
          </Stack>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Powers the warranty plan and original configuration shown on a Dell laptop's or monitor's
            asset dashboard. Dell blocks unauthenticated access to its support pages, so this needs an
            OAuth2 client from{' '}
            <Link href="https://techdirect.dell.com" target="_blank" rel="noopener noreferrer">
              techdirect.dell.com
            </Link>{' '}
            → APIs (request the Warranty / Asset Entitlement API).
          </Typography>

          <Stack spacing={2}>
            <TextField
              label="Dell API Gateway URL"
              value={form.base_url}
              onChange={(e) => setForm({ ...form, base_url: e.target.value })}
              helperText="US accounts: apigtwb2c.us.dell.com · EU accounts: apigtwb2c.eu.dell.com"
              fullWidth
            />
            <TextField
              label="Client ID"
              value={form.client_id}
              onChange={(e) => setForm({ ...form, client_id: e.target.value })}
              fullWidth
            />
            <TextField
              label={connection?.has_client_secret ? 'Client Secret (saved)' : 'Client Secret'}
              type="password"
              value={form.client_secret}
              onChange={(e) => setForm({ ...form, client_secret: e.target.value })}
              helperText={
                connection?.has_client_secret
                  ? 'Leave blank to keep the saved secret, or type a new one and save.'
                  : ''
              }
              fullWidth
            />

            {connection?.last_test_status && (
              <Alert severity={connection.last_test_status === 'success' ? 'success' : 'warning'}>
                {connection.last_test_message}
                {connection.last_tested_at ? ` (${formatDateTime(connection.last_tested_at)})` : ''}
              </Alert>
            )}

            <Divider />
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
              <Button variant="contained" startIcon={<SaveIcon />} onClick={handleSave} disabled={saving}>
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
            {hasUnsavedSecret && (
              <Typography variant="caption" color="text.secondary">
                Save the updated client secret before testing.
              </Typography>
            )}
          </Stack>
        </CardContent>
      </Card>
    </Box>
  );
}

export default DellSupportPanel;
