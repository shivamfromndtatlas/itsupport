import React, { useEffect, useState } from 'react';
import { Paper, Typography } from '@mui/material';
import api from '../../api/axios';

export const formatDateTime = (value) => {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  const pad = (n) => String(n).padStart(2, '0');
  return `${pad(date.getDate())}-${pad(date.getMonth() + 1)}-${date.getFullYear()} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
};

export const initialsOf = (user) =>
  (user.full_name || user.primary_email || '?')
    .split(/\s+/)
    .map((part) => part[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);

export const statusOf = (user) => {
  if (user.archived) return { key: 'archived', label: 'Archived', color: 'default' };
  if (user.suspended) return { key: 'suspended', label: 'Suspended', color: 'error' };
  return { key: 'active', label: 'Active', color: 'success' };
};

export const adminLabel = (user) => {
  if (user.is_admin) return 'Super admin';
  if (user.is_delegated_admin) return 'Delegated admin';
  return 'No';
};

export const userDashboardPath = (email) => `/google-workspace/users/${encodeURIComponent(email)}`;

export function StatCard({ label, value, color, hint }) {
  return (
    <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 2 }}>
      <Typography variant="caption" color="text.secondary" fontWeight={700} sx={{ textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        {label}
      </Typography>
      <Typography variant="h5" fontWeight={800} color={color}>
        {value}
      </Typography>
      {hint && (
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
          {hint}
        </Typography>
      )}
    </Paper>
  );
}

export const gridSx = {
  border: 'none',
  fontSize: 13.5,
  '& .MuiDataGrid-row': { cursor: 'pointer' },
  '& .MuiDataGrid-columnHeaders': { backgroundColor: '#F8FAFC', borderBottom: '1px solid #E2E8F0' },
  '& .MuiDataGrid-columnHeaderTitle': { fontWeight: 700, fontSize: 12, color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.05em' },
  '& .MuiDataGrid-row:hover': { backgroundColor: '#F8FAFC' },
  '& .MuiDataGrid-cell': { borderBottom: '1px solid #F1F5F9', '&:focus': { outline: 'none' }, '&:focus-within': { outline: 'none' } },
  '& .MuiDataGrid-footerContainer': { borderTop: '1px solid #E2E8F0', backgroundColor: '#F8FAFC' },
};

// email -> data URI, or null for "no picture". Module-level so paging, revisiting a page or opening
// a user's dashboard never asks again within a session (the server also caches for an hour).
const photoCache = new Map();
const PHOTO_BATCH = 40;
let photoError = '';

/**
 * Loads profile pictures in batches and returns a lookup (email -> image URL or undefined), with
 * the last failure's reason on ``lookup.error``. Everyone is asked about, not just users Google
 * flags as having a photo: that flag is a hint the list may not carry, and the server answers
 * "none" cheaply (and remembers it). Users without a picture, and any failed batch, keep initials.
 */
export function useUserPhotos(users) {
  const [, setLoaded] = useState(0);

  useEffect(() => {
    const wanted = (users || []).filter((user) => !photoCache.has(user.primary_email)).map((user) => user.primary_email);
    if (!wanted.length) return undefined;
    let cancelled = false;
    (async () => {
      for (let i = 0; i < wanted.length && !cancelled; i += PHOTO_BATCH) {
        const batch = wanted.slice(i, i + PHOTO_BATCH);
        try {
          const res = await api.get('/integrations/google-workspace/user-photos/', { params: { emails: batch.join(',') } });
          Object.entries(res.data?.photos || {}).forEach(([email, photo]) => {
            // A failed fetch comes back null too; when the server reports an error, don't remember
            // those as "no picture", so a later visit retries.
            if (photo || !res.data?.error) photoCache.set(email, photo || null);
          });
          photoError = res.data?.error || '';
          if (!cancelled) setLoaded((n) => n + 1);
        } catch (err) {
          photoError = err.response?.data?.detail || 'The photo request failed.';
          if (!cancelled) setLoaded((n) => n + 1);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [users]);

  const lookup = (email) => photoCache.get(email) || undefined;
  lookup.error = photoError;
  return lookup;
}
