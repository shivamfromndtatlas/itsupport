import React, { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Alert, Box, Chip, CircularProgress, Link, Stack, ToggleButton, ToggleButtonGroup, Tooltip, Typography } from '@mui/material';
import DesktopWindowsIcon from '@mui/icons-material/DesktopWindows';
import DevicesOtherIcon from '@mui/icons-material/DevicesOther';
import LaptopIcon from '@mui/icons-material/Laptop';
import PhoneAndroidIcon from '@mui/icons-material/PhoneAndroid';
import { DataGrid } from '@mui/x-data-grid';
import { formatDateTime, gridSx } from './shared';

const SOURCE_LABELS = { mobile: 'Mobile devices', cloud_identity: 'Computers and laptops' };

// "Laptop" / "Mobile" etc. as one label, plus where a laptop-or-desktop call came from.
export const typeOf = (device) => {
  if (device.category === 'mobile') return { key: 'mobile', label: 'Mobile', icon: <PhoneAndroidIcon fontSize="small" />, note: '' };
  if (device.category === 'computer') {
    const factor = device.form_factor;
    const note =
      device.form_factor_source === 'portal'
        ? `Taken from portal asset ${device.portal_asset?.asset_id} (${device.portal_asset?.type})`
        : device.form_factor_source === 'model'
          ? 'Guessed from the model name. Google does not report laptop vs desktop.'
          : 'Google does not report laptop vs desktop, and no portal asset matches this serial number.';
    if (factor === 'laptop') return { key: 'laptop', label: 'Laptop', icon: <LaptopIcon fontSize="small" />, note };
    return {
      key: 'computer',
      label: factor ? factor.charAt(0).toUpperCase() + factor.slice(1) : 'Computer',
      icon: <DesktopWindowsIcon fontSize="small" />,
      note,
    };
  }
  return { key: 'unknown', label: 'Unknown', icon: <DevicesOtherIcon fontSize="small" />, note: 'Google did not report a device type.' };
};

const FILTERS = [
  ['all', 'All'],
  ['mobile', 'Mobile'],
  ['laptop', 'Laptops'],
  ['computer', 'Other computers'],
];

function UserDevicesPanel({ report }) {
  const navigate = useNavigate();
  const [filter, setFilter] = useState('all');
  const { data, loading, error } = report;

  const rows = useMemo(() => (data?.devices || []).map((device) => ({ ...device, type: typeOf(device) })), [data]);
  const shown = filter === 'all' ? rows : rows.filter((row) => row.type.key === filter || (filter === 'computer' && row.type.key === 'unknown'));
  const failedSources = Object.entries(data?.sources || {}).filter(([, source]) => !source.ok);

  const columns = [
    {
      field: 'type',
      headerName: 'Type',
      width: 130,
      valueGetter: (value) => value.label,
      renderCell: ({ row }) => (
        <Tooltip title={row.type.note || ''}>
          <Chip size="small" variant="outlined" icon={row.type.icon} label={row.type.label} />
        </Tooltip>
      ),
    },
    { field: 'make', headerName: 'Make', flex: 0.8, minWidth: 120, valueGetter: (value) => value || '—' },
    { field: 'model', headerName: 'Model', flex: 1, minWidth: 150, valueGetter: (value) => value || '—' },
    {
      field: 'serial',
      headerName: 'Serial number',
      flex: 1,
      minWidth: 160,
      renderCell: ({ row }) =>
        row.serial ? (
          <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
            {row.serial}
          </Typography>
        ) : (
          <Tooltip title="Google did not report a serial number. Personal Android and iOS devices usually withhold it.">
            <Typography variant="body2" color="text.secondary">
              Not reported
            </Typography>
          </Tooltip>
        ),
    },
    {
      field: 'os',
      headerName: 'OS',
      flex: 0.9,
      minWidth: 130,
      valueGetter: (value, row) => value || row.platform || '—',
    },
    {
      field: 'ownership',
      headerName: 'Ownership',
      width: 110,
      valueGetter: (value) => (value ? value.charAt(0).toUpperCase() + value.slice(1) : '—'),
    },
    {
      field: 'last_sync',
      headerName: 'Last sync',
      width: 150,
      valueGetter: (value) => (value ? new Date(value) : null),
      renderCell: ({ row }) => formatDateTime(row.last_sync),
    },
    {
      field: 'portal_asset',
      headerName: 'Portal asset',
      width: 130,
      valueGetter: (value) => value?.asset_id || '',
      renderCell: ({ row }) =>
        row.portal_asset ? (
          <Link
            component="button"
            type="button"
            underline="hover"
            onClick={() => navigate(`/inventory/assets/${row.portal_asset.id}`)}
            sx={{ fontSize: 13.5, fontWeight: 600 }}
          >
            {row.portal_asset.asset_id}
          </Link>
        ) : (
          <Typography variant="body2" color="text.secondary">
            —
          </Typography>
        ),
    },
  ];

  return (
    <>
      {loading && (
        <Stack direction="row" spacing={1.5} alignItems="center" sx={{ py: 3 }}>
          <CircularProgress size={20} />
          <Typography variant="body2" color="text.secondary">
            Reading devices from Google. The first lookup reads the whole device list and can take a few seconds.
          </Typography>
        </Stack>
      )}
      {error && <Alert severity="warning">{error}</Alert>}
      {failedSources.map(([name, source]) => (
        <Alert key={name} severity="warning" sx={{ mb: 1.5 }}>
          {SOURCE_LABELS[name] || name} could not be read, so devices of that kind may be missing: {source.error}
        </Alert>
      ))}
      {data && (
        <>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} alignItems={{ sm: 'center' }} sx={{ mb: 1.5 }}>
            <ToggleButtonGroup size="small" exclusive value={filter} onChange={(e, value) => value && setFilter(value)} sx={{ flexWrap: 'wrap' }}>
              {FILTERS.map(([value, label]) => (
                <ToggleButton key={value} value={value} sx={{ textTransform: 'none', px: 1.5 }}>
                  {label}
                </ToggleButton>
              ))}
            </ToggleButtonGroup>
            <Typography variant="body2" color="text.secondary">
              {data.summary.total} device{data.summary.total === 1 ? '' : 's'}: {data.summary.laptops} laptop
              {data.summary.laptops === 1 ? '' : 's'}, {data.summary.other_computers} other computer
              {data.summary.other_computers === 1 ? '' : 's'}, {data.summary.mobile} mobile
            </Typography>
          </Stack>

          {rows.length === 0 ? (
            <Alert severity="info">
              Google lists no devices for this user. Only devices that have signed in with this account and are registered with
              Google (mobile management, Endpoint Verification or Windows management) appear here, so a computer that only uses
              the browser may not.
            </Alert>
          ) : (
            <Box sx={{ overflowX: 'auto' }}>
              <DataGrid
                rows={shown}
                columns={columns}
                autoHeight
                disableRowSelectionOnClick
                pageSizeOptions={[10, 25]}
                initialState={{ pagination: { paginationModel: { pageSize: 10 } } }}
                sx={{ ...gridSx, minWidth: 1000, '& .MuiDataGrid-row': { cursor: 'default' } }}
              />
            </Box>
          )}
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1.5 }}>
            Devices this user has signed in to with their Google account. Google reports an operating system, not laptop or
            desktop, so Laptop comes from the portal asset with the same serial number, or from the model name when it is
            unambiguous (hover the type for which). Last sync is when the device last checked in, not the last time it was used.
          </Typography>
        </>
      )}
    </>
  );
}

export default UserDevicesPanel;
