import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Card,
  CardContent,
  Grid,
  Typography,
  Skeleton,
  LinearProgress,
  Alert,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Stack,
  Button,
} from '@mui/material';
import DevicesIcon from '@mui/icons-material/Devices';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import AssignmentTurnedInIcon from '@mui/icons-material/AssignmentTurnedIn';
import BuildIcon from '@mui/icons-material/Build';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell, Legend,
} from 'recharts';
import api from '../../api/axios';

const PIE_COLORS = ['#10B981', '#4F46E5', '#F59E0B', '#64748B', '#EF4444'];
const BAR_COLORS = ['#4F46E5', '#7C3AED', '#0EA5E9', '#10B981', '#F59E0B', '#EF4444'];

const STAT_COLORS = {
  primary: { bg: 'rgba(79,70,229,0.08)', icon: '#4F46E5' },
  success:  { bg: 'rgba(16,185,129,0.08)', icon: '#10B981' },
  info:     { bg: 'rgba(14,165,233,0.08)', icon: '#0EA5E9' },
  warning:  { bg: 'rgba(245,158,11,0.08)', icon: '#F59E0B' },
};

function StatCard({ title, value, icon, color, loading }) {
  const colors = STAT_COLORS[color] || STAT_COLORS.primary;
  return (
    <Card sx={{ height: '100%' }}>
      <CardContent sx={{ p: 2.5, '&:last-child': { pb: 2.5 } }}>
        <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
          <Box>
            <Typography variant="body2" color="text.secondary" fontWeight={500} sx={{ fontSize: 13, mb: 1 }}>
              {title}
            </Typography>
            {loading ? (
              <Skeleton width={56} height={40} />
            ) : (
              <Typography sx={{ fontSize: 32, fontWeight: 800, color: 'text.primary', lineHeight: 1 }}>
                {value ?? '--'}
              </Typography>
            )}
          </Box>
          <Box sx={{
            bgcolor: colors.bg, borderRadius: '12px', p: 1.25,
            display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
          }}>
            {React.cloneElement(icon, { sx: { fontSize: 26, color: colors.icon } })}
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
}

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <Box sx={{ bgcolor: '#0F172A', borderRadius: '8px', px: 1.5, py: 1, boxShadow: '0 10px 25px rgba(0,0,0,0.25)' }}>
        <Typography sx={{ color: '#94A3B8', fontSize: 11, mb: 0.25 }}>{label}</Typography>
        <Typography sx={{ color: '#F8FAFC', fontWeight: 700, fontSize: 16 }}>{payload[0].value}</Typography>
      </Box>
    );
  }
  return null;
};

function InventoryDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/inventory/assets/dashboard-stats/');
      setData(res.data);
    } catch {
      setError('Failed to load inventory dashboard data.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  const stats = data?.summary || data || {};
  const statusCounts = data?.status_counts || data?.summary?.status_counts || {};
  const totalAssets = stats.total_assets ?? stats.total ?? null;
  const available = statusCounts.available ?? stats.available ?? null;
  const assigned = statusCounts.assigned ?? stats.assigned ?? null;
  const maintenance = statusCounts.maintenance ?? stats.maintenance ?? stats.under_maintenance ?? null;

  const byTypeRaw = data?.assets_by_type || data?.by_type || [];
  const byTypeData = Array.isArray(byTypeRaw)
    ? byTypeRaw.map((item) => ({ name: item.asset_type || item.name || item.type || item.label, count: item.count || item.total || item.value }))
    : Object.entries(byTypeRaw).map(([name, count]) => ({ name, count }));

  const statusData = [
    { name: 'Available', value: available },
    { name: 'Assigned', value: assigned },
    { name: 'Maintenance', value: maintenance },
  ].filter((d) => d.value != null && d.value > 0);

  const licenses = data?.software_licenses || data?.licenses || [];

  return (
    <Box>
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 2.5 }} spacing={2}>
        {error ? <Alert severity="error" sx={{ flex: 1 }}>{error}</Alert> : <Box />}
        <Button variant="outlined" size="small" onClick={loadDashboard}>Refresh</Button>
      </Stack>

      {/* Stat Cards */}
      <Grid container spacing={2.5} sx={{ mb: 3 }}>
        {[
          { title: 'Total Assets', value: totalAssets, icon: <DevicesIcon />, color: 'primary' },
          { title: 'Available', value: available, icon: <CheckCircleIcon />, color: 'success' },
          { title: 'Assigned', value: assigned, icon: <AssignmentTurnedInIcon />, color: 'info' },
          { title: 'Under Maintenance', value: maintenance, icon: <BuildIcon />, color: 'warning' },
        ].map((s) => (
          <Grid item xs={12} sm={6} md={3} key={s.title}>
            <StatCard {...s} loading={loading} />
          </Grid>
        ))}
      </Grid>

      {/* Charts */}
      <Grid container spacing={2.5} sx={{ mb: 3 }}>
        <Grid item xs={12} md={7}>
          <Card sx={{ p: 2.5 }}>
            <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 0.5 }}>Assets by Type</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2.5, fontSize: 13 }}>Distribution across hardware and software</Typography>
            {loading ? (
              <Skeleton variant="rectangular" height={260} sx={{ borderRadius: 2 }} />
            ) : byTypeData.length > 0 ? (
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={byTypeData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }} barSize={24}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" vertical={false} />
                  <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#94A3B8' }} axisLine={false} tickLine={false} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: '#94A3B8' }} axisLine={false} tickLine={false} />
                  <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(79,70,229,0.04)' }} />
                  <Bar dataKey="count" radius={[6, 6, 0, 0]} name="Assets">
                    {byTypeData.map((_, i) => <Cell key={i} fill={BAR_COLORS[i % BAR_COLORS.length]} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <Box sx={{ textAlign: 'center', py: 6 }}>
                <Typography color="text.secondary" fontSize={14}>No data available.</Typography>
              </Box>
            )}
          </Card>
        </Grid>

        <Grid item xs={12} md={5}>
          <Card sx={{ p: 2.5 }}>
            <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 0.5 }}>Status Distribution</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2.5, fontSize: 13 }}>Current asset status breakdown</Typography>
            {loading ? (
              <Skeleton variant="circular" width={200} height={200} sx={{ mx: 'auto' }} />
            ) : statusData.length > 0 ? (
              <ResponsiveContainer width="100%" height={260}>
                <PieChart>
                  <Pie
                    data={statusData} cx="50%" cy="45%" outerRadius={90}
                    dataKey="value" label={({ name, percent }) => `${(percent * 100).toFixed(0)}%`}
                    labelLine={false}
                  >
                    {statusData.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                  </Pie>
                  <Tooltip formatter={(v, n) => [v, n]} />
                  <Legend iconType="circle" iconSize={10} wrapperStyle={{ fontSize: 13 }} />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <Box sx={{ textAlign: 'center', py: 6 }}>
                <Typography color="text.secondary" fontSize={14}>No data available.</Typography>
              </Box>
            )}
          </Card>
        </Grid>
      </Grid>

      {/* Software Licenses */}
      {licenses.length > 0 && (
        <Card>
          <CardContent sx={{ p: 2.5, '&:last-child': { pb: 2.5 } }}>
            <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 0.5 }}>Software License Utilization</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2, fontSize: 13 }}>Seat usage across software products</Typography>
            <TableContainer sx={{ overflowX: 'auto' }}>
              <Table size="small" sx={{ minWidth: 400 }}>
                <TableHead>
                  <TableRow>
                    {['Software', 'Total', 'Used', 'Utilization'].map((h) => (
                      <TableCell key={h}>{h}</TableCell>
                    ))}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {licenses.map((lic, i) => {
                    const total = lic.total_seats || lic.total || 1;
                    const used = lic.used_seats ?? (total - (lic.available_seats || 0));
                    const pct = Math.round((used / total) * 100);
                    return (
                      <TableRow key={i} hover>
                        <TableCell sx={{ fontWeight: 500 }}>{lic.software_name || lic.name}</TableCell>
                        <TableCell align="center">{total}</TableCell>
                        <TableCell align="center">{used}</TableCell>
                        <TableCell sx={{ minWidth: 160 }}>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <LinearProgress
                              variant="determinate" value={pct}
                              sx={{ flex: 1, height: 6, borderRadius: 3,
                                bgcolor: 'grey.100',
                                '& .MuiLinearProgress-bar': {
                                  borderRadius: 3,
                                  bgcolor: pct > 90 ? 'error.main' : pct > 70 ? 'warning.main' : 'primary.main',
                                },
                              }}
                            />
                            <Typography variant="caption" fontWeight={600} sx={{ minWidth: 32, color: pct > 90 ? 'error.main' : 'text.secondary' }}>
                              {pct}%
                            </Typography>
                          </Box>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </TableContainer>
          </CardContent>
        </Card>
      )}
    </Box>
  );
}

export default InventoryDashboard;
