import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Grid,
  Paper,
  Typography,
  TextField,
  Button,
  List,
  ListItemButton,
  Divider,
  Chip,
  Stepper,
  Step,
  StepLabel,
  StepContent,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  MenuItem,
  IconButton,
  Snackbar,
  Alert,
  Checkbox,
  FormControlLabel,
  InputAdornment,
  Avatar,
  Tooltip,
  LinearProgress,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import SearchIcon from '@mui/icons-material/Search';
import MenuBookIcon from '@mui/icons-material/MenuBook';
import TouchAppIcon from '@mui/icons-material/TouchApp';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import HowToRegIcon from '@mui/icons-material/HowToReg';
import ChecklistIcon from '@mui/icons-material/Checklist';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import FormatListNumberedIcon from '@mui/icons-material/FormatListNumbered';
import api from '../../api/axios';
import { useAuth } from '../../context/AuthContext';

const STEP_TYPES = ['manual', 'automated', 'approval', 'checklist'];

const STEP_TYPE_META = {
  manual: { color: 'primary', icon: <TouchAppIcon fontSize="small" />, label: 'Manual' },
  automated: { color: 'success', icon: <AutoFixHighIcon fontSize="small" />, label: 'Automated' },
  approval: { color: 'warning', icon: <HowToRegIcon fontSize="small" />, label: 'Approval' },
  checklist: { color: 'secondary', icon: <ChecklistIcon fontSize="small" />, label: 'Checklist' },
};

const STEP_TYPE_BG = {
  manual: '#e3f2fd',
  automated: '#e8f5e9',
  approval: '#fff8e1',
  checklist: '#f3e5f5',
};

const EMPTY_STEP = { title: '', description: '', type: 'manual', checklist_items: [] };
const EMPTY_SOP_FORM = { name: '', category: '', description: '', steps: [{ ...EMPTY_STEP }] };

