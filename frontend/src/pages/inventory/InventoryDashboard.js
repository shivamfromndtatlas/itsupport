import React, { useState, useEffect } from 'react';
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
} from '@mui/material';
import DevicesIcon from '@mui/icons-material/Devices';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import AssignmentTurnedInIcon from '@mui/icons-material/AssignmentTurnedIn';
import BuildIcon from '@mui/icons-material/Build';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from 'recharts';
import api from '../../api/axios';

const PIE_COLORS = ['#1565C0', '#00897B', '#F9A825', '#757575', '#E53935'];

function StatCard({ title, value, icon, color, loading }) {
  return (
    <Card sx={{ borderRadius: 2, boxShadow: 2 }}>
      <CardContent sx={{ display: 'flex', alignItems: 'center', gap: 2, p: 2.5 }}>
        <Box
          sx={{
            bgcolor: `${color}.light`,
            borderRadius: 2,
            p: 1.5,
            display: 'flex',
          }}
        >
          {React.cloneElement(icon, { sx: { fontSize: 28, color: `${color}.main` } })}
        </Box>
        <Box>
          <Typography variant="caption" color="text.secondary" fontWeight={500}>
            {title}
          </Typography>
          {loading ? (
            <Skeleton width={50} height={32} />
          ) : (
            <Typography variant="h5" fontWeight={700}>
              {value ?? '--'}
            </Typography>
          )}
        </Box>
      </CardContent>
    </Card>
  );
}

function InventoryDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetch = async () => {
      setLoading(true);
      try {
        const res = await api.get('/inventory/assets/dashboard-stats/');
        setData(res.data);
      } catch {
        setError('Failed to load inventory dashboard data.');
      } finally {
        setLoading(false);
      }
    };
    fetch();
  }, []);

  const stats = data?.summary || data || {};
  const totalAssets = stats.total_assets ?? stats.total ?? null;
  const available = stats.available ?? null;
  const assigned = stats.assigned ?? null;
  const maintenance = stats.maintenance ?? stats.under_maintenance ?? null;

  // Assets by type
  const byTypeRaw = data?.assets_by_type || data?.by_type || [];
  const byTypeData = Array.isArray(byTypeRaw)
    ? byTypeRaw.map((item) => ({
        name: item.asset_type || item.name || item.type || item.label,
        count: item.count || item.total || item.value,
      }))
    : Object.entries(byTypeRaw).map(([name, count]) => ({ name, count }));

  // Status distribution
  const statusData = [
    { name: 'Available', value: available },
    { name: 'Assigned', value: assigned },
    { name: 'Maintenance', value: maintenance },
  ].filter((d) => d.value != null);

  // Software licenses
  const licenses = data?.software_licenses || data?.licenses || [];

  return (
    <Box>
      <Typography variant="h6" fontWeight={600} sx={{ mb: 3 }}>
        Inventory Dashboard
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {/* Stat Cards */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <StatCard title="Total Assets" value={totalAssets} icon={<DevicesIcon />} color="primary" loading={loading} />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <StatCard title="Available" value={available} icon={<CheckCircleIcon />} color="success" loading={loading} />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <StatCard title="Assigned" value={assigned} icon={<AssignmentTurnedInIcon />} color="info" loading={loading} />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <StatCard title="Under Maintenance" value={maintenance} icon={<BuildIcon />} color="warning" loading={loading} />
        </Grid>
      </Grid>

      {/* Charts Row */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        {/* Bar Chart */}
        <Grid size={{ xs: 12, md: 7 }}>
          <Card sx={{ borderRadius: 2, boxShadow: 2, p: 2 }}>
            <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 2 }}>
              Assets by Type
            </Typography>
            {loading ? (
              <Skeleton variant="rectangular" height={260} />
            ) : byTypeData.length > 0 ? (
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={byTypeData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="count" fill="#1565C0" radius={[4, 4, 0, 0]} name="Assets" />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <Box sx={{ textAlign: 'center', py: 5 }}>
                <Typography color="text.secondary">No data available.</Typography>
              </Box>
            )}
          </Card>
        </Grid>

        {/* Pie Chart */}
        <Grid size={{ xs: 12, md: 5 }}>
          <Card sx={{ borderRadius: 2, boxShadow: 2, p: 2 }}>
            <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 2 }}>
              Status Distribution
            </Typography>
            {loading ? (
              <Skeleton variant="circular" width={220} height={220} sx={{ mx: 'auto' }} />
            ) : statusData.length > 0 ? (
              <ResponsiveContainer width="100%" height={260}>
                <PieChart>
                  <Pie
                    data={statusData}
                    cx="50%"
                    cy="50%"
                    outerRadius={100}
                    dataKey="value"
                    label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                    labelLine={false}
                  >
                    {statusData.map((_, i) => (
                      <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <Box sx={{ textAlign: 'center', py: 5 }}>
                <Typography color="text.secondary">No data available.</Typography>
              </Box>
            )}
          </Card>
        </Grid>
      </Grid>

      {/* Software Licenses Table */}
      {licenses.length > 0 && (
        <Card sx={{ borderRadius: 2, boxShadow: 2 }}>
          <CardContent>
            <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 2 }}>
              Software License Utilization
            </Typography>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell><strong>Software</strong></TableCell>
                    <TableCell align="center"><strong>Total</strong></TableCell>
                    <TableCell align="center"><strong>Used</strong></TableCell>
                    <TableCell><strong>Utilization</strong></TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {licenses.map((lic, i) => {
                    const total = lic.total_seats || lic.total || 1;
                    const used = lic.used_seats ?? (total - (lic.available_seats || 0));
                    const pct = Math.round((used / total) * 100);
                    return (
                      <TableRow key={i}>
                        <TableCell>{lic.software_name || lic.name}</TableCell>
                        <TableCell align="center">{total}</TableCell>
                        <TableCell align="center">{used}</TableCell>
                        <TableCell sx={{ minWidth: 180 }}>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <LinearProgress
                              variant="determinate"
                              value={pct}
                              sx={{ flex: 1, height: 8, borderRadius: 4 }}
                              color={pct > 90 ? 'error' : pct > 70 ? 'warning' : 'primary'}
                            />
                            <Typography variant="caption">{pct}%</Typography>
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
