import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Card,
  CardContent,
  Grid,
  Typography,
  Skeleton,
  LinearProgress,
  Alert,
  Chip,
  Stack,
  Button,
  TextField,
  MenuItem,
  Tooltip as MuiTooltip,
} from '@mui/material';
import DevicesIcon from '@mui/icons-material/Devices';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import AssignmentTurnedInIcon from '@mui/icons-material/AssignmentTurnedIn';
import BuildIcon from '@mui/icons-material/Build';
import InventoryIcon from '@mui/icons-material/Inventory2';
import KeyIcon from '@mui/icons-material/VpnKey';
import PieChartIcon from '@mui/icons-material/PieChartOutlined';
import AllInclusiveIcon from '@mui/icons-material/AllInclusive';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell, Legend, LabelList,
} from 'recharts';
import api from '../../api/axios';

// Fixed categorical order, validated for CVD-safe adjacency (see dataviz skill):
// worst adjacent pair clears ΔE 12 with this exact sequence. Never reassign by
// position when the underlying set of categories changes - only by name.
const CATEGORICAL_COLORS = ['#4F46E5', '#10B981', '#F59E0B', '#EF4444', '#7C3AED', '#0EA5E9'];

// Assets by Type can list more categories than a categorical palette can safely
// carry, so it's a magnitude comparison (one sequential hue) rather than an
// identity chart - every type gets its own bar and its own name, no folding.
const SEQUENTIAL_HUE = '#4F46E5';

// Asset lifecycle status: Available/Maintenance carry real good/warning meaning
// (mirrors AVAILABILITY_STATUS_COLORS in Assets.js), Retired is deliberately
// grayed out as an inactive bucket rather than assigned a "real" hue.
const STATUS_COLOR_MAP = {
  Available: '#10B981',
  Assigned: '#4F46E5',
  Maintenance: '#F59E0B',
  Retired: '#94A3B8',
};

const STAT_COLORS = {
  primary: { bg: 'rgba(79,70,229,0.08)', icon: '#4F46E5' },
  success:  { bg: 'rgba(16,185,129,0.08)', icon: '#10B981' },
  info:     { bg: 'rgba(14,165,233,0.08)', icon: '#0EA5E9' },
  warning:  { bg: 'rgba(245,158,11,0.08)', icon: '#F59E0B' },
  default:  { bg: 'rgba(100,116,139,0.08)', icon: '#64748B' },
};

function StatCard({ title, value, icon, color, loading, subtitle }) {
  const colors = STAT_COLORS[color] || STAT_COLORS.primary;
  return (
    <Card sx={{ height: '100%' }}>
      <CardContent sx={{ p: 2.5, '&:last-child': { pb: 2.5 } }}>
        <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
          <Box sx={{ minWidth: 0 }}>
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
            {subtitle && !loading && (
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                {subtitle}
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

// Tooltip content: value leads (Strong, high-contrast), category name follows -
// the reader already has the series from the axis/legend and wants the number.
const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    const entry = payload[0];
    return (
      <Box sx={{ bgcolor: '#0F172A', borderRadius: '8px', px: 1.5, py: 1, boxShadow: '0 10px 25px rgba(0,0,0,0.25)' }}>
        <Typography sx={{ color: '#F8FAFC', fontWeight: 700, fontSize: 16 }}>{entry.value}</Typography>
        <Typography sx={{ color: '#94A3B8', fontSize: 11, mt: 0.25 }}>{entry.payload?.tooltipLabel || label || entry.name}</Typography>
      </Box>
    );
  }
  return null;
};

function ChartCard({ title, subtitle, icon, action, children, minHeight = 320 }) {
  return (
    <Card sx={{ p: 2.5, height: '100%' }}>
      <Stack direction="row" alignItems="flex-start" justifyContent="space-between" sx={{ mb: 0.5 }}>
        <Stack direction="row" spacing={1} alignItems="center">
          {icon}
          <Typography variant="subtitle1" fontWeight={700}>{title}</Typography>
        </Stack>
        {action}
      </Stack>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2.5, fontSize: 13 }}>{subtitle}</Typography>
      <Box sx={{ minHeight }}>{children}</Box>
    </Card>
  );
}

