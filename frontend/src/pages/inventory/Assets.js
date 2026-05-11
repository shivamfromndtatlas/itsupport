import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Tabs,
  Tab,
  Paper,
  Typography,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
  MenuItem,
  Chip,
  IconButton,
  Tooltip,
  Snackbar,
  Alert,
  Grid,
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import DataTable from '../../components/common/DataTable';
import ConfirmDialog from '../../components/common/ConfirmDialog';
import api from '../../api/axios';

const ASSET_STATUS_COLORS = {
  available: 'success',
  assigned: 'primary',
  maintenance: 'warning',
  retired: 'default',
};

const ASSET_TYPES = ['laptop', 'desktop', 'monitor', 'keyboard', 'mouse', 'printer', 'phone', 'other'];

const EMPTY_ASSET = {
  asset_type: '',
  asset_id: '',
  serial_number: '',
  vendor: '',
  purchase_date: '',
  purchase_cost: '',
  status: 'available',
  attribute_values: {},
};

const EMPTY_LICENSE = {
  software_name: '',
  license_key: '',
  total_seats: '',
  vendor: '',
  purchase_date: '',
  expiry_date: '',
  license_type: 'perpetual',
  notes: '',
};

const LICENSE_TYPES = ['perpetual', 'subscription', 'trial', 'open_source'];

function TabPanel({ value, index, children }) {
  return value === index ? <Box sx={{ pt: 2 }}>{children}</Box> : null;
}

