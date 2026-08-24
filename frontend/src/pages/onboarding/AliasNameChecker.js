import React, { useEffect, useRef, useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  TextField,
  Button,
  Alert,
  Chip,
  Stack,
  CircularProgress,
} from '@mui/material';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import api from '../../api/axios';

const HELP_TEXT =
  'Give a full name to get alias suggestions, or type an alias name directly to check whether its ' +
  'client email is available. First name initial + full last name, e.g. "Amy Jones" -> ajones@aeis.com.';

function AliasNameChecker() {
  const [fullName, setFullName] = useState('');
  const [aliasName, setAliasName] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const [suggesting, setSuggesting] = useState(false);
  const [suggestError, setSuggestError] = useState('');
  const [checking, setChecking] = useState(false);
  const [result, setResult] = useState(null); // { ok: boolean, message: string }
  const debounceRef = useRef(null);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);

    if (!aliasName.trim()) {
      setResult(null);
      return undefined;
    }

    debounceRef.current = setTimeout(async () => {
      setChecking(true);
      try {
        const res = await api.post('/employees/validate-alias/', {
          full_name: fullName.trim(),
          alias_name: aliasName.trim(),
        });
        setResult({ ok: true, message: `Available - client email: ${res.data.client_email}` });
      } catch (err) {
        const detail =
          err.response?.data?.alias_name || err.response?.data?.detail || 'This alias name is not valid.';
        setResult({ ok: false, message: Array.isArray(detail) ? detail.join(' ') : detail });
      } finally {
        setChecking(false);
      }
    }, 400);

    return () => clearTimeout(debounceRef.current);
  }, [aliasName, fullName]);

  const handleGetSuggestions = async () => {
    if (!fullName.trim()) return;
    setSuggesting(true);
    setSuggestError('');
    try {
      const res = await api.get('/employees/alias-suggestions/', {
        params: { full_name: fullName.trim() },
      });
      setSuggestions(res.data.suggestions || []);
      if (!(res.data.suggestions || []).length) {
        setSuggestError('No available suggestions found for this name.');
      }
    } catch {
      setSuggestions([]);
      setSuggestError('Failed to load suggestions.');
    } finally {
      setSuggesting(false);
    }
  };

  const handlePickSuggestion = (suggestion) => {
    setAliasName(suggestion.alias_name);
  };

  return (
    <Box>
      <Typography variant="h6" fontWeight={600} sx={{ mb: 2 }}>
        Alias Name Checker
      </Typography>

      <Paper sx={{ borderRadius: 2, p: 3, maxWidth: 640 }}>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          {HELP_TEXT}
        </Typography>

        <Stack spacing={3}>
          <Box>
            <Stack direction="row" spacing={1} sx={{ alignItems: 'flex-start' }}>
              <TextField
                label="Full Name (optional)"
                fullWidth
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                helperText="Provide the employee's real name to get matching alias suggestions."
              />
              <Button
                variant="outlined"
                startIcon={suggesting ? <CircularProgress size={16} /> : <AutoAwesomeIcon />}
                onClick={handleGetSuggestions}
                disabled={!fullName.trim() || suggesting}
                sx={{ whiteSpace: 'nowrap', mt: 0.25 }}
              >
                Suggest
              </Button>
            </Stack>

            {suggestError && (
              <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                {suggestError}
              </Typography>
            )}

            {suggestions.length > 0 && (
              <Stack direction="row" spacing={1} sx={{ mt: 1.5, flexWrap: 'wrap', gap: 1 }}>
                {suggestions.map((suggestion) => (
                  <Chip
                    key={suggestion.alias_name}
                    label={`${suggestion.alias_name} - ${suggestion.client_email}`}
                    onClick={() => handlePickSuggestion(suggestion)}
                    variant={aliasName === suggestion.alias_name ? 'filled' : 'outlined'}
                    color={aliasName === suggestion.alias_name ? 'primary' : 'default'}
                  />
                ))}
              </Stack>
            )}
          </Box>

          <Box>
            <TextField
              label="Alias Name"
              fullWidth
              value={aliasName}
              onChange={(e) => setAliasName(e.target.value)}
              placeholder="e.g. Amy Jones"
            />

            <Box sx={{ mt: 1.5, minHeight: 48 }}>
              {checking && (
                <Alert severity="info" icon={<CircularProgress size={16} />}>
                  Checking availability...
                </Alert>
              )}
              {!checking && result && (
                <Alert severity={result.ok ? 'success' : 'error'}>{result.message}</Alert>
              )}
            </Box>
          </Box>
        </Stack>
      </Paper>
    </Box>
  );
}

export default AliasNameChecker;
