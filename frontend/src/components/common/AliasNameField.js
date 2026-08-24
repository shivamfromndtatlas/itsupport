import React, { useEffect, useRef, useState } from 'react';
import {
  Box,
  TextField,
  IconButton,
  Tooltip,
  Menu,
  MenuItem,
  ListItemText,
  CircularProgress,
  Typography,
} from '@mui/material';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import api from '../../api/axios';

// Shared alias-name input: live-validates against the backend alias rules
// (matching initials, no middle name, globally unique derived client email)
// and offers curated western-name suggestions matching the employee's
// initials. Used by Onboarding, Employees, and Organisations forms.
function AliasNameField({
  label = 'Alias Name',
  fullName,
  value,
  onChange,
  onClientEmailChange,
  excludeEmployeeId,
  excludeProfileId,
  fullWidth = true,
  disabled = false,
  // The alias value (and its already-derived client email) as loaded from
  // the record, if editing one. While the field still holds this exact
  // value, we skip live validation -- older records may carry an alias that
  // predates the initials-matching rule, and re-checking it on every load
  // would flag it as broken even though nothing changed.
  initialValue,
  initialClientEmail,
}) {
  const [anchorEl, setAnchorEl] = useState(null);
  const [suggestions, setSuggestions] = useState([]);
  const [suggesting, setSuggesting] = useState(false);
  const [validating, setValidating] = useState(false);
  const [error, setError] = useState('');
  const [clientEmail, setClientEmail] = useState('');
  const debounceRef = useRef(null);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);

    if (!value || !value.trim()) {
      setError('');
      setClientEmail('');
      onClientEmailChange?.(null);
      return undefined;
    }
    if (!fullName || !fullName.trim()) {
      return undefined;
    }

    if (initialValue !== undefined && value === initialValue) {
      setError('');
      setClientEmail(initialClientEmail || '');
      onClientEmailChange?.(initialClientEmail || null);
      return undefined;
    }

    debounceRef.current = setTimeout(async () => {
      setValidating(true);
      try {
        const res = await api.post('/employees/validate-alias/', {
          full_name: fullName,
          alias_name: value,
          exclude_employee_id: excludeEmployeeId,
          exclude_profile_id: excludeProfileId,
        });
        setError('');
        setClientEmail(res.data.client_email);
        onClientEmailChange?.(res.data.client_email);
      } catch (err) {
        const detail =
          err.response?.data?.alias_name || err.response?.data?.detail || 'Invalid alias name.';
        setError(Array.isArray(detail) ? detail.join(' ') : detail);
        setClientEmail('');
        onClientEmailChange?.(null);
      } finally {
        setValidating(false);
      }
    }, 400);

    return () => clearTimeout(debounceRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, fullName, excludeEmployeeId, excludeProfileId, initialValue, initialClientEmail]);

  const handleSuggestClick = async (event) => {
    if (!fullName || !fullName.trim()) return;
    setAnchorEl(event.currentTarget);
    setSuggesting(true);
    try {
      const res = await api.get('/employees/alias-suggestions/', {
        params: { full_name: fullName },
      });
      setSuggestions(res.data.suggestions || []);
    } catch {
      setSuggestions([]);
    } finally {
      setSuggesting(false);
    }
  };

  const handlePick = (suggestion) => {
    onChange(suggestion.alias_name);
    setAnchorEl(null);
  };

  return (
    <Box>
      <TextField
        label={label}
        value={value || ''}
        onChange={(e) => onChange(e.target.value)}
        fullWidth={fullWidth}
        disabled={disabled}
        error={Boolean(error)}
        helperText={
          error ||
          (validating
            ? 'Checking...'
            : clientEmail
            ? `Client email: ${clientEmail}`
            : 'First + last name only, matching initials, e.g. "Andrew King" for "Ajay Kumar".')
        }
        slotProps={{
          input: {
            endAdornment: (
              <Tooltip title={fullName?.trim() ? 'Suggest alias names' : 'Enter full name first'}>
                <span>
                  <IconButton
                    size="small"
                    onClick={handleSuggestClick}
                    disabled={disabled || !fullName?.trim()}
                  >
                    <AutoAwesomeIcon fontSize="small" />
                  </IconButton>
                </span>
              </Tooltip>
            ),
          },
        }}
      />
      <Menu anchorEl={anchorEl} open={Boolean(anchorEl)} onClose={() => setAnchorEl(null)}>
        {suggesting && (
          <MenuItem disabled>
            <CircularProgress size={16} sx={{ mr: 1 }} /> Loading suggestions...
          </MenuItem>
        )}
        {!suggesting && suggestions.length === 0 && (
          <MenuItem disabled>No suggestions available.</MenuItem>
        )}
        {!suggesting &&
          suggestions.map((suggestion) => (
            <MenuItem key={suggestion.alias_name} onClick={() => handlePick(suggestion)}>
              <ListItemText
                primary={suggestion.alias_name}
                secondary={
                  <Typography variant="caption" color="text.secondary">
                    {suggestion.client_email}
                  </Typography>
                }
              />
            </MenuItem>
          ))}
      </Menu>
    </Box>
  );
}

export default AliasNameField;
