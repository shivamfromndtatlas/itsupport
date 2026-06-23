import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Divider,
  Grid,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
  Avatar,
  Alert,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import WorkOutlineIcon from '@mui/icons-material/WorkOutlineOutlined';
import CalendarMonthIcon from '@mui/icons-material/CalendarMonth';
import BadgeIcon from '@mui/icons-material/Badge';
import api from '../../api/axios';

const STATUS_COLORS = { active: 'success', inactive: 'default', on_leave: 'warning' };

const EMPTY_VALUE = 'Not available';

const formatValue = (value) => value || EMPTY_VALUE;

const formatDate = (value) => (value ? new Date(value).toLocaleDateString() : EMPTY_VALUE);

function getLogoUrl(logo) {
  if (!logo) return '';
  if (/^https?:\/\//i.test(logo)) return logo;
  const host = process.env.REACT_APP_API_HOST || window.location.hostname || 'localhost';
  return `http://${host}:8000${logo.startsWith('/') ? logo : `/${logo}`}`;
}

function OrgAvatar({ org }) {
  const logoUrl = getLogoUrl(org.logo);
  return logoUrl ? (
    <Avatar src={logoUrl} alt={org.name} sx={{ width: 44, height: 44, bgcolor: 'background.paper' }} />
  ) : (
    <Avatar sx={{ width: 44, height: 44, bgcolor: org.is_base ? 'primary.main' : 'secondary.main' }}>
      {org.name?.split(' ').filter(Boolean).map((part) => part[0]).join('').slice(0, 2).toUpperCase() || 'OR'}
    </Avatar>
  );
}

function InfoRow({ label, value, icon }) {
  return (
    <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'flex-start', py: 1.25 }}>
      <Box sx={{ color: 'primary.main', mt: 0.25 }}>{icon}</Box>
      <Box>
        <Typography variant="caption" color="text.secondary" display="block">
          {label}
        </Typography>
        <Typography variant="body2" fontWeight={600}>
          {value}
        </Typography>
      </Box>
    </Box>
  );
}