function InventoryDashboard() {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [organisations, setOrganisations] = useState([]);
  const [organisationId, setOrganisationId] = useState('');
  const [activeStatusIndex, setActiveStatusIndex] = useState(null);

  const loadDashboard = useCallback(async (orgId, isInitial) => {
    if (isInitial) setLoading(true);
    else setRefreshing(true);
    try {
      const params = orgId ? `?organisation_id=${orgId}` : '';
      const res = await api.get(`/inventory/assets/dashboard-stats/${params}`);
      setData(res.data);
      setError('');
    } catch {
      setError('Failed to load inventory dashboard data.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadDashboard(organisationId, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    api.get('/organisations/')
      .then((res) => setOrganisations(Array.isArray(res.data) ? res.data : res.data.results || []))
      .catch(() => setOrganisations([]));
  }, []);

  const handleOrganisationChange = (value) => {
    setOrganisationId(value);
    loadDashboard(value, false);
  };

  const statusCounts = data?.status_counts || {};
  const totalAssets = data?.total_assets ?? null;
  const available = statusCounts.available ?? null;
  const assigned = statusCounts.assigned ?? null;
  const maintenance = statusCounts.maintenance ?? null;
  const retired = statusCounts.retired ?? null;

  const licenseSummary = data?.software_licenses || {};

  const byTypeData = useMemo(() => {
    const types = data?.assets_by_type || [];
    return [...types]
      .sort((a, b) => b.count - a.count)
      .map((t) => ({ name: t.asset_type, count: t.count, tooltipLabel: t.asset_type }));
  }, [data]);

  const statusData = [
    { name: 'Available', value: available },
    { name: 'Assigned', value: assigned },
    { name: 'Maintenance', value: maintenance },
    { name: 'Retired', value: retired },
  ].filter((d) => d.value != null && d.value > 0);

  const orgData = (data?.assets_by_organisation || []).map((o) => ({ name: o.name, count: o.count, id: o.id }));
  const licenses = data?.license_usage || [];

  const handleTypeBarClick = (entry) => {
    const params = new URLSearchParams();
    params.set('type', entry.name);
    if (organisationId) params.set('organisation_id', organisationId);
    navigate(`/inventory/assets?${params.toString()}`);
  };

  const handleOrgBarClick = (entry) => {
    navigate(`/inventory/assets?organisation_id=${entry.id}`);
  };

  if (loading) {
    return (
      <Box>
        <Skeleton variant="rectangular" height={40} sx={{ mb: 2.5, borderRadius: 2 }} />
        <Grid container spacing={2.5} sx={{ mb: 3 }}>
          {[1, 2, 3, 4, 5].map((i) => (
            <Grid size={{ xs: 12, sm: 6, md: 2.4 }} key={i}>
              <Skeleton variant="rectangular" height={110} sx={{ borderRadius: 2 }} />
            </Grid>
          ))}
        </Grid>
        <Grid container spacing={2.5}>
          {[1, 2].map((i) => (
            <Grid size={{ xs: 12, md: 6 }} key={i}>
              <Skeleton variant="rectangular" height={340} sx={{ borderRadius: 2 }} />
            </Grid>
          ))}
        </Grid>
      </Box>
    );
  }

  return (
    <Box>
      {/* Filter row - scopes every stat, chart, and table below it */}
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 2.5 }} spacing={2} flexWrap="wrap">
        <Stack direction="row" spacing={2} alignItems="center">
          <TextField
            select
            size="small"
            label="Organisation"
            value={organisationId}
            onChange={(e) => handleOrganisationChange(e.target.value)}
            sx={{ minWidth: 260 }}
          >
            <MenuItem value="">All organisations</MenuItem>
            {organisations.map((org) => (
              <MenuItem key={org.id} value={String(org.id)}>{org.name}</MenuItem>
            ))}
          </TextField>
          {error && <Alert severity="error" sx={{ py: 0 }}>{error}</Alert>}
        </Stack>
        <Button variant="outlined" size="small" onClick={() => loadDashboard(organisationId, false)}>Refresh</Button>
      </Stack>

      {/* While refetching, hold the previous render at reduced opacity instead
          of flashing a skeleton - only the first load shows one. */}
      <Box sx={{ opacity: refreshing ? 0.5 : 1, transition: 'opacity 0.15s ease', pointerEvents: refreshing ? 'none' : 'auto' }}>
        {/* Asset KPI row */}
        <Grid container spacing={2.5} sx={{ mb: 2.5 }}>
          {[
            { title: 'Total Assets', value: totalAssets, icon: <DevicesIcon />, color: 'primary' },
            { title: 'Available', value: available, icon: <CheckCircleIcon />, color: 'success' },
            { title: 'Assigned', value: assigned, icon: <AssignmentTurnedInIcon />, color: 'info' },
            { title: 'Under Maintenance', value: maintenance, icon: <BuildIcon />, color: 'warning' },
            { title: 'Retired', value: retired, icon: <InventoryIcon />, color: 'default' },
          ].map((s) => (
            <Grid size={{ xs: 12, sm: 6, md: 2.4 }} key={s.title}>
              <StatCard {...s} />
            </Grid>
          ))}
        </Grid>

        {/* Software licence KPI row - reflects multi-org + unlimited licences */}
        <Grid container spacing={2.5} sx={{ mb: 3 }}>
          <Grid size={{ xs: 12, sm: 4 }}>
            <StatCard
              title="Total Licenses"
              value={licenseSummary.total_licenses}
              icon={<KeyIcon />}
              color="primary"
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 4 }}>
            <StatCard
              title="Seats Used"
              value={`${licenseSummary.used_seats ?? 0} / ${licenseSummary.total_seats ?? 0}`}
              subtitle="Excludes unlimited licenses"
              icon={<PieChartIcon />}
              color="info"
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 4 }}>
            <StatCard
              title="Unlimited Licenses"
              value={licenseSummary.unlimited_licenses}
              subtitle="No seat cap"
              icon={<AllInclusiveIcon />}
              color="success"
            />
          </Grid>
        </Grid>

        {/* Assets by Type - horizontal bars: with every type shown (not just a
            top-5 fold), several names are long, so labels run along the axis
            instead of rotating and colliding. */}
        <Grid container spacing={2.5} sx={{ mb: 2.5 }}>
          <Grid size={{ xs: 12 }}>
            <ChartCard
              title="Assets by Type"
              subtitle="Every asset type, click a bar to view those assets"
              minHeight={Math.max(240, byTypeData.length * 42)}
            >
              {byTypeData.length > 0 ? (
                <ResponsiveContainer width="100%" height={Math.max(240, byTypeData.length * 42)}>
                  <BarChart data={byTypeData} layout="vertical" margin={{ top: 0, right: 40, left: 8, bottom: 0 }} barSize={22}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" horizontal={false} />
                    <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11, fill: '#94A3B8' }} axisLine={false} tickLine={false} />
                    <YAxis type="category" dataKey="name" width={220} tick={{ fontSize: 11, fill: '#52514E' }} axisLine={false} tickLine={false} />
                    <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(79,70,229,0.04)' }} />
                    <Bar dataKey="count" radius={[0, 4, 4, 0]} name="Assets" fill={SEQUENTIAL_HUE} onClick={handleTypeBarClick} cursor="pointer">
                      <LabelList dataKey="count" position="right" style={{ fontSize: 11, fill: '#52514E', fontWeight: 600 }} />
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <Box sx={{ textAlign: 'center', py: 6 }}>
                  <Typography color="text.secondary" fontSize={14}>No data available.</Typography>
                </Box>
              )}
            </ChartCard>
          </Grid>
        </Grid>

        {/* Charts row 2 */}
        <Grid container spacing={2.5} sx={{ mb: 2.5 }}>
          <Grid size={{ xs: 12, md: organisationId ? 12 : 5 }}>
            <ChartCard title="Status Distribution" subtitle="Current asset status breakdown">
              {statusData.length > 0 ? (
                <ResponsiveContainer width="100%" height={280}>
                  <PieChart>
                    <Pie
                      data={statusData} cx="50%" cy="45%" outerRadius={90}
                      dataKey="value" label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                      labelLine={false}
                      onMouseEnter={(_, i) => setActiveStatusIndex(i)}
                      onMouseLeave={() => setActiveStatusIndex(null)}
                    >
                      {statusData.map((entry, i) => (
                        <Cell
                          key={entry.name}
                          fill={STATUS_COLOR_MAP[entry.name] || CATEGORICAL_COLORS[i % CATEGORICAL_COLORS.length]}
                          stroke="#fff"
                          strokeWidth={activeStatusIndex === i ? 3 : 1}
                          style={{ filter: activeStatusIndex === i ? 'brightness(1.08)' : 'none', cursor: 'pointer' }}
                        />
                      ))}
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
            </ChartCard>
          </Grid>

          {!organisationId && (
            <Grid size={{ xs: 12, md: 7 }}>
              <ChartCard title="Assets by Organisation" subtitle="Click a bar to view that organisation's assets" minHeight={Math.max(220, orgData.length * 56)}>
                {orgData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={Math.max(220, orgData.length * 56)}>
                    <BarChart
                      data={orgData}
                      layout="vertical"
                      margin={{ top: 0, right: 32, left: 8, bottom: 0 }}
                      barSize={22}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" horizontal={false} />
                      <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11, fill: '#94A3B8' }} axisLine={false} tickLine={false} />
                      <YAxis
                        type="category" dataKey="name" width={150}
                        tick={{ fontSize: 11, fill: '#52514E' }} axisLine={false} tickLine={false}
                        tickFormatter={(v) => (v.length > 22 ? `${v.slice(0, 22)}…` : v)}
                      />
                      <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(79,70,229,0.04)' }} />
                      <Bar dataKey="count" radius={[0, 4, 4, 0]} name="Assets" onClick={handleOrgBarClick} cursor="pointer">
                        {orgData.map((entry, i) => (
                          <Cell key={entry.name} fill={CATEGORICAL_COLORS[i % CATEGORICAL_COLORS.length]} />
                        ))}
                        <LabelList dataKey="count" position="right" style={{ fontSize: 11, fill: '#52514E', fontWeight: 600 }} />
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <Box sx={{ textAlign: 'center', py: 6 }}>
                    <Typography color="text.secondary" fontSize={14}>No data available.</Typography>
                  </Box>
                )}
              </ChartCard>
            </Grid>
          )}
        </Grid>

        {/* Software license utilization - always full width */}
        <Grid container spacing={2.5} sx={{ mb: 3 }}>
          <Grid size={{ xs: 12 }}>
            <Card sx={{ height: '100%' }}>
              <CardContent sx={{ p: 2.5, '&:last-child': { pb: 2.5 } }}>
                <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 0.5 }}>Software License Seat Utilization</Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2, fontSize: 13 }}>
                  Seat usage across software products - unlimited licenses have no cap to track
                </Typography>
                {licenses.length > 0 ? (
                  <Stack spacing={1.5}>
                    {licenses.map((lic) => {
                      const pct = lic.total_seats > 0 ? Math.round((lic.used_seats / lic.total_seats) * 100) : 0;
                      const barColor = pct > 90 ? 'error.main' : pct > 70 ? 'warning.main' : 'primary.main';
                      return (
                        <Box key={lic.id} sx={{ p: 1.5, border: '1px solid', borderColor: 'divider', borderRadius: 2 }}>
                          <Stack direction="row" alignItems="center" justifyContent="space-between" spacing={1} sx={{ mb: lic.organisations.length ? 0.75 : 0 }}>
                            <Typography variant="body2" fontWeight={600} noWrap sx={{ minWidth: 0 }}>
                              {lic.software_name}
                            </Typography>
                            {lic.is_unlimited ? (
                              <Chip icon={<AllInclusiveIcon sx={{ fontSize: 16 }} />} label="Unlimited" size="small" color="success" variant="outlined" />
                            ) : (
                              <Stack direction="row" spacing={1} alignItems="center" sx={{ minWidth: 160, flex: 1, maxWidth: 220 }}>
                                <LinearProgress
                                  variant="determinate" value={Math.min(pct, 100)}
                                  sx={{
                                    flex: 1, height: 6, borderRadius: 3, bgcolor: 'grey.100',
                                    '& .MuiLinearProgress-bar': { borderRadius: 3, bgcolor: barColor },
                                  }}
                                />
                                <Typography variant="caption" fontWeight={600} sx={{ minWidth: 60, color: pct > 90 ? 'error.main' : 'text.secondary' }}>
                                  {lic.used_seats}/{lic.total_seats} ({pct}%)
                                </Typography>
                              </Stack>
                            )}
                          </Stack>
                          {lic.organisations.length > 0 && (
                            <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                              {lic.organisations.map((name) => (
                                <MuiTooltip title={name} key={name}>
                                  <Chip label={name.length > 24 ? `${name.slice(0, 24)}…` : name} size="small" variant="outlined" sx={{ fontSize: 11 }} />
                                </MuiTooltip>
                              ))}
                            </Stack>
                          )}
                        </Box>
                      );
                    })}
                  </Stack>
                ) : (
                  <Box sx={{ textAlign: 'center', py: 6 }}>
                    <Typography color="text.secondary" fontSize={14}>No software licenses recorded yet.</Typography>
                  </Box>
                )}
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </Box>
    </Box>
  );
}

export default InventoryDashboard;