function Assets() {
  const [tab, setTab] = useState(0);

  // Hardware
  const [assets, setAssets] = useState([]);
  const [assetLoading, setAssetLoading] = useState(false);
  const [assetDialog, setAssetDialog] = useState(false);
  const [editAsset, setEditAsset] = useState(null);
  const [assetForm, setAssetForm] = useState(EMPTY_ASSET);
  const [savingAsset, setSavingAsset] = useState(false);
  const [confirmAsset, setConfirmAsset] = useState({ open: false, row: null });

  // Software
  const [licenses, setLicenses] = useState([]);
  const [licenseLoading, setLicenseLoading] = useState(false);
  const [licenseDialog, setLicenseDialog] = useState(false);
  const [editLicense, setEditLicense] = useState(null);
  const [licenseForm, setLicenseForm] = useState(EMPTY_LICENSE);
  const [savingLicense, setSavingLicense] = useState(false);
  const [confirmLicense, setConfirmLicense] = useState({ open: false, row: null });

  const [snack, setSnack] = useState({ open: false, msg: '', severity: 'success' });
  const showSnack = (msg, severity = 'success') => setSnack({ open: true, msg, severity });

  const fetchAssets = useCallback(async () => {
    setAssetLoading(true);
    try {
      const res = await api.get('/inventory/assets/');
      const data = Array.isArray(res.data) ? res.data : res.data.results || [];
      setAssets(data.map((a) => ({ ...a, id: a.id || a.asset_id })));
    } catch {
      showSnack('Failed to load assets.', 'error');
    } finally {
      setAssetLoading(false);
    }
  }, []);

  const fetchLicenses = useCallback(async () => {
    setLicenseLoading(true);
    try {
      const res = await api.get('/inventory/software-licenses/');
      const data = Array.isArray(res.data) ? res.data : res.data.results || [];
      setLicenses(data.map((l) => ({ ...l, id: l.id || l.pk })));
    } catch {
      showSnack('Failed to load licenses.', 'error');
    } finally {
      setLicenseLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAssets();
    fetchLicenses();
  }, [fetchAssets, fetchLicenses]);

  // Asset handlers
  const openAddAsset = () => {
    setEditAsset(null);
    setAssetForm(EMPTY_ASSET);
    setAssetDialog(true);
  };

  const openEditAsset = (row) => {
    setEditAsset(row);
    setAssetForm({
      asset_type: row.asset_type || '',
      asset_id: row.asset_id || '',
      serial_number: row.serial_number || '',
      vendor: row.vendor || '',
      purchase_date: row.purchase_date || '',
      purchase_cost: row.purchase_cost || '',
      status: row.status || 'available',
      attribute_values: row.attribute_values || {},
    });
    setAssetDialog(true);
  };

  const handleSaveAsset = async () => {
    setSavingAsset(true);
    try {
      if (editAsset) {
        await api.patch(`/inventory/assets/${editAsset.id}/`, assetForm);
        showSnack('Asset updated.');
      } else {
        await api.post('/inventory/assets/', assetForm);
        showSnack('Asset added.');
      }
      setAssetDialog(false);
      fetchAssets();
    } catch (err) {
      showSnack(err.response?.data?.detail || 'Save failed.', 'error');
    } finally {
      setSavingAsset(false);
    }
  };

  const handleDeleteAsset = async () => {
    try {
      await api.delete(`/inventory/assets/${confirmAsset.row.id}/`);
      showSnack('Asset deleted.');
      fetchAssets();
    } catch {
      showSnack('Delete failed.', 'error');
    } finally {
      setConfirmAsset({ open: false, row: null });
    }
  };

  // License handlers
  const openAddLicense = () => {
    setEditLicense(null);
    setLicenseForm(EMPTY_LICENSE);
    setLicenseDialog(true);
  };

  const openEditLicense = (row) => {
    setEditLicense(row);
    setLicenseForm({
      software_name: row.software_name || '',
      license_key: row.license_key || '',
      total_seats: row.total_seats || '',
      vendor: row.vendor || '',
      purchase_date: row.purchase_date || '',
      expiry_date: row.expiry_date || '',
      license_type: row.license_type || 'perpetual',
      notes: row.notes || '',
    });
    setLicenseDialog(true);
  };

  const handleSaveLicense = async () => {
    setSavingLicense(true);
    try {
      if (editLicense) {
        await api.patch(`/inventory/software-licenses/${editLicense.id}/`, licenseForm);
        showSnack('License updated.');
      } else {
        await api.post('/inventory/software-licenses/', licenseForm);
        showSnack('License added.');
      }
      setLicenseDialog(false);
      fetchLicenses();
    } catch (err) {
      showSnack(err.response?.data?.detail || 'Save failed.', 'error');
    } finally {
      setSavingLicense(false);
    }
  };

  const handleDeleteLicense = async () => {
    try {
      await api.delete(`/inventory/software-licenses/${confirmLicense.row.id}/`);
      showSnack('License deleted.');
      fetchLicenses();
    } catch {
      showSnack('Delete failed.', 'error');
    } finally {
      setConfirmLicense({ open: false, row: null });
    }
  };

  const assetColumns = [
    { field: 'asset_id', headerName: 'Asset ID', width: 130 },
    { field: 'asset_type_name', headerName: 'Type', width: 120 },
    {
      field: 'status',
      headerName: 'Status',
      width: 130,
      renderCell: ({ value }) => (
        <Chip
          label={value || ''}
          color={ASSET_STATUS_COLORS[value] || 'default'}
          size="small"
          sx={{ textTransform: 'capitalize' }}
        />
      ),
    },
    { field: 'vendor', headerName: 'Vendor', flex: 1 },
    { field: 'purchase_date', headerName: 'Purchase Date', width: 140 },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 100,
      sortable: false,
      renderCell: ({ row }) => (
        <Box>
          <Tooltip title="Edit">
            <IconButton size="small" onClick={() => openEditAsset(row)}>
              <EditIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Delete">
            <IconButton size="small" color="error" onClick={() => setConfirmAsset({ open: true, row })}>
              <DeleteIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      ),
    },
  ];

  const licenseColumns = [
    { field: 'software_name', headerName: 'Software Name', flex: 1, minWidth: 150 },
    {
      field: 'license_key',
      headerName: 'License Key',
      flex: 1,
      minWidth: 180,
      renderCell: ({ value }) => (
        <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
          {value ? `${value.slice(0, 8)}${'*'.repeat(8)}` : '--'}
        </Typography>
      ),
    },
    { field: 'total_seats', headerName: 'Total Seats', width: 120, type: 'number' },
    { field: 'available_seats', headerName: 'Available', width: 110, type: 'number' },
    { field: 'expiry_date', headerName: 'Expiry', width: 120 },
    {
      field: 'is_active',
      headerName: 'Status',
      width: 110,
      renderCell: ({ value }) => (
        <Chip label={value ? 'Active' : 'Inactive'} color={value ? 'success' : 'default'} size="small" />
      ),
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 100,
      sortable: false,
      renderCell: ({ row }) => (
        <Box>
          <Tooltip title="Edit">
            <IconButton size="small" onClick={() => openEditLicense(row)}>
              <EditIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Delete">
            <IconButton size="small" color="error" onClick={() => setConfirmLicense({ open: true, row })}>
              <DeleteIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      ),
    },
  ];

  return (
    <Box>
      <Typography variant="h6" fontWeight={600} sx={{ mb: 2 }}>
        IT Assets
      </Typography>
      <Paper sx={{ borderRadius: 2 }}>
        <Tabs
          value={tab}
          onChange={(_, v) => setTab(v)}
          sx={{ borderBottom: 1, borderColor: 'divider', px: 2 }}
        >
          <Tab label="Hardware Assets" />
          <Tab label="Software Licenses" />
        </Tabs>
        <Box sx={{ p: 2 }}>
          <TabPanel value={tab} index={0}>
            <DataTable
              rows={assets}
              columns={assetColumns}
              loading={assetLoading}
              onAdd={openAddAsset}
              addLabel="Add Asset"
              searchable
            />
          </TabPanel>
          <TabPanel value={tab} index={1}>
            <DataTable
              rows={licenses}
              columns={licenseColumns}
              loading={licenseLoading}
              onAdd={openAddLicense}
              addLabel="Add License"
              searchable
            />
          </TabPanel>
        </Box>
      </Paper>

      {/* Add/Edit Asset Dialog */}
      <Dialog open={assetDialog} onClose={() => setAssetDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editAsset ? 'Edit Asset' : 'Add Asset'}</DialogTitle>
        <DialogContent sx={{ pt: '12px !important' }}>
          <Grid container spacing={2}>
            <Grid item xs={12} sm={6}>
              <TextField
                select
                label="Asset Type"
                fullWidth
                value={assetForm.asset_type}
                onChange={(e) => setAssetForm({ ...assetForm, asset_type: e.target.value })}
              >
                {ASSET_TYPES.map((t) => (
                  <MenuItem key={t} value={t}>
                    {t}
                  </MenuItem>
                ))}
              </TextField>
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                label="Asset ID"
                fullWidth
                value={assetForm.asset_id}
                onChange={(e) => setAssetForm({ ...assetForm, asset_id: e.target.value })}
                disabled={!!editAsset}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                label="Serial Number"
                fullWidth
                value={assetForm.serial_number}
                onChange={(e) => setAssetForm({ ...assetForm, serial_number: e.target.value })}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                label="Vendor"
                fullWidth
                value={assetForm.vendor}
                onChange={(e) => setAssetForm({ ...assetForm, vendor: e.target.value })}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                label="Purchase Date"
                type="date"
                fullWidth
                value={assetForm.purchase_date}
                onChange={(e) => setAssetForm({ ...assetForm, purchase_date: e.target.value })}
                InputLabelProps={{ shrink: true }}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                label="Purchase Cost"
                type="number"
                fullWidth
                value={assetForm.purchase_cost}
                onChange={(e) => setAssetForm({ ...assetForm, purchase_cost: e.target.value })}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                select
                label="Status"
                fullWidth
                value={assetForm.status}
                onChange={(e) => setAssetForm({ ...assetForm, status: e.target.value })}
              >
                {Object.keys(ASSET_STATUS_COLORS).map((s) => (
                  <MenuItem key={s} value={s}>
                    {s}
                  </MenuItem>
                ))}
              </TextField>
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setAssetDialog(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleSaveAsset} disabled={savingAsset}>
            {savingAsset ? 'Saving...' : 'Save'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Add/Edit License Dialog */}
      <Dialog open={licenseDialog} onClose={() => setLicenseDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editLicense ? 'Edit License' : 'Add License'}</DialogTitle>
        <DialogContent sx={{ pt: '12px !important' }}>
          <Grid container spacing={2}>
            <Grid item xs={12} sm={6}>
              <TextField
                label="Software Name"
                fullWidth
                value={licenseForm.software_name}
                onChange={(e) => setLicenseForm({ ...licenseForm, software_name: e.target.value })}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                label="License Key"
                fullWidth
                value={licenseForm.license_key}
                onChange={(e) => setLicenseForm({ ...licenseForm, license_key: e.target.value })}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                label="Total Seats"
                type="number"
                fullWidth
                value={licenseForm.total_seats}
                onChange={(e) => setLicenseForm({ ...licenseForm, total_seats: e.target.value })}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                label="Vendor"
                fullWidth
                value={licenseForm.vendor}
                onChange={(e) => setLicenseForm({ ...licenseForm, vendor: e.target.value })}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                label="Purchase Date"
                type="date"
                fullWidth
                value={licenseForm.purchase_date}
                onChange={(e) => setLicenseForm({ ...licenseForm, purchase_date: e.target.value })}
                InputLabelProps={{ shrink: true }}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                label="Expiry Date"
                type="date"
                fullWidth
                value={licenseForm.expiry_date}
                onChange={(e) => setLicenseForm({ ...licenseForm, expiry_date: e.target.value })}
                InputLabelProps={{ shrink: true }}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                select
                label="License Type"
                fullWidth
                value={licenseForm.license_type}
                onChange={(e) => setLicenseForm({ ...licenseForm, license_type: e.target.value })}
              >
                {LICENSE_TYPES.map((t) => (
                  <MenuItem key={t} value={t}>
                    {t.replace('_', ' ')}
                  </MenuItem>
                ))}
              </TextField>
            </Grid>
            <Grid item xs={12}>
              <TextField
                label="Notes"
                fullWidth
                multiline
                rows={2}
                value={licenseForm.notes}
                onChange={(e) => setLicenseForm({ ...licenseForm, notes: e.target.value })}
              />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setLicenseDialog(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleSaveLicense} disabled={savingLicense}>
            {savingLicense ? 'Saving...' : 'Save'}
          </Button>
        </DialogActions>
      </Dialog>

      <ConfirmDialog
        open={confirmAsset.open}
        title="Delete Asset"
        message={`Delete asset ${confirmAsset.row?.asset_id}?`}
        onConfirm={handleDeleteAsset}
        onCancel={() => setConfirmAsset({ open: false, row: null })}
        confirmLabel="Delete"
      />

      <ConfirmDialog
        open={confirmLicense.open}
        title="Delete License"
        message={`Delete license for ${confirmLicense.row?.software_name}?`}
        onConfirm={handleDeleteLicense}
        onCancel={() => setConfirmLicense({ open: false, row: null })}
        confirmLabel="Delete"
      />

      <Snackbar
        open={snack.open}
        autoHideDuration={4000}
        onClose={() => setSnack({ ...snack, open: false })}
      >
        <Alert severity={snack.severity} onClose={() => setSnack({ ...snack, open: false })}>
          {snack.msg}
        </Alert>
      </Snackbar>
    </Box>
  );
}

export default Assets;
