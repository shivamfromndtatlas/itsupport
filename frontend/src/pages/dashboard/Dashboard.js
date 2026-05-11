import React, { useEffect, useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Grid,
  Typography,
  Skeleton,
  Alert,
} from '@mui/material';
import PeopleIcon from '@mui/icons-material/People';
import ConfirmationNumberIcon from '@mui/icons-material/ConfirmationNumber';
import DevicesIcon from '@mui/icons-material/Devices';
import PersonAddIcon from '@mui/icons-material/PersonAdd';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import api from '../../api/axios';
import { useAuth } from '../../context/AuthContext';

function StatCard({ title, value, icon, color, loading }) {
  return (
    <Card sx={{ borderRadius: 2, boxShadow: 2, height: '100%' }}>
      <CardContent sx={{ display: 'flex', alignItems: 'center', gap: 2, p: 3 }}>
        <Box
          sx={{
            bgcolor: `${color}.light`,
            borderRadius: 2,
            p: 1.5,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          {React.cloneElement(icon, { sx: { fontSize: 32, color: `${color}.main` } })}
        </Box>
        <Box>
          <Typography variant="body2" color="text.secondary" fontWeight={500}>
            {title}
          </Typography>
          {loading ? (
            <Skeleton width={60} height={36} />
          ) : (
            <Typography variant="h4" fontWeight={700}>
              {value ?? '--'}
            </Typography>
          )}
        </Box>
      </CardContent>
    </Card>
  );
}

function Dashboard() {
  const { user, hasRole } = useAuth();
  const [stats, setStats] = useState({
    employees: null,
    openTickets: null,
    availableAssets: null,
    pendingOnboardings: null,
  });
  const [chartData, setChartData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const userName = user?.full_name || user?.email || 'User';
  const roleName = (user?.role || '').replace('_', ' ');

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
          requests.push(
            api.get('/inventory/assets/?status=available').catch(() => ({ data: { count: null, results: [] } }))
          );
          requests.push(
            api.get('/onboarding/?status=pending').catch(() => ({ data: { count: null, results: [] } }))
          );
          requests.push(
            api.get('/inventory/assets/dashboard-stats/').catch(() => ({ data: null }))
          );
        } else {
          requests.push(Promise.resolve({ data: { count: null } }));
          requests.push(Promise.resolve({ data: { count: null } }));
          requests.push(Promise.resolve({ data: null }));
        }

        const [empRes, ticketRes, assetRes, onboardRes, dashRes] = await Promise.all(requests);

        const empCount =
          empRes.data?.count ?? (Array.isArray(empRes.data) ? empRes.data.length : null);
        const ticketCount =
          ticketRes.data?.count ?? (Array.isArray(ticketRes.data) ? ticketRes.data.length : null);
        const assetCount =
          assetRes.data?.count ?? (Array.isArray(assetRes.data) ? assetRes.data.length : null);
        const onboardCount =
          onboardRes.data?.count ?? (Array.isArray(onboardRes.data) ? onboardRes.data.length : null);

        setStats({
          employees: empCount,
          openTickets: ticketCount,
          availableAssets: assetCount,
          pendingOnboardings: onboardCount,
        });

        // Parse chart data
        if (dashRes.data) {
          const raw = dashRes.data;
          if (Array.isArray(raw.assets_by_type)) {
            setChartData(
              raw.assets_by_type.map((item) => ({
                name: item.asset_type || item.name || item.type,
                count: item.count || item.total,
              }))
            );
          } else if (raw.by_type) {
            setChartData(
              Object.entries(raw.by_type).map(([name, count]) => ({ name, count }))
            );
          }
        }
      } catch (err) {
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
      {/* Welcome */}
      <Card sx={{ mb: 3, borderRadius: 2, bgcolor: 'primary.main', color: 'white' }}>
        <CardContent sx={{ p: 3 }}>
          <Typography variant="h5" fontWeight={700}>
            Welcome back, {userName}!
          </Typography>
          <Typography variant="body2" sx={{ opacity: 0.85, textTransform: 'capitalize', mt: 0.5 }}>
            Role: {roleName}
          </Typography>
        </CardContent>
      </Card>

      {error && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {/* Stat Cards */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        {canSeeEmployees && (
          <Grid item xs={12} sm={6} md={3}>
            <StatCard
              title="Total Employees"
              value={stats.employees}
              icon={<PeopleIcon />}
              color="primary"
              loading={loading}
            />
          </Grid>
        )}
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Open Tickets"
            value={stats.openTickets}
            icon={<ConfirmationNumberIcon />}
            color="error"
            loading={loading}
          />
        </Grid>
        {canSeeAssets && (
          <>
            <Grid item xs={12} sm={6} md={3}>
              <StatCard
                title="Available Assets"
                value={stats.availableAssets}
                icon={<DevicesIcon />}
                color="success"
                loading={loading}
              />
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <StatCard
                title="Pending Onboardings"
                value={stats.pendingOnboardings}
                icon={<PersonAddIcon />}
                color="warning"
                loading={loading}
              />
            </Grid>
          </>
        )}
      </Grid>

      {/* Bar Chart */}
      {canSeeAssets && (
        <Card sx={{ borderRadius: 2, boxShadow: 2, p: 2 }}>
          <Typography variant="h6" fontWeight={600} sx={{ mb: 2, px: 1 }}>
            Asset Distribution by Type
          </Typography>
          {loading ? (
            <Skeleton variant="rectangular" height={280} />
          ) : chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" tick={{ fontSize: 13 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 13 }} />
                <Tooltip />
                <Legend />
                <Bar dataKey="count" fill="#1565C0" radius={[4, 4, 0, 0]} name="Assets" />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <Box sx={{ textAlign: 'center', py: 6 }}>
              <Typography color="text.secondary">No asset data available.</Typography>
            </Box>
          )}
        </Card>
      )}
    </Box>
  );
}

export default Dashboard;
