import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
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
  useMediaQuery,
  useTheme,
} from '@mui/material';
import SettingsBackupRestoreIcon from '@mui/icons-material/SettingsBackupRestore';
import PrintIcon from '@mui/icons-material/Print';
import { QRCodeSVG } from 'qrcode.react';
import DataTable from '../../components/common/DataTable';
import ConfirmDialog from '../../components/common/ConfirmDialog';
import api from '../../api/axios';

function TabPanel({ value, index, children }) {
  return value === index ? <Box sx={{ pt: 2 }}>{children}</Box> : null;
}

const EMPTY_HW_FORM = {
  employee: '',
  asset: '',
  assigned_date: new Date().toISOString().split('T')[0],
  notes: '',
};

const EMPTY_SW_FORM = {
  employee: '',
  software_license: '',
  assigned_date: new Date().toISOString().split('T')[0],
};

function AssetAllocation() {
  const theme = useTheme();
  const fullScreen = useMediaQuery(theme.breakpoints.down('sm'));
  const [tab, setTab] = useState(0);

  // Hardware
  const [hwAllocations, setHwAllocations] = useState([]);
  const [hwLoading, setHwLoading] = useState(false);
  const [hwDialog, setHwDialog] = useState(false);
  const [hwForm, setHwForm] = useState(EMPTY_HW_FORM);
  const [savingHw, setSavingHw] = useState(false);
  const [recoverHw, setRecoverHw] = useState({ open: false, row: null });
  const [qrDialog, setQrDialog] = useState({ open: false, data: null, asset: null });

  // Software
  const [swAllocations, setSwAllocations] = useState([]);
  const [swLoading, setSwLoading] = useState(false);
  const [swDialog, setSwDialog] = useState(false);
  const [swForm, setSwForm] = useState(EMPTY_SW_FORM);
  const [savingSw, setSavingSw] = useState(false);
  const [revokeSw, setRevokeSw] = useState({ open: false, row: null });

  // Dropdowns
  const [employees, setEmployees] = useState([]);
  const [availableAssets, setAvailableAssets] = useState([]);
  const [availableLicenses, setAvailableLicenses] = useState([]);
  const [assetTypes, setAssetTypes] = useState([]);
  const [assetTypeFilter, setAssetTypeFilter] = useState([]);

  const assetTypeOptions = useMemo(() => {
    const filterKey = tab === 0 ? 'hardware' : 'software';
    return assetTypes.filter((type) => type.asset_type === filterKey);
  }, [assetTypes, tab]);

  const [snack, setSnack] = useState({ open: false, msg: '', severity: 'success' });
  const qrRef = useRef();

  const showSnack = (msg, severity = 'success') => setSnack({ open: true, msg, severity });

  const formatAssetLabel = (asset) => {
    if (!asset) return '';
    const values = asset.attribute_values_with_names || asset.attribute_values || {};
    const make = values.make || values.Make || values.make_name || values.MakeName || values.Brand || values.brand || '';
    const model = values.model || values.Model || values.model_name || values.ModelName || '';
    const typeName = asset.asset_type_name || asset.asset_type || '';
    const details = [make, model].filter(Boolean).join(' - ');
    if (details && typeName) {
      return `${asset.asset_id} (${details} • ${typeName})`;
    }
    if (details) return `${asset.asset_id} (${details})`;
    if (typeName) return `${asset.asset_id} (${typeName})`;
    return asset.asset_id;
  };

  const fetchAll = useCallback(async () => {
    setHwLoading(true);
    setSwLoading(true);
    try {
      const [hwRes, swRes, empRes, assetRes, licRes, typeRes] = await Promise.all([
        api.get('/allocation/assets/').catch(() => ({ data: [] })),
        api.get('/allocation/licenses/').catch(() => ({ data: [] })),
        api.get('/employees/').catch(() => ({ data: [] })),
        api.get('/inventory/assets/?status=available&source=portal').catch(() => ({ data: [] })),
        api.get('/inventory/software-licenses/').catch(() => ({ data: [] })),
        api.get('/inventory/asset-types/').catch(() => ({ data: [] })),
      ]);

      const hw = Array.isArray(hwRes.data) ? hwRes.data : hwRes.data.results || [];
      const sw = Array.isArray(swRes.data) ? swRes.data : swRes.data.results || [];
      const emp = Array.isArray(empRes.data) ? empRes.data : empRes.data.results || [];
      const assets = Array.isArray(assetRes.data) ? assetRes.data : assetRes.data.results || [];
      const lics = Array.isArray(licRes.data) ? licRes.data : licRes.data.results || [];

      setHwAllocations(hw.map((r) => ({ ...r, id: r.id || r.pk })));
      setSwAllocations(sw.map((r) => ({ ...r, id: r.id || r.pk })));
      setEmployees(emp.map((e) => ({ ...e, id: e.id || e.pk })));
      setAvailableAssets(assets.map((a) => ({ ...a, id: a.id || a.pk })));
      setAvailableLicenses(lics.map((l) => ({ ...l, id: l.id || l.pk })));
      const types = Array.isArray(typeRes.data) ? typeRes.data : typeRes.data.results || [];
      setAssetTypes(types.map((t) => ({ ...t, id: t.id || t.pk })));
    } catch {
      showSnack('Failed to load data.', 'error');
    } finally {
      setHwLoading(false);
      setSwLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  const handleAssignHw = async () => {
    setSavingHw(true);
    try {
      const res = await api.post('/allocation/assets/', hwForm);
      showSnack('Asset assigned successfully.');
      setHwDialog(false);
      setHwForm(EMPTY_HW_FORM);
      // Show QR
      const asset = availableAssets.find((a) => a.id === hwForm.asset || String(a.id) === String(hwForm.asset));
      const emp = employees.find((e) => e.id === hwForm.employee || String(e.id) === String(hwForm.employee));
      const qrData = JSON.stringify({
        allocation_id: res.data?.id,
        asset_id: asset?.asset_id || hwForm.asset,
        asset_type: asset?.asset_type,
        employee: emp?.full_name || emp?.email,
        assigned_date: hwForm.assigned_date,
      });
      setQrDialog({ open: true, data: qrData, asset: asset?.asset_id || hwForm.asset });
      fetchAll();
    } catch (err) {
      showSnack(err.response?.data?.detail || 'Assignment failed.', 'error');
    } finally {
      setSavingHw(false);
    }
  };

  const handleRecoverHw = async () => {
    try {
      await api.post(`/allocation/assets/${recoverHw.row.id}/recover/`);
      showSnack('Asset recovered.');
      fetchAll();
    } catch {
      showSnack('Recovery failed.', 'error');
    } finally {
      setRecoverHw({ open: false, row: null });
    }
  };

  const handleAssignSw = async () => {
    setSavingSw(true);
    try {
      await api.post('/allocation/licenses/', swForm);
      showSnack('License assigned successfully.');
      setSwDialog(false);
      setSwForm(EMPTY_SW_FORM);
      fetchAll();
    } catch (err) {
      showSnack(err.response?.data?.detail || 'Assignment failed.', 'error');
    } finally {
      setSavingSw(false);
    }
  };

  const handleRevokeSw = async () => {
    try {
      await api.post(`/allocation/licenses/${revokeSw.row.id}/revoke/`);
      showSnack('License revoked.');
      fetchAll();
    } catch {
      showSnack('Revoke failed.', 'error');
    } finally {
      setRevokeSw({ open: false, row: null });
    }
  };

  const handlePrintQR = () => {
    const printWindow = window.open('', '_blank');
    const svgEl = qrRef.current?.querySelector('svg');
    if (!svgEl) return;
    const svgContent = svgEl.outerHTML;
    const scriptClose = String.fromCharCode(60) + '/script>';
    const scriptTag = '<script>window.onload=()=>{window.print();window.close();}' + scriptClose;
    printWindow.document.write(
      '<html><head><title>Asset QR Label</title>' +
      '<style>body{font-family:sans-serif;text-align:center;padding:20px;}h2{margin-bottom:8px;}</style>' +
      '</head><body>' +
      '<h2>Asset: ' + qrDialog.asset + '</h2>' +
      svgContent +
      scriptTag +
      '</body></html>'
    );
    printWindow.document.close();
  };

  const findAttributeValue = (attributes, searchTerms) => {
    if (!attributes) return '--';
    for (const term of searchTerms) {
      if (attributes[term]) return attributes[term];
    }
    return '--';
  };

  const hwColumns = [
    {
      field: 'asset_detail',
      headerName: 'Asset IDs',
      flex: 0.8,
      renderCell: ({ row }) => row.asset_detail?.asset_id || row.asset_id || row.asset || '--',
    },
    {
      field: 'asset_type',
      headerName: 'Asset Type',
      flex: 0.8,
      renderCell: ({ row }) => row.asset_detail?.asset_type_name || row.asset_detail?.asset_type || '--',
    },
    {
      field: 'brand_name',
      headerName: 'Brand Name',
      flex: 0.8,
      renderCell: ({ row }) => {
        const values = row.asset_detail?.attribute_values_with_names || row.asset_detail?.attribute_values || {};
        return findAttributeValue(values, ['Brand', 'brand', 'Make', 'make', 'Manufacturer', 'manufacturer']);
      },
    },
    {
      field: 'model',
      headerName: 'Model',
      flex: 0.8,
      renderCell: ({ row }) => {
        const values = row.asset_detail?.attribute_values_with_names || row.asset_detail?.attribute_values || {};
        return findAttributeValue(values, ['Model', 'model']);
      },
    },
    {
      field: 'employee_detail',
      headerName: 'Employee Name',
      flex: 1,
      renderCell: ({ row }) => row.employee_detail?.full_name || row.employee_name || row.employee || '--',
    },
    { field: 'assigned_date', headerName: 'Assigned Date', width: 140 },
    {
      field: 'status',
      headerName: 'Asset Condition',
      width: 140,
      renderCell: ({ row }) => {
        const attrValues = row.asset_detail?.attribute_values_with_names || row.asset_detail?.attribute_values || {};
        const condition = attrValues.condition || attrValues.Condition || 'Active';
        const colorMap = {
          'Good': 'success',
          'Fair': 'warning',
          'Poor': 'error',
          'Active': 'primary',
          'Recovered': 'default',
        };
        return (
          <Chip
            label={condition}
            color={colorMap[condition] || 'default'}
            size="small"
            sx={{ textTransform: 'capitalize' }}
          />
        );
      },
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 100,
      sortable: false,
      renderCell: ({ row }) =>
        row.status !== 'recovered' ? (
          <Tooltip title="Recover Asset">
            <IconButton
              size="small"
              color="warning"
              onClick={() => setRecoverHw({ open: true, row })}
            >
              <SettingsBackupRestoreIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        ) : null,
    },
  ];

  const swColumns = [
    {
      field: 'license_detail',
      headerName: 'Software',
      flex: 1,
      renderCell: ({ row }) =>
        row.license_detail?.software_name || row.software_name || row.software_license || '--',
    },
    {
      field: 'employee_detail',
      headerName: 'Employee',
      flex: 1,
      renderCell: ({ row }) =>
        row.employee_detail?.full_name || row.employee_name || row.employee || '--',
    },
    { field: 'assigned_date', headerName: 'Assigned Date', width: 140 },
    {
      field: 'status',
      headerName: 'Status',
      width: 120,
      renderCell: ({ value }) => (
        <Chip
          label={value || 'active'}
          color={value === 'revoked' ? 'default' : 'success'}
          size="small"
          sx={{ textTransform: 'capitalize' }}
        />
      ),
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 100,
      sortable: false,
      renderCell: ({ row }) =>
        row.status !== 'revoked' ? (
          <Tooltip title="Revoke License">
            <IconButton
              size="small"
              color="error"
              onClick={() => setRevokeSw({ open: true, row })}
            >
              <SettingsBackupRestoreIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        ) : null,
    },
  ];

  const filteredHwAllocations = useMemo(() => {
    if (!assetTypeFilter.length) return hwAllocations;
    return hwAllocations.filter((row) => {
      const typeName = row.asset_detail?.asset_type_name || row.asset_detail?.asset_type || '';
      return assetTypeFilter.includes(typeName);
    });
  }, [hwAllocations, assetTypeFilter]);

  return (
    <Box>
      <Typography variant="h6" fontWeight={600} sx={{ mb: 2 }}>
        Asset Allocation
      </Typography>
      <Paper sx={{ borderRadius: 2 }}>
        <Tabs
          value={tab}
          onChange={(_, v) => {
            setTab(v);
            setAssetTypeFilter([]);
          }}
          sx={{ borderBottom: 1, borderColor: 'divider', px: 2 }}
        >
          <Tab label="Hardware Allocation" />
          <Tab label="Software License Allocation" />
        </Tabs>
        <Box sx={{ p: 2 }}>
          <TabPanel value={tab} index={0}>
            <DataTable
              rows={filteredHwAllocations}
              columns={hwColumns}
              loading={hwLoading}
              onAdd={() => { setHwForm(EMPTY_HW_FORM); setHwDialog(true); }}
              addLabel="Assign Asset"
              searchable
              toolbar={
                <TextField
                  select
                  size="small"
                  label="Hardware Asset Type"
                  value={assetTypeFilter}
                  onChange={(e) => setAssetTypeFilter(e.target.value)}
                  SelectProps={{ multiple: true, renderValue: (selected) => (selected.length ? selected.join(', ') : 'All asset types') }}
                  sx={{ minWidth: 240, maxWidth: 420 }}
                >
                  {assetTypeOptions.map((type) => (
                    <MenuItem key={type.id} value={type.name}>
                      {type.name}
                    </MenuItem>
                  ))}
                </TextField>
              }
            />
          </TabPanel>
          <TabPanel value={tab} index={1}>
            <DataTable
              rows={swAllocations}
              columns={swColumns}
              loading={swLoading}
              onAdd={() => { setSwForm(EMPTY_SW_FORM); setSwDialog(true); }}
              addLabel="Assign License"
              searchable
              toolbar={
                <TextField
                  select
                  size="small"
                  label="Software Asset Type"
                  value={assetTypeFilter}
                  onChange={(e) => setAssetTypeFilter(e.target.value)}
                  SelectProps={{ multiple: true, renderValue: (selected) => (selected.length ? selected.join(', ') : 'All asset types') }}
                  sx={{ minWidth: 240, maxWidth: 420 }}
                >
                  {assetTypeOptions.map((type) => (
                    <MenuItem key={type.id} value={type.name}>
                      {type.name}
                    </MenuItem>
                  ))}
                </TextField>
              }
            />
          </TabPanel>
        </Box>
      </Paper>

      {/* HW Assign Dialog */}
      <Dialog open={hwDialog} onClose={() => setHwDialog(false)} maxWidth="sm" fullWidth fullScreen={fullScreen}>
        <DialogTitle>Assign Asset</DialogTitle>
        <DialogContent sx={{ pt: '12px !important' }}>
          <Grid container spacing={2}>
            <Grid item xs={12}>
              <TextField
                select
                label="Employee"
                fullWidth
                value={hwForm.employee}
                onChange={(e) => setHwForm({ ...hwForm, employee: e.target.value })}
              >
                {employees.map((e) => (
                  <MenuItem key={e.id} value={e.id}>
                    {e.full_name || e.email} ({e.employee_id})
                  </MenuItem>
                ))}
              </TextField>
            </Grid>
            <Grid item xs={12}>
              <TextField
                select
                label="Available Asset"
                fullWidth
                value={hwForm.asset}
                onChange={(e) => setHwForm({ ...hwForm, asset: e.target.value })}
              >
                {availableAssets.map((a) => (
                  <MenuItem key={a.id} value={a.id}>
                    {formatAssetLabel(a)}
                  </MenuItem>
                ))}
              </TextField>
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                label="Assigned Date"
                type="date"
                fullWidth
                value={hwForm.assigned_date}
                onChange={(e) => setHwForm({ ...hwForm, assigned_date: e.target.value })}
                InputLabelProps={{ shrink: true }}
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                label="Notes"
                fullWidth
                multiline
                rows={2}
                value={hwForm.notes}
                onChange={(e) => setHwForm({ ...hwForm, notes: e.target.value })}
              />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setHwDialog(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleAssignHw} disabled={savingHw}>
            {savingHw ? 'Assigning...' : 'Assign'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* SW Assign Dialog */}
      <Dialog open={swDialog} onClose={() => setSwDialog(false)} maxWidth="sm" fullWidth fullScreen={fullScreen}>
        <DialogTitle>Assign Software License</DialogTitle>
        <DialogContent sx={{ pt: '12px !important' }}>
          <Grid container spacing={2}>
            <Grid item xs={12}>
              <TextField
                select
                label="Employee"
                fullWidth
                value={swForm.employee}
                onChange={(e) => setSwForm({ ...swForm, employee: e.target.value })}
              >
                {employees.map((e) => (
                  <MenuItem key={e.id} value={e.id}>
                    {e.full_name || e.email}
                  </MenuItem>
                ))}
              </TextField>
            </Grid>
            <Grid item xs={12}>
              <TextField
                select
                label="Software License"
                fullWidth
                value={swForm.software_license}
                onChange={(e) => setSwForm({ ...swForm, software_license: e.target.value })}
              >
                {availableLicenses.map((l) => (
                  <MenuItem key={l.id} value={l.id}>
                    {l.software_name} ({l.available_seats ?? '?'} seats left)
                  </MenuItem>
                ))}
              </TextField>
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                label="Assigned Date"
                type="date"
                fullWidth
                value={swForm.assigned_date}
                onChange={(e) => setSwForm({ ...swForm, assigned_date: e.target.value })}
                InputLabelProps={{ shrink: true }}
              />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setSwDialog(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleAssignSw} disabled={savingSw}>
            {savingSw ? 'Assigning...' : 'Assign'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* QR Code Label Dialog */}
      <Dialog open={qrDialog.open} onClose={() => setQrDialog({ open: false, data: null, asset: null })} maxWidth="xs" fullWidth>
        <DialogTitle>Asset QR Label</DialogTitle>
        <DialogContent>
          <Box sx={{ textAlign: 'center', py: 2 }} ref={qrRef}>
            <Typography variant="h6" fontWeight={700} sx={{ mb: 2 }}>
              Asset: {qrDialog.asset}
            </Typography>
            {qrDialog.data && (
              <QRCodeSVG
                value={qrDialog.data}
                size={200}
                level="M"
                includeMargin
              />
            )}
            <Typography variant="caption" display="block" sx={{ mt: 1, color: 'text.secondary' }}>
              Scan to view allocation details
            </Typography>
          </Box>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button
            startIcon={<PrintIcon />}
            variant="contained"
            onClick={handlePrintQR}
          >
            Print Label
          </Button>
          <Button onClick={() => setQrDialog({ open: false, data: null, asset: null })}>
            Close
          </Button>
        </DialogActions>
      </Dialog>

      {/* Recover Confirm */}
      <ConfirmDialog
        open={recoverHw.open}
        title="Recover Asset"
        message={`Mark this asset allocation as recovered?`}
        onConfirm={handleRecoverHw}
        onCancel={() => setRecoverHw({ open: false, row: null })}
        confirmLabel="Recover"
        confirmColor="warning"
      />

      {/* Revoke Confirm */}
      <ConfirmDialog
        open={revokeSw.open}
        title="Revoke License"
        message={`Revoke this software license allocation?`}
        onConfirm={handleRevokeSw}
        onCancel={() => setRevokeSw({ open: false, row: null })}
        confirmLabel="Revoke"
        confirmColor="error"
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

export default AssetAllocation;
