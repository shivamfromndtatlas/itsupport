import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
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
  Typography,
  Divider,
  Paper,
  Avatar,
  List,
  ListItem,
  ListItemAvatar,
  ListItemText,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import VisibilityIcon from '@mui/icons-material/Visibility';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';
import SendIcon from '@mui/icons-material/Send';
import CloseIcon from '@mui/icons-material/Close';
import DataTable from '../../components/common/DataTable';
import api from '../../api/axios';
import { useAuth } from '../../context/AuthContext';

const PRIORITY_COLORS = { low: 'default', medium: 'info', high: 'warning', critical: 'error' };
const STATUS_COLORS = { open: 'error', in_progress: 'warning', resolved: 'success', closed: 'default' };
const CATEGORIES = ['hardware', 'software', 'network', 'access', 'account', 'other'];
const PRIORITIES = ['low', 'medium', 'high', 'critical'];
const EMPTY_TICKET = { title: '', description: '', category: 'other', priority: 'medium' };

function Tickets() {
  const { hasRole } = useAuth();
  const theme = useTheme();
  const fullScreen = useMediaQuery(theme.breakpoints.down('sm'));
  const isITorAdmin = hasRole('super_admin', 'it_specialist');

  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [raiseDialog, setRaiseDialog] = useState(false);
  const [form, setForm] = useState(EMPTY_TICKET);
  const [submitting, setSubmitting] = useState(false);
  const [detailDialog, setDetailDialog] = useState({ open: false, ticket: null });
  const [comments, setComments] = useState([]);
  const [commentText, setCommentText] = useState('');
  const [sendingComment, setSendingComment] = useState(false);
  const [users, setUsers] = useState([]);
  const [assignee, setAssignee] = useState('');
  const [snack, setSnack] = useState({ open: false, msg: '', severity: 'success' });

  const showSnack = (msg, severity = 'success') => setSnack({ open: true, msg, severity });

  const fetchTickets = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/tickets/');
      const data = Array.isArray(res.data) ? res.data : res.data.results || [];
      setRows(data.map((t) => ({ ...t, id: t.id || t.pk })));
    } catch { showSnack('Failed to load tickets.', 'error'); }
    finally { setLoading(false); }
  }, []);

  const fetchUsers = useCallback(async () => {
    if (!isITorAdmin) return;
    try {
      const res = await api.get('/auth/users/');
      setUsers(Array.isArray(res.data) ? res.data : res.data.results || []);
    } catch {}
  }, [isITorAdmin]);

  useEffect(() => { fetchTickets(); fetchUsers(); }, [fetchTickets, fetchUsers]);

  const handleRaise = async () => {
    setSubmitting(true);
    try {
      await api.post('/tickets/', form);
      showSnack('Ticket raised successfully.');
      setRaiseDialog(false);
      setForm(EMPTY_TICKET);
      fetchTickets();
    } catch (err) {
      showSnack(err.response?.data?.detail || 'Failed to raise ticket.', 'error');
    } finally { setSubmitting(false); }
  };

  const openDetail = async (ticket) => {
    setDetailDialog({ open: true, ticket });
    setAssignee(ticket.assigned_to || '');
    try {
      const res = await api.get(`/tickets/${ticket.id}/comments/`);
      setComments(Array.isArray(res.data) ? res.data : res.data.results || []);
    } catch { setComments([]); }
  };

  const handleStatusChange = async (status) => {
    const ticket = detailDialog.ticket;
    try {
      await api.patch(`/tickets/${ticket.id}/`, { status });
      showSnack(`Ticket ${status}.`);
      setDetailDialog({ open: true, ticket: { ...ticket, status } });
      fetchTickets();
    } catch { showSnack('Status update failed.', 'error'); }
  };

  const handleAssign = async () => {
    const ticket = detailDialog.ticket;
    try {
      await api.patch(`/tickets/${ticket.id}/`, { assigned_to: assignee || null });
      showSnack('Ticket assigned.');
      setDetailDialog({ open: true, ticket: { ...ticket, assigned_to: assignee } });
      fetchTickets();
    } catch { showSnack('Assignment failed.', 'error'); }
  };

  const handleSendComment = async () => {
    if (!commentText.trim()) return;
    setSendingComment(true);
    try {
      const res = await api.post(`/tickets/${detailDialog.ticket.id}/comments/`, { comment: commentText });
      setComments((prev) => [...prev, res.data]);
      setCommentText('');
    } catch { showSnack('Failed to send comment.', 'error'); }
    finally { setSendingComment(false); }
  };

  const columns = [
    { field: 'ticket_id', headerName: 'Ticket ID', width: 120, renderCell: ({ row }) => row.ticket_id || `#${row.id}` },
    { field: 'title', headerName: 'Title', flex: 1.5, minWidth: 180 },
    {
      field: 'priority', headerName: 'Priority', width: 110,
      renderCell: ({ value }) => (
        <Chip label={value} color={PRIORITY_COLORS[value] || 'default'} size="small" sx={{ textTransform: 'capitalize' }} />
      ),
    },
    {
      field: 'status', headerName: 'Status', width: 130,
      renderCell: ({ value }) => (
        <Chip label={(value || '').replace('_', ' ')} color={STATUS_COLORS[value] || 'default'} size="small" sx={{ textTransform: 'capitalize' }} />
      ),
    },
    { field: 'raised_by', headerName: 'Raised By', flex: 1, minWidth: 120, renderCell: ({ row }) => row.raised_by_name || row.raised_by || '--' },
    { field: 'created_at', headerName: 'Created', width: 120, renderCell: ({ value }) => value ? new Date(value).toLocaleDateString() : '--' },
    {
      field: 'actions', headerName: '', width: 60, sortable: false,
      renderCell: ({ row }) => (
        <Tooltip title="View Details">
          <IconButton size="small" onClick={() => openDetail(row)}>
            <VisibilityIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      ),
    },
  ];

  const ticket = detailDialog.ticket;

  return (
    <Box>
      <DataTable
        title="Support Tickets"
        rows={rows}
        columns={columns}
        loading={loading}
        onRefresh={fetchTickets}
        onAdd={() => { setForm(EMPTY_TICKET); setRaiseDialog(true); }}
        addLabel="Raise Ticket"
        refreshLabel="Refresh"
        searchable
      />

      {/* ── Raise Ticket Dialog ── */}
      <Dialog open={raiseDialog} onClose={() => setRaiseDialog(false)} maxWidth="sm" fullWidth fullScreen={fullScreen}>
        <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          Raise Support Ticket
          {fullScreen && (
            <IconButton size="small" onClick={() => setRaiseDialog(false)}>
              <CloseIcon fontSize="small" />
            </IconButton>
          )}
        </DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 0 }}>
            <Grid item xs={12}>
              <TextField
                label="Title" fullWidth value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                label="Description" fullWidth multiline rows={4}
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField select label="Category" fullWidth value={form.category}
                onChange={(e) => setForm({ ...form, category: e.target.value })}>
                {CATEGORIES.map((c) => <MenuItem key={c} value={c} sx={{ textTransform: 'capitalize' }}>{c}</MenuItem>)}
              </TextField>
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField select label="Priority" fullWidth value={form.priority}
                onChange={(e) => setForm({ ...form, priority: e.target.value })}>
                {PRIORITIES.map((p) => <MenuItem key={p} value={p} sx={{ textTransform: 'capitalize' }}>{p}</MenuItem>)}
              </TextField>
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRaiseDialog(false)} sx={{ color: 'text.secondary' }}>Cancel</Button>
          <Button variant="contained" onClick={handleRaise} disabled={submitting}>
            {submitting ? 'Submitting…' : 'Raise Ticket'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* ── Ticket Detail Dialog ── */}
      <Dialog
        open={detailDialog.open}
        onClose={() => setDetailDialog({ open: false, ticket: null })}
        maxWidth="md" fullWidth fullScreen={fullScreen}
      >
        {ticket && (
          <>
            <DialogTitle>
              {/* Responsive title: stacks on mobile */}
              <Box sx={{ display: 'flex', flexDirection: { xs: 'column', sm: 'row' }, gap: { xs: 1.5, sm: 1 }, justifyContent: 'space-between' }}>
                <Box sx={{ flex: 1, minWidth: 0 }}>
                  <Typography variant="h6" fontWeight={700} sx={{ fontSize: { xs: 14, sm: 16 }, wordBreak: 'break-word' }}>
                    {ticket.ticket_id || `#${ticket.id}`} — {ticket.title}
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 1, mt: 0.75, flexWrap: 'wrap' }}>
                    <Chip label={(ticket.status || '').replace('_', ' ')} color={STATUS_COLORS[ticket.status] || 'default'} size="small" />
                    <Chip label={ticket.priority} color={PRIORITY_COLORS[ticket.priority] || 'default'} size="small" />
                  </Box>
                </Box>
                {isITorAdmin && ticket.status !== 'closed' && (
                  <Box sx={{ display: 'flex', gap: 1, flexShrink: 0, flexWrap: 'wrap', alignItems: 'flex-start' }}>
                    {ticket.status !== 'resolved' && (
                      <Button size="small" variant="outlined" color="success" startIcon={<CheckCircleIcon />}
                        onClick={() => handleStatusChange('resolved')}>
                        Resolve
                      </Button>
                    )}
                    <Button size="small" variant="outlined" color="inherit" startIcon={<CancelIcon />}
                      onClick={() => handleStatusChange('closed')}>
                      Close
                    </Button>
                    {fullScreen && (
                      <IconButton size="small" onClick={() => setDetailDialog({ open: false, ticket: null })}>
                        <CloseIcon fontSize="small" />
                      </IconButton>
                    )}
                  </Box>
                )}
                {(!isITorAdmin || ticket.status === 'closed') && fullScreen && (
                  <IconButton size="small" onClick={() => setDetailDialog({ open: false, ticket: null })} sx={{ alignSelf: 'flex-start' }}>
                    <CloseIcon fontSize="small" />
                  </IconButton>
                )}
              </Box>
            </DialogTitle>

            <DialogContent dividers>
              <Grid container spacing={2}>
                <Grid item xs={6} sm={4}>
                  <Typography variant="caption" color="text.secondary" fontWeight={600} display="block">Category</Typography>
                  <Typography variant="body2" sx={{ textTransform: 'capitalize', mt: 0.25 }}>{ticket.category}</Typography>
                </Grid>
                <Grid item xs={6} sm={4}>
                  <Typography variant="caption" color="text.secondary" fontWeight={600} display="block">Raised By</Typography>
                  <Typography variant="body2" sx={{ mt: 0.25 }}>{ticket.raised_by_name || ticket.raised_by || '--'}</Typography>
                </Grid>
                <Grid item xs={12}>
                  <Typography variant="caption" color="text.secondary" fontWeight={600} display="block">Description</Typography>
                  <Paper variant="outlined" sx={{ p: 1.5, mt: 0.5, bgcolor: 'grey.50', borderRadius: 2 }}>
                    <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>{ticket.description}</Typography>
                  </Paper>
                </Grid>

                {isITorAdmin && (
                  <Grid item xs={12}>
                    <Divider sx={{ my: 0.5 }} />
                    <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1.5 }}>Assign To</Typography>
                    <Box sx={{ display: 'flex', gap: 1, flexDirection: { xs: 'column', sm: 'row' } }}>
                      <TextField
                        select size="small" fullWidth value={assignee}
                        onChange={(e) => setAssignee(e.target.value)} label="Assignee"
                      >
                        <MenuItem value="">Unassigned</MenuItem>
                        {users.map((u) => (
                          <MenuItem key={u.id} value={u.id}>{u.full_name || u.email}</MenuItem>
                        ))}
                      </TextField>
                      <Button variant="outlined" onClick={handleAssign} sx={{ flexShrink: 0, height: 36 }}>
                        Assign
                      </Button>
                    </Box>
                  </Grid>
                )}

                <Grid item xs={12}>
                  <Divider sx={{ my: 0.5 }} />
                  <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1.5 }}>Comments</Typography>
                  {comments.length === 0 ? (
                    <Typography variant="body2" color="text.secondary" sx={{ py: 1 }}>No comments yet.</Typography>
                  ) : (
                    <List dense disablePadding>
                      {comments.map((c, i) => (
                        <ListItem key={i} alignItems="flex-start" disablePadding sx={{ mb: 1.5 }}>
                          <ListItemAvatar>
                            <Avatar sx={{ width: 30, height: 30, fontSize: 12, bgcolor: 'primary.main' }}>
                              {(c.author_name || c.author || 'U')[0].toUpperCase()}
                            </Avatar>
                          </ListItemAvatar>
                          <ListItemText
                            primary={
                              <Typography variant="caption" fontWeight={600}>
                                {c.author_name || c.author || 'Unknown'}
                              </Typography>
                            }
                            secondary={
                              <Paper variant="outlined" sx={{ p: 1.25, mt: 0.5, bgcolor: 'grey.50', borderRadius: 2 }}>
                                <Typography variant="body2">{c.comment || c.text || c.content}</Typography>
                              </Paper>
                            }
                          />
                        </ListItem>
                      ))}
                    </List>
                  )}

                  <Box sx={{ display: 'flex', gap: 1, mt: 1.5, alignItems: 'flex-end' }}>
                    <TextField
                      size="small" fullWidth placeholder="Write a comment…"
                      value={commentText}
                      onChange={(e) => setCommentText(e.target.value)}
                      onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSendComment(); } }}
                      multiline maxRows={4}
                    />
                    <Button
                      variant="contained" onClick={handleSendComment}
                      disabled={sendingComment || !commentText.trim()}
                      sx={{ minWidth: 44, px: 1.5, height: 36, flexShrink: 0 }}
                    >
                      <SendIcon fontSize="small" />
                    </Button>
                  </Box>
                </Grid>
              </Grid>
            </DialogContent>

            <DialogActions>
              <Button onClick={() => setDetailDialog({ open: false, ticket: null })}>Close</Button>
            </DialogActions>
          </>
        )}
      </Dialog>

      <Snackbar open={snack.open} autoHideDuration={4000} onClose={() => setSnack({ ...snack, open: false })}>
        <Alert severity={snack.severity} onClose={() => setSnack({ ...snack, open: false })}>{snack.msg}</Alert>
      </Snackbar>
    </Box>
  );
}

export default Tickets;
