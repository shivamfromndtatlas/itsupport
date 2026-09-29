import React from 'react';
import { Paper, Typography } from '@mui/material';

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