function SOPManagement() {
  const { hasRole } = useAuth();
  const theme = useTheme();
  const fullScreen = useMediaQuery(theme.breakpoints.down('sm'));
  const canCreate = hasRole('super_admin', 'it_specialist');

  const [sops, setSops] = useState([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [sopForm, setSopForm] = useState(EMPTY_SOP_FORM);
  const [saving, setSaving] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [execStep, setExecStep] = useState(0);
  const [execOpen, setExecOpen] = useState(false);
  const [snack, setSnack] = useState({ open: false, msg: '', severity: 'success' });

  const showSnack = (msg, severity = 'success') =>
    setSnack({ open: true, msg, severity });

  const fetchSOPs = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/sop/');
      const data = Array.isArray(res.data) ? res.data : res.data.results || [];
      setSops(data);
    } catch {
      showSnack('Failed to load SOPs.', 'error');
    } finally {
      setLoading(false);
    }
  }, []);

  const handleSelectSOP = useCallback(async (sop) => {
    // Optimistically show the SOP with whatever data we have
    setSelected(sop);
    setLoadingDetail(true);
    try {
      const res = await api.get(`/sop/${sop.id}/`);
      setSelected(res.data);
    } catch {
      // Keep the summary data if detail fetch fails
    } finally {
      setLoadingDetail(false);
    }
  }, []);

  useEffect(() => { fetchSOPs(); }, [fetchSOPs]);

  const filteredSOPs = sops.filter(
    (s) =>
      s.name?.toLowerCase().includes(search.toLowerCase()) ||
      s.category?.toLowerCase().includes(search.toLowerCase())
  );

  const grouped = filteredSOPs.reduce((acc, sop) => {
    const cat = sop.category || 'General';
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(sop);
    return acc;
  }, {});

  const addStep = () =>
    setSopForm((p) => ({ ...p, steps: [...p.steps, { ...EMPTY_STEP, checklist_items: [] }] }));

  const removeStep = (idx) =>
    setSopForm((p) => ({ ...p, steps: p.steps.filter((_, i) => i !== idx) }));

  const updateStep = (idx, field, value) =>
    setSopForm((p) => ({
      ...p,
      steps: p.steps.map((s, i) => (i === idx ? { ...s, [field]: value } : s)),
    }));

  const addChecklistItem = (stepIdx) =>
    setSopForm((p) => ({
      ...p,
      steps: p.steps.map((s, i) =>
        i === stepIdx ? { ...s, checklist_items: [...(s.checklist_items || []), ''] } : s
      ),
    }));

  const updateChecklistItem = (stepIdx, itemIdx, value) =>
    setSopForm((p) => ({
      ...p,
      steps: p.steps.map((s, i) =>
        i === stepIdx
          ? { ...s, checklist_items: s.checklist_items.map((c, ci) => (ci === itemIdx ? value : c)) }
          : s
      ),
    }));

  const removeChecklistItem = (stepIdx, itemIdx) =>
    setSopForm((p) => ({
      ...p,
      steps: p.steps.map((s, i) =>
        i === stepIdx
          ? { ...s, checklist_items: s.checklist_items.filter((_, ci) => ci !== itemIdx) }
          : s
      ),
    }));

  const handleCreateSOP = async () => {
    setSaving(true);
    try {
      await api.post('/sop/', sopForm);
      showSnack('SOP created successfully.');
      setCreateOpen(false);
      setSopForm(EMPTY_SOP_FORM);
      fetchSOPs();
    } catch (err) {
      showSnack(err.response?.data?.detail || 'Failed to create SOP.', 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleExecute = async () => {
    if (!selected) return;
    setExecuting(true);
    try {
      await api.post(`/sop/${selected.id}/execute/`, {});
      setExecStep(0);
      setExecOpen(true);
    } catch {
      showSnack('Failed to start execution.', 'error');
    } finally {
      setExecuting(false);
    }
  };

  const steps = selected?.steps || [];
  const execProgress = steps.length > 0 ? Math.round((execStep / steps.length) * 100) : 0;

  return (
    <Box sx={{ height: 'calc(100vh - 100px)', display: 'flex', flexDirection: 'column' }}>
      {/* Page Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <Avatar sx={{ bgcolor: 'primary.main', width: 38, height: 38 }}>
            <MenuBookIcon fontSize="small" />
          </Avatar>
          <Box>
            <Typography variant="h6" fontWeight={700} lineHeight={1.2}>
              SOP Management
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {sops.length} procedure{sops.length !== 1 ? 's' : ''} across {Object.keys(grouped).length} categor{Object.keys(grouped).length !== 1 ? 'ies' : 'y'}
            </Typography>
          </Box>
        </Box>
        {canCreate && (
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => { setSopForm(EMPTY_SOP_FORM); setCreateOpen(true); }}
            sx={{ borderRadius: 2, fontWeight: 600 }}
          >
            New SOP
          </Button>
        )}
      </Box>

      <Grid container spacing={2} sx={{ flex: 1, minHeight: 0, gridAutoRows: { xs: 'auto', md: '1fr' } }}>
        {/* ── Left Panel ── */}
        <Grid item xs={12} md={4} sx={{ height: { md: '100%' }, display: 'flex', flexDirection: 'column' }}>
          <Paper sx={{ flex: 1, display: 'flex', flexDirection: 'column', borderRadius: 2, overflow: 'hidden' }}>
            {/* Search */}
            <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
              <TextField
                size="small"
                placeholder="Search SOPs..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                fullWidth
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchIcon fontSize="small" color="action" />
                    </InputAdornment>
                  ),
                  sx: { borderRadius: 2, bgcolor: 'grey.50' },
                }}
              />
            </Box>

            {/* SOP List */}
            <Box sx={{ flex: 1, overflow: 'auto' }}>
              {loading ? (
                <Box sx={{ p: 0 }}>
                  <LinearProgress />
                  <Typography sx={{ p: 3, color: 'text.secondary', textAlign: 'center' }}>
                    Loading SOPs...
                  </Typography>
                </Box>
              ) : Object.keys(grouped).length === 0 ? (
                <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 1.5, py: 6 }}>
                  <FolderOpenIcon sx={{ fontSize: 48, color: 'grey.300' }} />
                  <Typography color="text.secondary" fontWeight={500}>
                    {search ? 'No SOPs match your search' : 'No SOPs yet'}
                  </Typography>
                  {canCreate && !search && (
                    <Button
                      size="small"
                      variant="outlined"
                      startIcon={<AddIcon />}
                      onClick={() => { setSopForm(EMPTY_SOP_FORM); setCreateOpen(true); }}
                      sx={{ borderRadius: 2 }}
                    >
                      Create your first SOP
                    </Button>
                  )}
                </Box>
              ) : (
                Object.entries(grouped).map(([category, items]) => (
                  <Box key={category}>
                    {/* Category Header */}
                    <Box sx={{ px: 2, pt: 2, pb: 0.5, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <Typography
                        variant="caption"
                        fontWeight={700}
                        sx={{ color: 'text.secondary', textTransform: 'uppercase', letterSpacing: 1 }}
                      >
                        {category}
                      </Typography>
                      <Chip label={items.length} size="small" sx={{ height: 18, fontSize: 11, bgcolor: 'grey.100' }} />
                    </Box>

                    <List dense disablePadding sx={{ px: 1, pb: 1 }}>
                      {items.map((sop) => {
                        const isActive = selected?.id === sop.id;
                        return (
                          <ListItemButton
                            key={sop.id}
                            selected={isActive}
                            onClick={() => handleSelectSOP(sop)}
                            sx={{
                              borderRadius: 1.5,
                              mb: 0.5,
                              px: 1.5,
                              py: 1,
                              '&.Mui-selected': {
                                bgcolor: 'primary.main',
                                color: 'white',
                                '&:hover': { bgcolor: 'primary.dark' },
                              },
                            }}
                          >
                            <Box sx={{ width: '100%' }}>
                              <Typography
                                variant="body2"
                                fontWeight={isActive ? 600 : 500}
                                sx={{ color: isActive ? 'white' : 'text.primary', mb: 0.25 }}
                              >
                                {sop.name}
                              </Typography>
                              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
                                <FormatListNumberedIcon
                                  sx={{ fontSize: 12, color: isActive ? 'rgba(255,255,255,0.7)' : 'text.disabled' }}
                                />
                                <Typography
                                  variant="caption"
                                  sx={{ color: isActive ? 'rgba(255,255,255,0.75)' : 'text.secondary' }}
                                >
                                  {(sop.steps || []).length} step{(sop.steps || []).length !== 1 ? 's' : ''}
                                </Typography>
                              </Box>
                            </Box>
                          </ListItemButton>
                        );
                      })}
                    </List>
                    <Divider />
                  </Box>
                ))
              )}
            </Box>
          </Paper>
        </Grid>

        {/* ── Right Panel ── */}
        <Grid item xs={12} md={8} sx={{ height: { md: '100%' }, display: 'flex', flexDirection: 'column' }}>
          <Paper sx={{ flex: 1, overflow: 'auto', borderRadius: 2, minHeight: 300 }}>
            {loadingDetail ? (
              <Box sx={{ p: 3 }}>
                <LinearProgress sx={{ borderRadius: 2, mb: 3 }} />
                {[1, 2, 3].map((i) => (
                  <Box key={i} sx={{ mb: 2 }}>
                    <Box sx={{ height: 16, bgcolor: 'grey.100', borderRadius: 1, mb: 1, width: `${60 + i * 10}%` }} />
                    <Box sx={{ height: 12, bgcolor: 'grey.50', borderRadius: 1, width: '80%' }} />
                  </Box>
                ))}
              </Box>
            ) : !selected ? (
              <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', py: 12, gap: 2 }}>
                <MenuBookIcon sx={{ fontSize: 64, color: 'grey.200' }} />
                <Typography variant="h6" color="text.disabled" fontWeight={500}>
                  Select an SOP to view details
                </Typography>
                <Typography variant="body2" color="text.disabled">
                  Choose a procedure from the list on the left
                </Typography>
              </Box>
            ) : (
              <Box sx={{ p: 3 }}>
                {/* SOP Header */}
                <Box
                  sx={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'flex-start',
                    mb: 3,
                    pb: 3,
                    borderBottom: 1,
                    borderColor: 'divider',
                  }}
                >
                  <Box sx={{ flex: 1 }}>
                    <Typography variant="h5" fontWeight={700} sx={{ mb: 1 }}>
                      {selected.name}
                    </Typography>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: selected.description ? 1.5 : 0 }}>
                      <Chip
                        label={selected.category || 'General'}
                        size="small"
                        color="primary"
                        variant="outlined"
                        sx={{ fontWeight: 600 }}
                      />
                      <Chip
                        icon={<FormatListNumberedIcon />}
                        label={`${steps.length} steps`}
                        size="small"
                        variant="outlined"
                        sx={{ fontWeight: 500 }}
                      />
                      {Object.entries(
                        steps.reduce((acc, s) => {
                          acc[s.type] = (acc[s.type] || 0) + 1;
                          return acc;
                        }, {})
                      ).map(([type, count]) => (
                        <Chip
                          key={type}
                          icon={STEP_TYPE_META[type]?.icon}
                          label={`${count} ${STEP_TYPE_META[type]?.label || type}`}
                          size="small"
                          color={STEP_TYPE_META[type]?.color || 'default'}
                          variant="outlined"
                          sx={{ fontWeight: 500 }}
                        />
                      ))}
                    </Box>
                    {selected.description && (
                      <Typography variant="body2" color="text.secondary" sx={{ mt: 1, lineHeight: 1.6 }}>
                        {selected.description}
                      </Typography>
                    )}
                  </Box>
                  {canCreate && (
                    <Tooltip title="Run this SOP step by step">
                      <Button
                        variant="contained"
                        startIcon={<PlayArrowIcon />}
                        onClick={handleExecute}
                        disabled={executing || steps.length === 0}
                        color="success"
                        sx={{ ml: 2, borderRadius: 2, fontWeight: 600, whiteSpace: 'nowrap' }}
                      >
                        {executing ? 'Starting...' : 'Execute SOP'}
                      </Button>
                    </Tooltip>
                  )}
                </Box>

                {/* Steps */}
                {steps.length === 0 ? (
                  <Box sx={{ textAlign: 'center', py: 6 }}>
                    <FormatListNumberedIcon sx={{ fontSize: 40, color: 'grey.300', mb: 1 }} />
                    <Typography color="text.secondary">No steps defined for this SOP.</Typography>
                  </Box>
                ) : (
                  <Stepper orientation="vertical" nonLinear>
                    {steps.map((step, idx) => {
                      const meta = STEP_TYPE_META[step.type] || STEP_TYPE_META.manual;
                      return (
                        <Step key={idx} active expanded>
                          <StepLabel
                            StepIconComponent={() => (
                              <Avatar
                                sx={{
                                  width: 32,
                                  height: 32,
                                  bgcolor: STEP_TYPE_BG[step.type] || '#e3f2fd',
                                  color: `${meta.color}.main`,
                                  border: '2px solid',
                                  borderColor: `${meta.color}.light`,
                                }}
                              >
                                <Typography variant="caption" fontWeight={700} sx={{ color: `${meta.color}.dark` }}>
                                  {idx + 1}
                                </Typography>
                              </Avatar>
                            )}
                          >
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                              <Typography fontWeight={600} variant="body1">
                                {step.title}
                              </Typography>
                              <Chip
                                icon={meta.icon}
                                label={meta.label}
                                color={meta.color}
                                size="small"
                                sx={{ fontWeight: 500 }}
                              />
                            </Box>
                          </StepLabel>
                          <StepContent>
                            <Box
                              sx={{
                                bgcolor: STEP_TYPE_BG[step.type] || 'grey.50',
                                borderRadius: 2,
                                p: 2,
                                mb: 1,
                                border: '1px solid',
                                borderColor: `${meta.color}.light`,
                              }}
                            >
                              {step.description && (
                                <Typography variant="body2" color="text.secondary" sx={{ mb: step.checklist_items?.length > 0 ? 1.5 : 0, lineHeight: 1.6 }}>
                                  {step.description}
                                </Typography>
                              )}
                              {step.checklist_items?.length > 0 && (
                                <Box>
                                  <Typography variant="caption" fontWeight={700} color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: 0.5 }}>
                                    Checklist
                                  </Typography>
                                  {step.checklist_items.map((item, ci) => (
                                    <FormControlLabel
                                      key={ci}
                                      control={<Checkbox size="small" />}
                                      label={<Typography variant="body2">{item}</Typography>}
                                      sx={{ display: 'flex', ml: 0, mt: 0.5 }}
                                    />
                                  ))}
                                </Box>
                              )}
                            </Box>
                          </StepContent>
                        </Step>
                      );
                    })}
                  </Stepper>
                )}
              </Box>
            )}
          </Paper>
        </Grid>
      </Grid>

      {/* ── Create SOP Dialog ── */}
      <Dialog open={createOpen} onClose={() => setCreateOpen(false)} maxWidth="md" fullWidth fullScreen={fullScreen}>
        <DialogTitle sx={{ pb: 1 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
            <Avatar sx={{ bgcolor: 'primary.main', width: 36, height: 36 }}>
              <MenuBookIcon fontSize="small" />
            </Avatar>
            <Box>
              <Typography variant="h6" fontWeight={700}>Create New SOP</Typography>
              <Typography variant="caption" color="text.secondary">Define the procedure and its steps</Typography>
            </Box>
          </Box>
        </DialogTitle>
        <Divider />
        <DialogContent sx={{ pt: 2 }}>
          {/* Basic Info */}
          <Typography variant="subtitle2" fontWeight={700} color="text.secondary" sx={{ mb: 1.5, textTransform: 'uppercase', letterSpacing: 0.5, fontSize: 11 }}>
            Basic Information
          </Typography>
          <Grid container spacing={2} sx={{ mb: 1 }}>
            <Grid item xs={12} sm={6}>
              <TextField
                label="SOP Name"
                fullWidth
                value={sopForm.name}
                onChange={(e) => setSopForm({ ...sopForm, name: e.target.value })}
                placeholder="e.g. New Employee Laptop Setup"
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                label="Category"
                fullWidth
                value={sopForm.category}
                onChange={(e) => setSopForm({ ...sopForm, category: e.target.value })}
                placeholder="e.g. Onboarding, Hardware, Software"
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                label="Description"
                fullWidth
                multiline
                rows={2}
                value={sopForm.description}
                onChange={(e) => setSopForm({ ...sopForm, description: e.target.value })}
                placeholder="Brief description of what this SOP covers..."
              />
            </Grid>
          </Grid>

          <Divider sx={{ my: 2.5 }} />

          {/* Steps */}
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
            <Box>
              <Typography variant="subtitle2" fontWeight={700} color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: 0.5, fontSize: 11 }}>
                Steps
              </Typography>
              <Typography variant="caption" color="text.disabled">
                {sopForm.steps.length} step{sopForm.steps.length !== 1 ? 's' : ''} defined
              </Typography>
            </Box>
            <Button
              size="small"
              variant="outlined"
              startIcon={<AddIcon />}
              onClick={addStep}
              sx={{ borderRadius: 2 }}
            >
              Add Step
            </Button>
          </Box>

          {sopForm.steps.map((step, idx) => {
            const meta = STEP_TYPE_META[step.type] || STEP_TYPE_META.manual;
            return (
              <Paper
                key={idx}
                variant="outlined"
                sx={{
                  p: 2,
                  mb: 2,
                  borderRadius: 2,
                  borderColor: `${meta.color}.light`,
                  bgcolor: STEP_TYPE_BG[step.type] + '60',
                }}
              >
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.5 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Avatar sx={{ width: 26, height: 26, bgcolor: `${meta.color}.main`, fontSize: 12, fontWeight: 700 }}>
                      {idx + 1}
                    </Avatar>
                    <Typography fontWeight={600} variant="body2" color="text.secondary">
                      Step {idx + 1}
                    </Typography>
                  </Box>
                  {sopForm.steps.length > 1 && (
                    <Tooltip title="Remove step">
                      <IconButton size="small" color="error" onClick={() => removeStep(idx)}>
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  )}
                </Box>

                <Grid container spacing={1.5}>
                  <Grid item xs={12} sm={8}>
                    <TextField
                      label="Step Title"
                      fullWidth
                      size="small"
                      value={step.title}
                      onChange={(e) => updateStep(idx, 'title', e.target.value)}
                      placeholder="What needs to be done?"
                    />
                  </Grid>
                  <Grid item xs={12} sm={4}>
                    <TextField
                      select
                      label="Type"
                      fullWidth
                      size="small"
                      value={step.type}
                      onChange={(e) => updateStep(idx, 'type', e.target.value)}
                    >
                      {STEP_TYPES.map((t) => (
                        <MenuItem key={t} value={t}>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            {STEP_TYPE_META[t]?.icon}
                            <span style={{ textTransform: 'capitalize' }}>{t}</span>
                          </Box>
                        </MenuItem>
                      ))}
                    </TextField>
                  </Grid>
                  <Grid item xs={12}>
                    <TextField
                      label="Description"
                      fullWidth
                      size="small"
                      multiline
                      rows={2}
                      value={step.description}
                      onChange={(e) => updateStep(idx, 'description', e.target.value)}
                      placeholder="Describe what this step involves..."
                    />
                  </Grid>

                  {/* Checklist Items */}
                  <Grid item xs={12}>
                    <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                      <ChecklistIcon fontSize="small" color="action" sx={{ mr: 0.5 }} />
                      <Typography variant="caption" fontWeight={700} color="text.secondary">
                        Checklist Items
                      </Typography>
                      <Button size="small" sx={{ ml: 1, fontSize: 11 }} onClick={() => addChecklistItem(idx)}>
                        + Add
                      </Button>
                    </Box>
                    {(step.checklist_items || []).map((item, ci) => (
                      <Box key={ci} sx={{ display: 'flex', gap: 0.75, mb: 0.75 }}>
                        <TextField
                          size="small"
                          fullWidth
                          placeholder={`Checklist item ${ci + 1}`}
                          value={item}
                          onChange={(e) => updateChecklistItem(idx, ci, e.target.value)}
                        />
                        <IconButton size="small" color="error" onClick={() => removeChecklistItem(idx, ci)}>
                          <DeleteIcon fontSize="small" />
                        </IconButton>
                      </Box>
                    ))}
                  </Grid>
                </Grid>
              </Paper>
            );
          })}
        </DialogContent>
        <Divider />
        <DialogActions sx={{ px: 3, py: 2 }}>
          <Button onClick={() => setCreateOpen(false)} sx={{ borderRadius: 2 }}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleCreateSOP}
            disabled={saving || !sopForm.name}
            sx={{ borderRadius: 2, fontWeight: 600 }}
          >
            {saving ? 'Creating...' : 'Create SOP'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* ── Execute SOP Dialog ── */}
      <Dialog open={execOpen} onClose={() => setExecOpen(false)} maxWidth="sm" fullWidth fullScreen={fullScreen}>
        <DialogTitle sx={{ pb: 1 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
            <Avatar sx={{ bgcolor: 'success.main', width: 36, height: 36 }}>
              <PlayArrowIcon fontSize="small" />
            </Avatar>
            <Box>
              <Typography variant="subtitle1" fontWeight={700}>{selected?.name}</Typography>
              <Typography variant="caption" color="text.secondary">
                Step {Math.min(execStep + 1, steps.length)} of {steps.length}
              </Typography>
            </Box>
          </Box>
          {/* Progress bar */}
          <Box sx={{ mt: 2 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
              <Typography variant="caption" color="text.secondary">Progress</Typography>
              <Typography variant="caption" fontWeight={600} color="success.main">{execProgress}%</Typography>
            </Box>
            <LinearProgress
              variant="determinate"
              value={execProgress}
              color="success"
              sx={{ borderRadius: 4, height: 6 }}
            />
          </Box>
        </DialogTitle>
        <Divider />
        <DialogContent sx={{ pt: 2 }}>
          {execStep >= steps.length ? (
            <Box sx={{ textAlign: 'center', py: 4 }}>
              <CheckCircleIcon sx={{ fontSize: 56, color: 'success.main', mb: 1.5 }} />
              <Typography variant="h6" fontWeight={700} color="success.main">
                SOP Completed!
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                All {steps.length} steps have been executed successfully.
              </Typography>
            </Box>
          ) : (
            <Stepper activeStep={execStep} orientation="vertical">
              {steps.map((step, idx) => {
                const meta = STEP_TYPE_META[step.type] || STEP_TYPE_META.manual;
                return (
                  <Step key={idx}>
                    <StepLabel>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Typography fontWeight={600}>{step.title}</Typography>
                        <Chip icon={meta.icon} label={meta.label} color={meta.color} size="small" />
                      </Box>
                    </StepLabel>
                    <StepContent>
                      {step.description && (
                        <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5, lineHeight: 1.6 }}>
                          {step.description}
                        </Typography>
                      )}
                      {step.checklist_items?.length > 0 && (
                        <Box sx={{ mb: 1.5, pl: 0.5 }}>
                          <Typography variant="caption" fontWeight={700} color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: 0.5 }}>
                            Checklist
                          </Typography>
                          {step.checklist_items.map((item, ci) => (
                            <FormControlLabel
                              key={ci}
                              control={<Checkbox size="small" color="success" />}
                              label={<Typography variant="body2">{item}</Typography>}
                              sx={{ display: 'flex', ml: 0, mt: 0.5 }}
                            />
                          ))}
                        </Box>
                      )}
                      <Box sx={{ mt: 2, display: 'flex', gap: 1 }}>
                        <Button
                          variant="contained"
                          color="success"
                          size="small"
                          startIcon={idx < steps.length - 1 ? null : <CheckCircleIcon />}
                          onClick={() => setExecStep((s) => s + 1)}
                          sx={{ borderRadius: 2, fontWeight: 600 }}
                        >
                          {idx < steps.length - 1 ? 'Complete & Next' : 'Finish SOP'}
                        </Button>
                        {idx > 0 && (
                          <Button size="small" onClick={() => setExecStep((s) => s - 1)} sx={{ borderRadius: 2 }}>
                            Back
                          </Button>
                        )}
                      </Box>
                    </StepContent>
                  </Step>
                );
              })}
            </Stepper>
          )}
        </DialogContent>
        <Divider />
        <DialogActions sx={{ px: 3, py: 2 }}>
          <Button onClick={() => setExecOpen(false)} sx={{ borderRadius: 2 }}>Close</Button>
        </DialogActions>
      </Dialog>

      <Snackbar
        open={snack.open}
        autoHideDuration={4000}
        onClose={() => setSnack({ ...snack, open: false })}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert severity={snack.severity} onClose={() => setSnack({ ...snack, open: false })} sx={{ borderRadius: 2 }}>
          {snack.msg}
        </Alert>
      </Snackbar>
    </Box>
  );
}

export default SOPManagement;
