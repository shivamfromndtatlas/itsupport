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
  Stack,
  Switch,
  Select,
  InputLabel,
  FormControl,
  FormHelperText,
  OutlinedInput,
  Divider,
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import DataTable from '../../components/common/DataTable';
import ConfirmDialog from '../../components/common/ConfirmDialog';
import api from '../../api/axios';

const ASSET_CATEGORY_CHOICES = [
  { value: 'hardware', label: 'Hardware' },
  { value: 'software', label: 'Software' },
];

const FIELD_TYPE_CHOICES = [
  { value: 'text', label: 'Text' },
  { value: 'number', label: 'Number' },
  { value: 'date', label: 'Date' },
  { value: 'boolean', label: 'Boolean' },
  { value: 'select', label: 'Select (dropdown)' },
];

const EMPTY_TYPE = { name: '', asset_type: '', description: '' };
const EMPTY_ATTR = { name: '', field_type: '', options: [], asset_types: [], is_common: false };

function TabPanel({ value, index, children }) {
  return value === index ? <Box sx={{ pt: 2 }}>{children}</Box> : null;
}

function InventoryConfig() {
  const [tab, setTab] = useState(0);

  // Asset Types state
  const [assetTypes, setAssetTypes] = useState([]);
  const [typeLoading, setTypeLoading] = useState(false);
  const [typeDialog, setTypeDialog] = useState(false);
  const [editType, setEditType] = useState(null);
  const [typeForm, setTypeForm] = useState(EMPTY_TYPE);
  const [savingType, setSavingType] = useState(false);
  const [confirmType, setConfirmType] = useState({ open: false, row: null });

  // Asset Attributes state
  const [attributes, setAttributes] = useState([]);
  const [attrLoading, setAttrLoading] = useState(false);
  const [attrDialog, setAttrDialog] = useState(false);
  const [editAttr, setEditAttr] = useState(null);
  const [attrForm, setAttrForm] = useState(EMPTY_ATTR);
  const [savingAttr, setSavingAttr] = useState(false);
  const [confirmAttr, setConfirmAttr] = useState({ open: false, row: null });
  const [optionsInput, setOptionsInput] = useState('');

  const [snack, setSnack] = useState({ open: false, msg: '', severity: 'success' });
  const showSnack = (msg, severity = 'success') => setSnack({ open: true, msg, severity });

  const fetchAssetTypes = useCallback(async () => {
    setTypeLoading(true);
    try {
      const res = await api.get('/inventory/asset-types/');
      const data = Array.isArray(res.data) ? res.data : res.data.results || [];
      setAssetTypes(data.map((t) => ({ ...t, id: t.id })));
    } catch {
      showSnack('Failed to load asset types.', 'error');
    } finally {
      setTypeLoading(false);
    }
  }, []);

  const fetchAttributes = useCallback(async () => {
    setAttrLoading(true);
    try {
      const res = await api.get('/inventory/asset-attributes/');
      const data = Array.isArray(res.data) ? res.data : res.data.results || [];
      setAttributes(data.map((a) => ({ ...a, id: a.id })));
    } catch {
      showSnack('Failed to load asset attributes.', 'error');
    } finally {
      setAttrLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAssetTypes();
    fetchAttributes();
  }, [fetchAssetTypes, fetchAttributes]);

  // ── Asset Type handlers ──────────────────────────────────────────────────

  const openAddType = () => {
    setEditType(null);
    setTypeForm(EMPTY_TYPE);
    setTypeDialog(true);
  };

  const openEditType = (row) => {
    setEditType(row);
    setTypeForm({ name: row.name, asset_type: row.asset_type, description: row.description || '' });
    setTypeDialog(true);
  };

  const handleSaveType = async () => {
    if (!typeForm.name.trim() || !typeForm.asset_type) {
      showSnack('Name and category are required.', 'error');
      return;
    }
    setSavingType(true);
    try {
      if (editType) {
        await api.patch(`/inventory/asset-types/${editType.id}/`, typeForm);
        showSnack('Asset type updated.');
      } else {
        await api.post('/inventory/asset-types/', typeForm);
        showSnack('Asset type created.');
      }
      setTypeDialog(false);
      fetchAssetTypes();
    } catch (err) {
      showSnack(err.response?.data?.detail || 'Save failed.', 'error');
    } finally {
      setSavingType(false);
    }
  };

  const handleDeleteType = async () => {
    try {
      await api.delete(`/inventory/asset-types/${confirmType.row.id}/`);
      showSnack('Asset type deleted.');
      fetchAssetTypes();
    } catch {
      showSnack('Delete failed. It may be in use by existing assets.', 'error');
    } finally {
      setConfirmType({ open: false, row: null });
    }
  };

  // ── Asset Attribute handlers ─────────────────────────────────────────────

  const openAddAttr = () => {
    setEditAttr(null);
    setAttrForm(EMPTY_ATTR);
    setOptionsInput('');
    setAttrDialog(true);
  };

  const openEditAttr = (row) => {
    setEditAttr(row);
    setAttrForm({
      name: row.name,
      field_type: row.field_type,
      options: row.options || [],
      asset_types: row.asset_types || [],
      is_common: row.is_common || false,
    });
    setOptionsInput((row.options || []).join(', '));
    setAttrDialog(true);
  };

  const handleSaveAttr = async () => {
    if (!attrForm.name.trim() || !attrForm.field_type) {
      showSnack('Name and field type are required.', 'error');
      return;
    }
    const payload = {
      ...attrForm,
      options:
        attrForm.field_type === 'select'
          ? optionsInput.split(',').map((s) => s.trim()).filter(Boolean)
          : [],
    };
    setSavingAttr(true);
    try {
      if (editAttr) {
        await api.patch(`/inventory/asset-attributes/${editAttr.id}/`, payload);
        showSnack('Attribute updated.');
      } else {
        await api.post('/inventory/asset-attributes/', payload);
        showSnack('Attribute created.');
      }
      setAttrDialog(false);
      fetchAttributes();
    } catch (err) {
      showSnack(err.response?.data?.detail || 'Save failed.', 'error');
    } finally {
      setSavingAttr(false);
    }
  };

  const handleDeleteAttr = async () => {
    try {
      await api.delete(`/inventory/asset-attributes/${confirmAttr.row.id}/`);
      showSnack('Attribute deleted.');
      fetchAttributes();
    } catch {
      showSnack('Delete failed.', 'error');
    } finally {
      setConfirmAttr({ open: false, row: null });
    }
  };

  // ── Column definitions ───────────────────────────────────────────────────

  const typeColumns = [
    { field: 'name', headerName: 'Name', flex: 1, minWidth: 150 },
    {
      field: 'asset_type',
      headerName: 'Category',
      width: 130,
      renderCell: ({ value }) => (
        <Chip
          label={value === 'hardware' ? 'Hardware' : 'Software'}
          color={value === 'hardware' ? 'primary' : 'secondary'}
          size="small"
          sx={{ textTransform: 'capitalize' }}
        />
      ),
    },
    { field: 'description', headerName: 'Description', flex: 2 },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 100,
      sortable: false,
      renderCell: ({ row }) => (
        <Box>
          <Tooltip title="Edit">
            <IconButton size="small" onClick={() => openEditType(row)}>
              <EditIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Delete">
            <IconButton size="small" color="error" onClick={() => setConfirmType({ open: true, row })}>
              <DeleteIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      ),
    },
  ];

  const attrColumns = [
    { field: 'name', headerName: 'Name', flex: 1, minWidth: 150 },
    {
      field: 'field_type',
      headerName: 'Field Type',
      width: 150,
      renderCell: ({ value }) => (
        <Chip label={value} size="small" variant="outlined" sx={{ textTransform: 'capitalize' }} />
      ),
    },
    {
      field: 'is_common',
      headerName: 'Common',
      width: 110,
      renderCell: ({ value }) => (
        <Chip label={value ? 'Yes' : 'No'} color={value ? 'success' : 'default'} size="small" />
      ),
    },
    {
      field: 'asset_types',
      headerName: 'Linked Asset Types',
      flex: 1,
      minWidth: 180,
      renderCell: ({ value }) => {
        const linkedIds = value || [];
        const names = linkedIds
          .map((id) => assetTypes.find((t) => t.id === id)?.name)
          .filter(Boolean);
        if (!names.length) return <Typography variant="body2" color="text.secondary">All / None</Typography>;
        return (
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
            {names.map((n) => <Chip key={n} label={n} size="small" />)}
          </Box>
        );
      },
    },
    {
      field: 'options',
      headerName: 'Options',
      flex: 1,
      renderCell: ({ row, value }) => {
        if (row.field_type !== 'select' || !value?.length) return '—';
        return (
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
            {value.map((o) => <Chip key={o} label={o} size="small" variant="outlined" />)}
          </Box>
        );
      },
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 100,
      sortable: false,
      renderCell: ({ row }) => (
        <Box>
          <Tooltip title="Edit">
            <IconButton size="small" onClick={() => openEditAttr(row)}>
              <EditIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Delete">
            <IconButton size="small" color="error" onClick={() => setConfirmAttr({ open: true, row })}>
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
        Inventory Configuration
      </Typography>
      <Paper sx={{ borderRadius: 2 }}>
        <Tabs
          value={tab}
          onChange={(_, v) => setTab(v)}
          sx={{ borderBottom: 1, borderColor: 'divider', px: 2 }}
        >
          <Tab label="Asset Types" />
          <Tab label="Asset Attributes" />
        </Tabs>
        <Box sx={{ p: 2 }}>
          <TabPanel value={tab} index={0}>
            <DataTable
              rows={assetTypes}
              columns={typeColumns}
              loading={typeLoading}
              onAdd={openAddType}
              addLabel="Add Asset Type"
              searchable
            />
          </TabPanel>
          <TabPanel value={tab} index={1}>
            <DataTable
              rows={attributes}
              columns={attrColumns}
              loading={attrLoading}
              onAdd={openAddAttr}
              addLabel="Add Attribute"
              searchable
            />
          </TabPanel>
        </Box>
      </Paper>

      {/* Add/Edit Asset Type Dialog */}
      <Dialog open={typeDialog} onClose={() => setTypeDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ pb: 1 }}>{editType ? 'Edit Asset Type' : 'Add Asset Type'}</DialogTitle>
        <Divider />
        <DialogContent sx={{ pt: 2.5 }}>
          <Stack spacing={2.5}>
            <Grid container spacing={2}>
              <Grid item xs={12} sm={7}>
                <TextField
                  label="Name"
                  fullWidth
                  value={typeForm.name}
                  onChange={(e) => setTypeForm({ ...typeForm, name: e.target.value })}
                  placeholder="e.g. Laptop, Monitor, Server"
                />
              </Grid>
              <Grid item xs={12} sm={5}>
                <TextField
                  select
                  label="Category"
                  fullWidth
                  value={typeForm.asset_type}
                  onChange={(e) => setTypeForm({ ...typeForm, asset_type: e.target.value })}
                >
                  {ASSET_CATEGORY_CHOICES.map((c) => (
                    <MenuItem key={c.value} value={c.value}>
                      {c.label}
                    </MenuItem>
                  ))}
                </TextField>
              </Grid>
            </Grid>
            <TextField
              label="Description"
              fullWidth
              multiline
              rows={2}
              value={typeForm.description}
              onChange={(e) => setTypeForm({ ...typeForm, description: e.target.value })}
              placeholder="Optional description of this asset type"
            />
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setTypeDialog(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleSaveType} disabled={savingType}>
            {savingType ? 'Saving...' : 'Save'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Add/Edit Asset Attribute Dialog */}
      <Dialog open={attrDialog} onClose={() => setAttrDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ pb: 1 }}>{editAttr ? 'Edit Attribute' : 'Add Attribute'}</DialogTitle>
        <Divider />
        <DialogContent sx={{ pt: 2.5 }}>
          <Stack spacing={2.5}>
            <Grid container spacing={2}>
              <Grid item xs={12} sm={7}>
                <TextField
                  label="Attribute Name"
                  fullWidth
                  value={attrForm.name}
                  onChange={(e) => setAttrForm({ ...attrForm, name: e.target.value })}
                  placeholder="e.g. RAM Size, Color, Warranty"
                />
              </Grid>
              <Grid item xs={12} sm={5}>
                <TextField
                  select
                  label="Field Type"
                  fullWidth
                  value={attrForm.field_type}
                  onChange={(e) => setAttrForm({ ...attrForm, field_type: e.target.value })}
                >
                  {FIELD_TYPE_CHOICES.map((c) => (
                    <MenuItem key={c.value} value={c.value}>
                      {c.label}
                    </MenuItem>
                  ))}
                </TextField>
              </Grid>
            </Grid>

            {attrForm.field_type === 'select' && (
              <TextField
                label="Dropdown Options"
                fullWidth
                value={optionsInput}
                onChange={(e) => setOptionsInput(e.target.value)}
                placeholder="e.g. Option A, Option B, Option C"
                helperText="Separate each option with a comma"
              />
            )}

            <FormControl fullWidth>
              <InputLabel>Linked Asset Types</InputLabel>
              <Select
                multiple
                value={attrForm.asset_types}
                onChange={(e) => setAttrForm({ ...attrForm, asset_types: e.target.value })}
                input={<OutlinedInput label="Linked Asset Types" />}
                renderValue={(selected) => (
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, py: 0.5 }}>
                    {selected.map((id) => {
                      const t = assetTypes.find((x) => x.id === id);
                      return t ? <Chip key={id} label={t.name} size="small" /> : null;
                    })}
                  </Box>
                )}
              >
                {assetTypes.map((t) => (
                  <MenuItem key={t.id} value={t.id}>
                    {t.name}
                  </MenuItem>
                ))}
              </Select>
              <FormHelperText>Leave empty to apply to all asset types</FormHelperText>
            </FormControl>

            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                px: 2,
                py: 1.5,
                border: 1,
                borderColor: 'divider',
                borderRadius: 1,
              }}
            >
              <Box>
                <Typography variant="body2" fontWeight={500}>
                  Common to all asset types
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  This attribute will appear for every asset type
                </Typography>
              </Box>
              <Switch
                checked={attrForm.is_common}
                onChange={(e) => setAttrForm({ ...attrForm, is_common: e.target.checked })}
              />
            </Box>
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setAttrDialog(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleSaveAttr} disabled={savingAttr}>
            {savingAttr ? 'Saving...' : 'Save'}
          </Button>
        </DialogActions>
      </Dialog>

      <ConfirmDialog
        open={confirmType.open}
        title="Delete Asset Type"
        message={`Delete asset type "${confirmType.row?.name}"? This cannot be undone if assets of this type exist.`}
        onConfirm={handleDeleteType}
        onCancel={() => setConfirmType({ open: false, row: null })}
        confirmLabel="Delete"
      />

      <ConfirmDialog
        open={confirmAttr.open}
        title="Delete Attribute"
        message={`Delete attribute "${confirmAttr.row?.name}"?`}
        onConfirm={handleDeleteAttr}
        onCancel={() => setConfirmAttr({ open: false, row: null })}
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

export default InventoryConfig;
