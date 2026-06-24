import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Card,
  CardContent,
  Grid,
  Typography,
  Skeleton,
  Alert,
  ButtonBase,
} from '@mui/material';
import PeopleIcon from '@mui/icons-material/People';
import ConfirmationNumberIcon from '@mui/icons-material/ConfirmationNumber';
import DevicesIcon from '@mui/icons-material/Devices';
import LaptopWindowsIcon from '@mui/icons-material/LaptopWindows';
import PersonAddIcon from '@mui/icons-material/PersonAdd';
import BusinessIcon from '@mui/icons-material/Business';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import api from '../../api/axios';
import { useAuth } from '../../context/AuthContext';

const STAT_COLORS = {
  primary:  { bg: 'rgba(79,70,229,0.08)',  icon: '#4F46E5', bar: '#4F46E5' },
  error:    { bg: 'rgba(239,68,68,0.08)',  icon: '#EF4444', bar: '#EF4444' },
  success:  { bg: 'rgba(16,185,129,0.08)', icon: '#10B981', bar: '#10B981' },
  info:     { bg: 'rgba(14,165,233,0.08)', icon: '#0EA5E9', bar: '#0EA5E9' },
  warning:  { bg: 'rgba(245,158,11,0.08)', icon: '#F59E0B', bar: '#F59E0B' },
};

const BAR_PALETTE = ['#4F46E5', '#7C3AED', '#0EA5E9', '#10B981', '#F59E0B', '#EF4444', '#EC4899', '#8B5CF6'];

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
          <Box
            sx={{
              bgcolor: colors.bg,
              borderRadius: '12px',
              p: 1.25,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
            }}
          >
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
      <Box sx={{
        bgcolor: '#0F172A',
        borderRadius: '8px',
        px: 1.5, py: 1,
        boxShadow: '0 10px 25px rgba(0,0,0,0.25)',
      }}>
        <Typography sx={{ color: '#94A3B8', fontSize: 11, mb: 0.25 }}>{label}</Typography>
        <Typography sx={{ color: '#F8FAFC', fontWeight: 700, fontSize: 16 }}>
          {payload[0].value}
        </Typography>
      </Box>
    );
  }
  return null;
};