function EmployeeDashboard() {
  const { employeeId } = useParams();
  const navigate = useNavigate();
  const [employee, setEmployee] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;

    const load = async () => {
      setLoading(true);
      setError('');
      try {
        const { data } = await api.get(`/employees/${employeeId}/dashboard/`);
        if (active) setEmployee(data);
      } catch (err) {
        if (active) {
          setEmployee(null);
          setError(err.response?.data?.detail || 'Unable to load employee dashboard.');
        }
      } finally {
        if (active) setLoading(false);
      }
    };

    load();
    return () => {
      active = false;
    };
  }, [employeeId]);

  const assignedAssets = useMemo(() => {
    const rows = employee?.assigned_assets || [];
    return rows.map((row) => ({ ...row, id: row.id || row.asset_detail?.id || row.asset?.id }));
  }, [employee]);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error || !employee) {
    return (
      <Stack spacing={2}>
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate(-1)} sx={{ alignSelf: 'flex-start' }}>
          Back
        </Button>
        <Alert severity="error">{error || 'Employee not found.'}</Alert>
      </Stack>
    );
  }

  const initials = employee.full_name
    ?.split(' ')
    .filter(Boolean)
    .map((part) => part[0])
    .join('')
    .slice(0, 2)
    .toUpperCase() || 'EM';

  return (
    <Box>
      <Button startIcon={<ArrowBackIcon />} onClick={() => navigate(-1)} sx={{ mb: 2 }}>
        Back
      </Button>

      <Paper sx={{ p: 3, mb: 3, borderRadius: 3, background: 'linear-gradient(135deg, rgba(76,70,255,0.08), rgba(24,144,255,0.05))' }}>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} alignItems={{ sm: 'center' }} justifyContent="space-between">
          <Stack direction="row" spacing={2} alignItems="center">
            <Avatar sx={{ width: 60, height: 60, bgcolor: 'primary.main', fontSize: 22, fontWeight: 700 }}>{initials}</Avatar>
            <Box>
              <Typography variant="h4" fontWeight={800}>
                {employee.full_name}
              </Typography>
              <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mt: 0.75 }}>
                <Chip label={employee.employee_id} icon={<BadgeIcon />} />
                <Chip label={employee.core_process_code || 'No Process'} icon={<WorkOutlineIcon />} variant="outlined" />
                <Chip label={(employee.status || 'active').replace(/_/g, ' ')} color={STATUS_COLORS[employee.status] || 'default'} />
              </Stack>
            </Box>
          </Stack>
        </Stack>
      </Paper>

      <Grid container spacing={3}>
        <Grid item xs={12} lg={6}>
          <Card sx={{ borderRadius: 3, height: '100%' }}>
            <CardContent>
              <Typography variant="h6" fontWeight={800} sx={{ mb: 1 }}>
                Identity
              </Typography>
              <Divider sx={{ mb: 1 }} />
              <InfoRow label="Full Name" value={formatValue(employee.full_name)} icon={<BadgeIcon fontSize="small" />} />
              <InfoRow label="Alias Name" value={formatValue(employee.alias_name)} icon={<BadgeIcon fontSize="small" />} />
              <InfoRow label="Employee ID" value={formatValue(employee.employee_id)} icon={<BadgeIcon fontSize="small" />} />
              <InfoRow
                label="Core Process"
                value={employee.core_process_code ? `${employee.core_process_code} - ${employee.core_process_name || ''}`.trim() : EMPTY_VALUE}
                icon={<WorkOutlineIcon fontSize="small" />}
              />
              <InfoRow label="Designation" value={formatValue(employee.designation)} icon={<WorkOutlineIcon fontSize="small" />} />
              <InfoRow label="Date of Joining" value={formatDate(employee.date_of_joining)} icon={<CalendarMonthIcon fontSize="small" />} />
              <InfoRow label="Date of Separation" value={formatDate(employee.date_of_separation)} icon={<CalendarMonthIcon fontSize="small" />} />
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} lg={6}>
          <Card sx={{ borderRadius: 3, height: '100%' }}>
            <CardContent>
              <Typography variant="h6" fontWeight={800} sx={{ mb: 1 }}>
                Organisations & Email IDs
              </Typography>
              <Divider sx={{ mb: 2 }} />

              <Stack spacing={1.5}>
                <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 2 }}>
                  <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
                    <Box sx={{ flex: 1 }}>
                      <Typography variant="caption" color="text.secondary" display="block">
                        Base organisation email
                      </Typography>
                      <Typography variant="body2" fontWeight={700}>
                        {employee.base_email || EMPTY_VALUE}
                      </Typography>
                    </Box>
                    <Box sx={{ flex: 1 }}>
                      <Typography variant="caption" color="text.secondary" display="block">
                        Client email ID{(employee.client_emails || []).length === 1 ? '' : 's'}
                      </Typography>
                      {(employee.client_emails || []).length > 0 ? (
                        <Stack spacing={0.5} sx={{ mt: 0.25 }}>
                          {employee.client_emails.map((org) => (
                            <Typography key={org.id} variant="body2" fontWeight={700}>
                              {org.email || EMPTY_VALUE}
                            </Typography>
                          ))}
                        </Stack>
                      ) : (
                        <Typography variant="body2" fontWeight={700}>
                          {EMPTY_VALUE}
                        </Typography>
                      )}
                    </Box>
                  </Stack>
                </Paper>

                {(employee.organisation_cards || []).length > 0 ? (
                  employee.organisation_cards.map((org) => (
                    <Paper
                      key={org.id}
                      variant="outlined"
                      sx={{ p: 1.5, borderRadius: 2, display: 'flex', alignItems: 'center', gap: 1.5 }}
                    >
                      <OrgAvatar org={org} />
                      <Box sx={{ minWidth: 0, flex: 1 }}>
                        <Typography variant="body2" fontWeight={700}>
                          {org.name}
                        </Typography>
                        <Typography variant="caption" color="text.secondary" display="block">
                          {org.is_base ? 'Base organisation' : 'Client organisation'}
                        </Typography>
                        <Typography variant="body2" sx={{ mt: 0.5 }}>
                          <Box component="span" sx={{ color: 'text.secondary' }}>
                            Email:
                          </Box>{' '}
                          {org.email || EMPTY_VALUE}
                        </Typography>
                      </Box>
                    </Paper>
                  ))
                ) : (
                  <Typography color="text.secondary">No organisation information available.</Typography>
                )}
              </Stack>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12}>
          <Paper sx={{ p: 3, borderRadius: 3 }}>
            <Typography variant="h6" fontWeight={800} sx={{ mb: 1 }}>
              Assigned Assets
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Detailed asset allocation history for this employee.
            </Typography>
            <Divider sx={{ mb: 2 }} />

            {assignedAssets.length === 0 ? (
              <Box sx={{ py: 4, textAlign: 'center', color: 'text.secondary' }}>
                No assets have been assigned to this employee yet.
              </Box>
            ) : (
              <Box sx={{ width: '100%', overflowX: 'auto' }}>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Asset</TableCell>
                      <TableCell>Type</TableCell>
                      <TableCell>Serial Number</TableCell>
                      <TableCell>Assigned Date</TableCell>
                      <TableCell>Status</TableCell>
                      <TableCell>Assigned By</TableCell>
                      <TableCell>Recovered Date</TableCell>
                      <TableCell>Notes</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {assignedAssets.map((row) => (
                      <TableRow key={row.id} hover>
                        <TableCell>{row.asset_detail?.asset_id || row.asset || EMPTY_VALUE}</TableCell>
                        <TableCell>{row.asset_detail?.asset_type_name || EMPTY_VALUE}</TableCell>
                        <TableCell>{row.asset_detail?.serial_number || EMPTY_VALUE}</TableCell>
                        <TableCell>{row.assigned_date || EMPTY_VALUE}</TableCell>
                        <TableCell>
                          <Chip
                            label={(row.status || 'active').replace(/_/g, ' ')}
                            size="small"
                            color={STATUS_COLORS[row.status] || 'default'}
                          />
                        </TableCell>
                        <TableCell>{row.assigned_by_name || EMPTY_VALUE}</TableCell>
                        <TableCell>{row.recovered_date || EMPTY_VALUE}</TableCell>
                        <TableCell>{row.notes || EMPTY_VALUE}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Box>
            )}
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
}

export default EmployeeDashboard;
