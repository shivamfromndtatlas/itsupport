import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
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
  FormControlLabel,
  Checkbox,
  useMediaQuery,
  useTheme,
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

const CONDITION_CHOICES = ['Good', 'Fair', 'Poor'];
const SYSTEM_ASSET_ATTRIBUTE_NAMES = new Set(['asset id', 'asset type', 'status', 'condition']);

const EMPTY_ASSET = {
  asset_type: '',
  asset_id: '',
  serial_number: '',
  vendor: '',
  purchase_date: '',
  purchase_cost: '',
  status: 'available',
  attribute_values: { condition: 'Good' },
};

const EMPTY_LICENSE = {
  software_name: '',
  license_key: '',
  total_seats: '',
  vendor: '',
  purchase_date: '',
  expiry_date: '',
  license_type: '',
  notes: '',
};

function TabPanel({ value, index, children }) {
  return value === index ? <Box sx={{ pt: 2 }}>{children}</Box> : null;
}

function Assets() {
  const theme = useTheme();
  const fullScreen = useMediaQuery(theme.breakpoints.down('sm'));
  const navigate = useNavigate();
  const [tab, setTab] = useState(0);

  // Hardware
  const [assets, setAssets] = useState([]);
  const [assetLoading, setAssetLoading] = useState(false);
  const [assetDialog, setAssetDialog] = useState(false);
  const [editAsset, setEditAsset] = useState(null);
  const [assetForm, setAssetForm] = useState(EMPTY_ASSET);
  const [savingAsset, setSavingAsset] = useState(false);
  const [confirmAsset, setConfirmAsset] = useState({ open: false, row: null });
  const [bulkDialog, setBulkDialog] = useState(false);
  const [bulkAssetTypeIds, setBulkAssetTypeIds] = useState([]);
  const [bulkFile, setBulkFile] = useState(null);
  const [bulkBusy, setBulkBusy] = useState(false);

  // Software
  const [licenses, setLicenses] = useState([]);
  const [licenseLoading, setLicenseLoading] = useState(false);
  const [licenseDialog, setLicenseDialog] = useState(false);
  const [editLicense, setEditLicense] = useState(null);
  const [licenseForm, setLicenseForm] = useState(EMPTY_LICENSE);
  const [savingLicense, setSavingLicense] = useState(false);
  const [confirmLicense, setConfirmLicense] = useState({ open: false, row: null });

  const [assetTypes, setAssetTypes] = useState([]);
  const [assetAttributes, setAssetAttributes] = useState([]);
  const [licenseTypeChoices, setLicenseTypeChoices] = useState([]);
  const [hardwareAssetTypeFilter] = useState([]);
  const [softwareAssetTypeFilter, setSoftwareAssetTypeFilter] = useState([]);
  const [selectedHwTypeName, setSelectedHwTypeName] = useState('');

  const [snack, setSnack] = useState({ open: false, msg: '', severity: 'success' });
  const showSnack = (msg, severity = 'success') => setSnack({ open: true, msg, severity });

  const hardwareAssetTypeOptions = useMemo(
    () => assetTypes.filter((type) => type.asset_type === 'hardware'),
    [assetTypes]
  );
  const softwareAssetTypeOptions = useMemo(
    () => assetTypes.filter((type) => type.asset_type === 'software'),
    [assetTypes]
  );

  const filteredAssets = useMemo(() => {
    let rows = assets;
    if (hardwareAssetTypeFilter.length) {
      rows = rows.filter((row) => {
        const typeName = row.asset_type_name || row.asset_type || '';
        return hardwareAssetTypeFilter.includes(typeName);
      });
    }
    if (selectedHwTypeName) {
      rows = rows.filter((row) => {
        const typeName = row.asset_type_name || row.asset_type || '';
        return typeName === selectedHwTypeName;
      });
    }
    return rows;
  }, [assets, hardwareAssetTypeFilter, selectedHwTypeName]);

  const filteredLicenses = useMemo(() => {
    if (!softwareAssetTypeFilter.length) return licenses;
    return licenses.filter((row) => {
      const typeName = row.asset_type_name || row.asset_type || row.license_type || row.software_name || '';
      return softwareAssetTypeFilter.includes(typeName);
    });
  }, [licenses, softwareAssetTypeFilter]);

  const fetchChoices = useCallback(async () => {
    try {
      const [typesRes, licenseTypeRes] = await Promise.all([
        api.get('/inventory/asset-types/'),
        api.get('/inventory/form-choices/license-type-choices/'),
      ]);
      setAssetTypes(Array.isArray(typesRes.data) ? typesRes.data : typesRes.data.results || []);
      setLicenseTypeChoices(Array.isArray(licenseTypeRes.data) ? licenseTypeRes.data : []);
    } catch {
      showSnack('Failed to load form options.', 'error');
    }
  }, []);

  const fetchAssetAttributes = useCallback(async () => {
    try {
      const res = await api.get('/inventory/asset-attributes/');
      setAssetAttributes(Array.isArray(res.data) ? res.data : res.data.results || []);
    } catch {
      showSnack('Failed to load asset attributes.', 'error');
    }
  }, []);

  const fetchAssets = useCallback(async () => {
    setAssetLoading(true);
    try {
      const res = await api.get('/inventory/assets/?source=portal');
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
    fetchChoices();
    fetchAssetAttributes();
    fetchAssets();
    fetchLicenses();
  }, [fetchChoices, fetchAssetAttributes, fetchAssets, fetchLicenses]);

  const selectedAssetType = useMemo(
    () => assetTypes.find((type) => type.name === assetForm.asset_type),
    [assetForm.asset_type, assetTypes]
  );

  const configuredAssetAttributes = useMemo(() => {
    if (!selectedAssetType) return [];
    return assetAttributes.filter((attr) => {
      if (SYSTEM_ASSET_ATTRIBUTE_NAMES.has(attr.name.trim().toLowerCase())) {
        return false;
      }
      const linkedTypes = attr.asset_types || [];
      return (
        attr.is_common ||
        linkedTypes.length === 0 ||
        linkedTypes.map(String).includes(String(selectedAssetType.id))
      );
    });
  }, [assetAttributes, selectedAssetType]);

  const getAttributeKey = (attr) => String(attr.id);

  const getAttributeValue = (attr) => {
    const values = assetForm.attribute_values || {};
    return values[getAttributeKey(attr)] ?? values[attr.name] ?? '';
  };

  const updateAttributeValue = (attr, value) => {
    setAssetForm((prev) => ({
      ...prev,
      attribute_values: {
        ...(prev.attribute_values || {}),
        [getAttributeKey(attr)]: value,
      },
    }));
  };

  const getConditionValue = () => assetForm.attribute_values?.condition || 'Good';

  const updateConditionValue = (value) => {
    setAssetForm((prev) => ({
      ...prev,
      attribute_values: {
        ...(prev.attribute_values || {}),
        condition: value,
      },
    }));
  };

  const buildAssetPayload = () => {
    const payload = {
      asset_type: assetForm.asset_type,
      asset_id: assetForm.asset_id,
      serial_number: assetForm.serial_number,
      vendor: assetForm.vendor,
      status: assetForm.status || 'available',
      attribute_values: {
        ...(assetForm.attribute_values || {}),
        condition: getConditionValue(),
      },
    };

    if (assetForm.purchase_date) {
      payload.purchase_date = assetForm.purchase_date;
    }
    if (assetForm.purchase_cost !== '') {
      payload.purchase_cost = assetForm.purchase_cost;
    }

    return payload;
  };

  const getErrorMessage = (err) => {
    const data = err.response?.data;
    if (!data) return 'Save failed.';
    if (typeof data === 'string') return data;
    if (data.detail) return data.detail;
    const firstField = Object.keys(data)[0];
    const firstValue = data[firstField];
    const message = Array.isArray(firstValue) ? firstValue.join(' ') : firstValue;
    return firstField ? `${firstField}: ${message}` : 'Save failed.';
  };

  const renderAttributeField = (attr) => {
    const value = getAttributeValue(attr);

    if (attr.field_type === 'boolean') {
      return (
        <FormControlLabel
          control={
            <Checkbox
              checked={Boolean(value)}
              onChange={(e) => updateAttributeValue(attr, e.target.checked)}
            />
          }
          label={attr.name}
        />
      );
    }

    return (
      <TextField
        select={attr.field_type === 'select'}
        label={attr.name}
        type={attr.field_type === 'number' || attr.field_type === 'date' ? attr.field_type : 'text'}
        fullWidth
        value={value}
        onChange={(e) => updateAttributeValue(attr, e.target.value)}
        InputLabelProps={attr.field_type === 'date' ? { shrink: true } : undefined}
      >
        {attr.field_type === 'select' &&
          (attr.options || []).map((option) => (
            <MenuItem key={option} value={option}>
              {option}
            </MenuItem>
          ))}
      </TextField>
    );
  };

  // Asset handlers
  const openAddAsset = () => {
    setEditAsset(null);
    setAssetForm(EMPTY_ASSET);
    setAssetDialog(true);
  };

  const openBulkUpload = () => {
    setBulkAssetTypeIds([]);
    setBulkFile(null);
    setBulkDialog(true);
  };

  const openEditAsset = useCallback((row) => {
    setEditAsset(row);
    setAssetForm({
      asset_type: row.asset_type_name || row.asset_type || '',
      asset_id: row.asset_id || '',
      serial_number: row.serial_number || '',
      vendor: row.vendor || '',
      purchase_date: row.purchase_date || '',
      purchase_cost: row.purchase_cost || '',
      status: row.status || 'available',
      attribute_values: {
        condition: 'Good',
        ...(row.attribute_values || {}),
      },
    });
    setAssetDialog(true);
  }, []);

  const handleSaveAsset = async () => {
    setSavingAsset(true);
    try {
      const payload = buildAssetPayload();
      if (editAsset) {
        await api.patch(`/inventory/assets/${editAsset.id}/`, payload);
        showSnack('Asset updated.');
      } else {
        await api.post('/inventory/assets/', payload);
        showSnack('Asset added.');
      }
      setAssetDialog(false);
      fetchAssets();
    } catch (err) {
      showSnack(getErrorMessage(err), 'error');
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

  const downloadBulkTemplate = async () => {
    try {
      setBulkBusy(true);
      const params = new URLSearchParams();
      if (bulkAssetTypeIds.length) {
        params.set('asset_type_ids', bulkAssetTypeIds.join(','));
      }
      const res = await api.get(`/inventory/assets/bulk-template/${params.toString() ? `?${params.toString()}` : ''}`, {
        responseType: 'blob',
      });
      const blob = new Blob([res.data], {
        type: res.headers['content-type'] || 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      });
      const link = document.createElement('a');
      const url = window.URL.createObjectURL(blob);
      link.href = url;
      link.download = 'asset-bulk-upload-template.xlsx';
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      showSnack('Template downloaded.');
    } catch (err) {
      showSnack(err.response?.data?.detail || 'Template download failed.', 'error');
    } finally {
      setBulkBusy(false);
    }
  };

  const handleBulkUpload = async () => {
    if (!bulkFile) {
      showSnack('Choose an Excel file first.', 'error');
      return;
    }
    try {
      setBulkBusy(true);
      const formData = new FormData();
      formData.append('file', bulkFile);
      const res = await api.post('/inventory/assets/bulk-upload/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      showSnack(`Bulk upload complete: ${res.data.created || 0} created, ${res.data.updated || 0} updated.`);
      setBulkDialog(false);
      setBulkFile(null);
      fetchAssets();
    } catch (err) {
      const errors = err.response?.data?.errors;
      showSnack(
        errors?.length ? errors[0] : err.response?.data?.detail || 'Bulk upload failed.',
        'error'
      );
    } finally {
      setBulkBusy(false);
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
      license_type: row.license_type || '',
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

  const assetColumns = useMemo(() => [
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
    {
      field: 'actions',
      headerName: 'Actions',
      width: 100,
      sortable: false,
      renderCell: ({ row }) => (
        <Box>
          <Tooltip title="Edit">
            <IconButton size="small" onClick={(e) => { e.stopPropagation(); openEditAsset(row); }}>
              <EditIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Delete">
            <IconButton size="small" color="error" onClick={(e) => { e.stopPropagation(); setConfirmAsset({ open: true, row }); }}>
              <DeleteIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      ),
    },
  ], [openEditAsset]);

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
            <Box sx={{ display: 'flex', gap: 2 }}>
              <Box sx={{ width: 220, borderRight: 1, borderColor: 'divider', pr: 1 }}>
                <Tabs
                  orientation="vertical"
                  value={selectedHwTypeName}
                  onChange={(_, v) => setSelectedHwTypeName(v)}
                  sx={{ height: '100%' }}
                >
                  <Tab value="" label="All Types" />
                  {hardwareAssetTypeOptions.map((type) => (
                    <Tab key={type.id} value={type.name} label={type.name} />
                  ))}
                </Tabs>
              </Box>
              <Box sx={{ flex: 1 }}>
                <DataTable
                  rows={useMemo(() => {
                    // Map attribute values into fields for dynamic columns
                    const attrs = assetAttributes || [];
                    const selectedType = assetTypes.find((t) => t.name === selectedHwTypeName);
                    const relevantAttrs = selectedType
                      ? attrs.filter((attr) => {
                          if (SYSTEM_ASSET_ATTRIBUTE_NAMES.has(attr.name.trim().toLowerCase())) return false;
                          const linkedTypes = attr.asset_types || [];
                          return attr.is_common || linkedTypes.length === 0 || linkedTypes.map(String).includes(String(selectedType.id));
                        })
                      : [];

                    return filteredAssets.map((row) => {
                      const values = row.asset_detail?.attribute_values_with_names || row.asset_detail?.attribute_values || row.attribute_values || {};
                      const mapped = { ...row };
                      relevantAttrs.forEach((attr) => {
                        const key = `attr_${attr.id}`;
                        mapped[key] = values[String(attr.id)] ?? values[attr.name] ?? values[attr.name.toLowerCase()] ?? '';
                      });
                      return mapped;
                    });
                  }, [filteredAssets, assetAttributes, assetTypes, selectedHwTypeName])}
                  columns={useMemo(() => {
                    // Build columns: base + dynamic attribute columns when a type is selected
                    const base = assetColumns;
                    if (!selectedHwTypeName) return base;
                    const selectedType = assetTypes.find((t) => t.name === selectedHwTypeName);
                    const attrs = assetAttributes || [];
                    const relevantAttrs = attrs.filter((attr) => {
                      if (SYSTEM_ASSET_ATTRIBUTE_NAMES.has(attr.name.trim().toLowerCase())) return false;
                      const linkedTypes = attr.asset_types || [];
                      return (
                        attr.is_common ||
                        linkedTypes.length === 0 ||
                        linkedTypes.map(String).includes(String(selectedType?.id))
                      );
                    });
                    const attrCols = relevantAttrs.map((attr) => ({
                      field: `attr_${attr.id}`,
                      headerName: attr.name,
                      flex: 1,
                      minWidth: 120,
                      renderCell: ({ value }) => value ?? '--',
                    }));
                    return [...base.slice(0, base.length - 1), ...attrCols, base[base.length - 1]];
                  }, [assetColumns, assetAttributes, assetTypes, selectedHwTypeName])}
                  loading={assetLoading}
                  onRowClick={({ row }) => navigate(`/inventory/assets/${row.id}`)}
                  onAdd={openAddAsset}
                  addLabel="Add Asset"
                  searchable
                  toolbar={
                    <Button variant="outlined" onClick={openBulkUpload}>
                      Bulk Upload
                    </Button>
                  }
                />
              </Box>
            </Box>
          </TabPanel>
          <TabPanel value={tab} index={1}>
            <DataTable
              rows={filteredLicenses}
              columns={licenseColumns}
              loading={licenseLoading}
              onAdd={openAddLicense}
              addLabel="Add License"
              searchable
              toolbar={
                <TextField
                  select
                  size="small"
                  label="Software Asset Type"
                  value={softwareAssetTypeFilter}
                  onChange={(e) => setSoftwareAssetTypeFilter(e.target.value)}
                  SelectProps={{ multiple: true, renderValue: (selected) => (selected.length ? selected.join(', ') : 'All asset types') }}
                  sx={{ minWidth: 240, maxWidth: 420 }}
                >
                  {softwareAssetTypeOptions.map((type) => (
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

      <Dialog open={bulkDialog} onClose={() => setBulkDialog(false)} maxWidth="sm" fullWidth fullScreen={fullScreen}>
        <DialogTitle>Bulk Upload Assets</DialogTitle>
        <DialogContent sx={{ pt: '12px !important' }}>
          <Grid container spacing={2}>
            <Grid item xs={12}>
              <TextField
                select
                label="Asset Types for Template"
                fullWidth
                value={bulkAssetTypeIds}
                onChange={(e) => setBulkAssetTypeIds(typeof e.target.value === 'string' ? e.target.value.split(',') : e.target.value)}
                SelectProps={{
                  multiple: true,
                  renderValue: (selected) => {
                    const names = assetTypes
                      .filter((type) => selected.includes(String(type.id)))
                      .map((type) => type.name);
                    return names.length ? names.join(', ') : 'All asset types';
                  },
                }}
                helperText="Leave blank to generate a template for all asset types."
              >
                {assetTypes.map((type) => (
                  <MenuItem key={type.id} value={String(type.id)}>
                    {type.name}
                  </MenuItem>
                ))}
              </TextField>
            </Grid>
            <Grid item xs={12}>
              <Button variant="outlined" onClick={downloadBulkTemplate} disabled={bulkBusy} fullWidth>
                Download Excel Template
              </Button>
            </Grid>
            <Grid item xs={12}>
              <Button variant="outlined" component="label" fullWidth>
                {bulkFile ? bulkFile.name : 'Choose Filled Excel File'}
                <input
                  hidden
                  type="file"
                  accept=".xlsx"
                  onChange={(e) => setBulkFile(e.target.files?.[0] || null)}
                />
              </Button>
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setBulkDialog(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleBulkUpload} disabled={bulkBusy}>
            {bulkBusy ? 'Uploading...' : 'Upload Assets'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Add/Edit Asset Dialog */}
      <Dialog open={assetDialog} onClose={() => setAssetDialog(false)} maxWidth="sm" fullWidth fullScreen={fullScreen}>
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
                {hardwareAssetTypeOptions.map((t) => (
                  <MenuItem key={t.id} value={t.name}>
                    {t.name}
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
            {assetForm.asset_type && configuredAssetAttributes.length === 0 && (
              <Grid item xs={12}>
                <Typography variant="body2" color="text.secondary">
                  No attributes are configured for this asset type.
                </Typography>
              </Grid>
            )}
            {configuredAssetAttributes.map((attr) => (
              <Grid item xs={12} sm={attr.field_type === 'boolean' ? 12 : 6} key={attr.id}>
                {renderAttributeField(attr)}
              </Grid>
            ))}
            <Grid item xs={12} sm={6}>
              <TextField
                select
                label="Condition"
                fullWidth
                value={getConditionValue()}
                onChange={(e) => updateConditionValue(e.target.value)}
              >
                {CONDITION_CHOICES.map((condition) => (
                  <MenuItem key={condition} value={condition}>
                    {condition}
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
      <Dialog open={licenseDialog} onClose={() => setLicenseDialog(false)} maxWidth="sm" fullWidth fullScreen={fullScreen}>
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
                {licenseTypeChoices.map((t) => (
                  <MenuItem key={t.value} value={t.value}>
                    {t.label}
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