function Dashboard() {
  const { user, hasRole } = useAuth();
  const [stats, setStats] = useState({ employees: null, openTickets: null, availableAssets: null, systemsWithMdm: null, pendingOnboardings: null });
  const [chartData, setChartData] = useState([]);
  const [mdmCategoryData, setMdmCategoryData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const userName = user?.full_name || user?.email || 'User';
  const firstName = userName.split(' ')[0];
  const roleName = (user?.role || '').replace(/_/g, ' ');
  const navigate = useNavigate();

  useEffect(() => {
    const fetchAll = async () => {
      setLoading(true);
      try {
        const requests = [];
        if (hasRole('super_admin', 'hr', 'it_specialist')) {
          requests.push(api.get('/employees/').catch(() => ({ data: { count: null, results: [] } })));
        } else {
          requests.push(Promise.resolve({ data: { count: null } }));
        }
        requests.push(api.get('/tickets/?status=open').catch(() => ({ data: { count: null, results: [] } })));
        if (hasRole('super_admin', 'it_specialist')) {
          requests.push(api.get('/inventory/assets/?status=available&source=portal').catch(() => ({ data: { count: null } })));
          requests.push(api.get('/onboarding/?status=pending').catch(() => ({ data: { count: null } })));
          requests.push(api.get('/inventory/assets/dashboard-stats/').catch(() => ({ data: null })));
          requests.push(api.get('/integrations/suremdm/summary/').catch(() => ({ data: null })));
        } else {
          requests.push(...[null, null, null, null].map(() => Promise.resolve({ data: null })));
        }

        const [empRes, ticketRes, assetRes, onboardRes, dashRes, mdmRes] = await Promise.all(requests);

        setStats({
          employees: empRes.data?.count ?? (Array.isArray(empRes.data) ? empRes.data.length : null),
          openTickets: ticketRes.data?.count ?? (Array.isArray(ticketRes.data) ? ticketRes.data.length : null),
          availableAssets: assetRes.data?.count ?? (Array.isArray(assetRes.data) ? assetRes.data.length : null),
          systemsWithMdm: mdmRes?.data?.total_systems ?? null,
          pendingOnboardings: onboardRes.data?.count ?? (Array.isArray(onboardRes.data) ? onboardRes.data.length : null),
        });

        if (dashRes?.data) {
          const raw = dashRes.data;
          if (Array.isArray(raw.assets_by_type)) {
            setChartData(raw.assets_by_type.map((i) => ({ name: i.asset_type || i.name || i.type, count: i.count || i.total })));
          } else if (raw.by_type) {
            setChartData(Object.entries(raw.by_type).map(([name, count]) => ({ name, count })));
          }
        }

        if (Array.isArray(mdmRes?.data?.categories)) {
          setMdmCategoryData(mdmRes.data.categories.map((i) => ({ name: i.category, count: i.count })));
        }
      } catch {
        setError('Failed to load dashboard data.');
      } finally {
        setLoading(false);
      }
    };
    fetchAll();
  }, [hasRole]);

  const canSeeAssets = hasRole('super_admin', 'it_specialist');
  const canSeeEmployees = hasRole('super_admin', 'hr', 'it_specialist');

  return (
    <Box>
      {/* Welcome banner */}
      <Box
        sx={{
          mb: 3,
          p: 3,
          borderRadius: '16px',
          background: 'linear-gradient(135deg, #0F172A 0%, #1E1B4B 50%, #312E81 100%)',
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        <Box sx={{
          position: 'absolute', top: -40, right: -40,
          width: 200, height: 200, borderRadius: '50%',
          background: 'rgba(99,102,241,0.15)',
          pointerEvents: 'none',
        }} />
        <Box sx={{
          position: 'absolute', bottom: -30, right: 80,
          width: 130, height: 130, borderRadius: '50%',
          background: 'rgba(124,58,237,0.12)',
          pointerEvents: 'none',
        }} />
        <Typography sx={{ color: '#F8FAFC', fontWeight: 800, fontSize: { xs: 20, md: 24 }, mb: 0.5 }}>
          Good day, {firstName}!
        </Typography>
        <Typography sx={{ color: '#94A3B8', fontSize: 14, textTransform: 'capitalize' }}>
          {roleName} — here's what's happening today
        </Typography>
      </Box>

      {error && <Alert severity="warning" sx={{ mb: 2.5 }}>{error}</Alert>}

      {/* Stat Cards */}
      <Grid container spacing={2.5} sx={{ mb: 3 }}>
        {canSeeEmployees && (
          <Grid item xs={12} sm={6} md={3}>
            <StatCard title="Total Employees" value={stats.employees} icon={<PeopleIcon />} color="primary" loading={loading} />
          </Grid>
        )}
        <Grid item xs={12} sm={6} md={canSeeEmployees ? 3 : 4}>
          <StatCard title="Open Tickets" value={stats.openTickets} icon={<ConfirmationNumberIcon />} color="error" loading={loading} />
        </Grid>
        {canSeeAssets && (
          <>
            <Grid item xs={12} sm={6} md={3}>
              <StatCard title="Available Assets" value={stats.availableAssets} icon={<DevicesIcon />} color="success" loading={loading} />
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <StatCard title="MDM Systems" value={stats.systemsWithMdm} icon={<LaptopWindowsIcon />} color="info" loading={loading} />
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <StatCard title="Pending Onboardings" value={stats.pendingOnboardings} icon={<PersonAddIcon />} color="warning" loading={loading} />
            </Grid>
          </>
        )}
      </Grid>

      {/* Shortcut tiles for quick actions */}
      {hasRole('super_admin') && (
        <Grid container spacing={2.5} sx={{ mb: 3 }}>
          <Grid item xs={12} sm={6} md={3}>
            <Card
              component={ButtonBase}
              sx={{
                height: '100%',
                width: '100%',
                display: 'block',
                textAlign: 'left',
              }}
              onClick={() => navigate('/organisations')}
            >
              <CardContent sx={{ p: 2.5, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box>
                  <Typography variant="body2" color="text.secondary" fontWeight={500} sx={{ fontSize: 13, mb: 1 }}>
                    Shortcut
                  </Typography>
                  <Typography sx={{ fontSize: 18, fontWeight: 700, color: 'text.primary' }}>
                    Organisation Management
                  </Typography>
                </Box>
                <Box sx={{ bgcolor: 'rgba(79,70,229,0.08)', borderRadius: '12px', p: 1.25 }}>
                  <BusinessIcon sx={{ fontSize: 26, color: '#4F46E5' }} />
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Charts */}
      {canSeeAssets && (
        <Grid container spacing={2.5}>
          <Grid item xs={12} lg={7}>
            <Card sx={{ p: 2.5 }}>
              <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 0.5 }}>
                Asset Distribution by Type
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2.5, fontSize: 13 }}>
                Breakdown of hardware & software assets
              </Typography>
              {loading ? (
                <Skeleton variant="rectangular" height={260} sx={{ borderRadius: 2 }} />
              ) : chartData.length > 0 ? (
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={chartData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }} barSize={28}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" vertical={false} />
                    <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#94A3B8' }} axisLine={false} tickLine={false} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: '#94A3B8' }} axisLine={false} tickLine={false} />
                    <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(79,70,229,0.04)' }} />
                    <Bar dataKey="count" radius={[6, 6, 0, 0]} name="Assets">
                      {chartData.map((_, i) => (
                        <Cell key={i} fill={BAR_PALETTE[i % BAR_PALETTE.length]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <Box sx={{ textAlign: 'center', py: 6 }}>
                  <Typography color="text.secondary" fontSize={14}>No asset data available.</Typography>
                </Box>
              )}
            </Card>
          </Grid>

          <Grid item xs={12} lg={5}>
            <Card sx={{ p: 2.5 }}>
              <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 0.5 }}>
                MDM Systems by Category
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2.5, fontSize: 13 }}>
                Device enrollment by OS category
              </Typography>
              {loading ? (
                <Skeleton variant="rectangular" height={260} sx={{ borderRadius: 2 }} />
              ) : mdmCategoryData.length > 0 ? (
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={mdmCategoryData} margin={{ top: 0, right: 0, left: -20, bottom: 36 }} barSize={28}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" vertical={false} />
                    <XAxis
                      dataKey="name"
                      tick={{ fontSize: 11, fill: '#94A3B8' }}
                      axisLine={false}
                      tickLine={false}
                      interval={0}
                      angle={-30}
                      textAnchor="end"
                      height={56}
                    />
                    <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: '#94A3B8' }} axisLine={false} tickLine={false} />
                    <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(14,165,233,0.04)' }} />
                    <Bar dataKey="count" radius={[6, 6, 0, 0]} name="Systems">
                      {mdmCategoryData.map((_, i) => (
                        <Cell key={i} fill={BAR_PALETTE[(i + 2) % BAR_PALETTE.length]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <Box sx={{ textAlign: 'center', py: 6 }}>
                  <Typography color="text.secondary" fontSize={14}>No MDM category data available.</Typography>
                </Box>
              )}
            </Card>
          </Grid>
        </Grid>
      )}
    </Box>
  );
}

export default Dashboard;
